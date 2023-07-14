"""Module providing a simulation of behavior-oriented concurrency."""

from functools import wraps
from queue import Empty, Queue
from threading import Event, Lock, Thread
from typing import Callable, List

from .core import Region, RegionIsolationError


class _Cown:
    def __init__(self, region: Region):
        self.region = region

    def compare_exchange(self, value: "_Request", comparand: "_Request") -> "_Request":
        with self.region.lock:
            if self.region.last == comparand:
                prev = self.region.last
                object.__setattr__(self.region, "last", value)
                return prev

            return self.region.last

    def exchange(self, request: "_Request") -> "_Request":
        with self.region.lock:
            prev = self.region.last
            object.__setattr__(self.region, "last", request)
            return prev

    def __lt__(self, other: "_Cown") -> bool:
        return self.region < other.region

    def __eq__(self, other: "_Cown") -> bool:
        return self.region == other.region

    def __hash__(self) -> int:
        return hash(self.region)


class _Terminator:
    def __init__(self):
        self._count = 1
        self._lock = Lock()
        self._event = Event()

    def increment(self):
        with self._lock:
            self._count += 1

    def decrement(self):
        with self._lock:
            self._count -= 1
            if self._count == 0:
                self._event.set()

    def wait(self):
        self.decrement()
        self._event.wait()


class _Behavior:
    """Behaviour that captures the content of a when body.

    It contains all the state required to run the body, and release the
    cowns when the body has finished.
    """
    def __init__(self, t: Callable, *cowns: _Cown):
        self.thunk = t
        # We add an additional count, so that the 2PL is finished
        # before we start running the thunk. Without this, the calls to
        # Release at the end of the thunk could race with the calls to
        # FinishEnqueue in the 2PL.
        self.count = len(cowns) + 1
        self.lock = Lock()

        cowns = list(cowns)
        cowns.sort()
        self.requests : List[_Request] = [_Request(r) for r in cowns]

    def schedule(self):
        """Schedules the behavior.

        Performs two phase locking (2PL) over the enqueuing of the requests.
        This ensures that the overall effect of the enqueue is atomic.
        """
        # Complete first phase of 2PL enqueuing on all cowns.
        for r in self.requests:
            r.start_enqueue(self)

        # Complete second phase of 2PL enqueuing on all cowns.
        for r in self.requests:
            r.finish_enqueue()

        # Resolve the additional request. [See comment in the Constructor]
        # All the cowns may already be resolved, in which case, this will
        # schedule the task.
        self.resolve_one()

        # Prevent runtime exiting until this has run.
        _terminator.increment()

    def __call__(self):
        # Run body.
        self.thunk()
        # Release all the cowns.
        for r in self.requests:
            r.release()

        _terminator.decrement()

    def resolve_one(self):
        """Resolves a single outstanding request for this behaviour.

        Called when a request is at the head of the queue for a particular cown.
        If this is the last request, then the thunk is scheduled.
        """
        with self.lock:
            self.count -= 1
            if self.count != 0:
                return

        # Last request so schedule the task.
        thread = Thread(target=self)
        thread.start()


class _Request:
    def __init__(self, target: _Cown):
        self.target = target
        self.next : _Behavior = None
        self.next_lock = Lock()
        self.scheduled = False
        self.scheduled_lock = Lock()

    def __repr__(self) -> str:
        return "Request({})".format(self.target.region)

    def is_scheduled(self) -> bool:
        with self.scheduled_lock:
            return self.scheduled

    def set_next(self, behavior: _Behavior):
        with self.next_lock:
            self.next = behavior

    def release(self):
        """Release the cown to the next behaviour.

        This is called when the associated behaviour has completed, and thus can
        allow any waiting behaviour to run.

        If there is no next behaviour, then the cown's `last` pointer is set to null.
        """
        # This code is effectively a MCS-style queue lock release.
        with self.next_lock:
            if self.next is None:
                if self.target.compare_exchange(None, self) == self:
                    return

        # Wait for the next pointer to be set. The target.last is no longer us
        # so this should not take long.
        while True:
            with self.next_lock:
                if self.next is not None:
                    break

        with self.next_lock:
            self.next.resolve_one()

    def start_enqueue(self, behavior: _Behavior):
        """Start the first phase of the 2PL enqueue operation.

        This enqueues the request onto the cown.  It will only return
        once any previous behaviour on this cown has finished enqueueing
        on all its required cowns.  This ensures that the 2PL is obeyed.
        """
        prev = self.target.exchange(self)
        if prev is None:
            behavior.resolve_one()
            return

        prev.set_next(behavior)
        while True:
            if prev.is_scheduled():
                break

    def finish_enqueue(self):
        """Finish the second phase of the 2PL enqueue operation.

        This will set the scheduled flag, so subsequent behaviours on this
        cown can continue the 2PL enqueue.
        """
        with self.scheduled_lock:
            self.scheduled = True


_terminator = _Terminator()

_behaviors : List[_Behavior] = []

_exceptions = Queue()


def _safe_run(func):
    try:
        func()
    except Exception as ex:
        _exceptions.put(ex)


def when(*regions: Region):
    """Returns a decorator which opens all the regions before calling the function."""
    def when_factory(func):
        @wraps(func)
        def when_():
            for r in regions:
                if r.is_shared:
                    r._open()
                else:
                    raise RegionIsolationError("Region is private.")
            if func.__code__.co_argcount > 0:
                value = func(*regions)
            else:
                value = func()

            for r in regions:
                r._close()
            return value

        cowns = [_Cown(r) for r in regions]
        behavior = _Behavior(lambda: _safe_run(when_), *cowns)
        behavior.schedule()
        _behaviors.append(behavior)

        return when_

    return when_factory


def wait():
    """Waits for all behaviors to execute."""
    _terminator.wait()
    try:
        ex = _exceptions.get(block=False)
    except Empty:
        pass
    else:
        raise ex
