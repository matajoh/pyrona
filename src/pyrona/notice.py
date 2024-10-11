"""Implementation of a concurrent-safe notice system."""

from threading import Event, Lock
from typing import Any, List, Mapping

from .core import is_imm


class Notice:
    """A notice is a many-reader, one-writer concurrency primitive.

    In this demonstrator, the notice is a simple wrapper around a threading.Event.
    However, with the use of atomics it can be made lock-free.
    """

    def __init__(self):
        """Initialize the notice."""
        self.lock = Lock()
        self.event = Event()
        self.event.set()
        self.value = None

    def read(self) -> Any:
        """Read the value of the notice.

        This will only block if the notice is actively being written to.
        """
        self.event.wait()
        return self.value

    def exchange(self, value: Any) -> Any:
        """Write a value to the notice.

        This will block any readers until the value is read.

        Args:
            value: The value to write to the notice. Must be immutable.
        """
        if not is_imm(value):
            raise ValueError("Value must be immutable.")

        with self.lock:
            prev = self.value
            self.event.clear()
            self.value = value
            self.event.set()
            return prev

    def compare_exchange(self, value: Any, comparand: Any) -> Any:
        """Compare and exchange the value of the notice.

        This will only block if the notice is actively being written to.
        The exchange will only occur if the value is equal to the comparand.

        Args:
            value: The new value to write to the notice. Must be immutable.
            comparand: The value to compare against.

        Returns:
            The previous value of the notice.
        """
        if not is_imm(value):
            raise ValueError("Value must be immutable.")

        with self.lock:
            if self.value == comparand:
                prev = self.value
                self.event.clear()
                self.value = value
                self.event.set()
                return prev

            return self.value


class NoticeBoard:
    """A notice board is a collection of notices."""

    def __init__(self, names: List[str]):
        """Initialize the notice board.

        Args:
            names: A list of names for the notices.
        """
        self.notices: Mapping[str, Notice] = {name: Notice() for name in names}

    def read(self, key: str) -> Any:
        """Read the value of a notice.

        Args:
            key: The name of the notice to read.

        Returns:
            The value of the notice.
        """
        if key not in self.notices:
            raise KeyError(f"Notice '{key}' not found.")

        return self.notices[key].read()

    def exchange(self, key: str, value: Any):
        """Write a value to a notice.

        Args:
            key: The name of the notice to write to.
            value: The value to write to the notice. Must be immutable.
        """
        if key not in self.notices:
            raise KeyError(f"Notice '{key}' not found.")

        self.notices[key].exchange(value)

    def compare_exchange(self, key: str, value: Any, comparand: Any) -> Any:
        """Compare and exchange the value of a notice.

        Args:
            key: The name of the notice to write to.
            value: The new value to write to the notice. Must be immutable.
            comparand: The value to compare against.

        Returns:
            The previous value of the notice.
        """
        if key not in self.notices:
            raise KeyError(f"Notice '{key}' not found.")

        return self.notices[key].compare_exchange(value, comparand)


noticeboard = None


def notice_register(names: List[str]):
    """Register a list of notice names.

    Args:
        names: A list of names for the notices.
    """
    global noticeboard
    noticeboard = NoticeBoard(names)


def notice_read(key: str) -> Any:
    """Read the value of a notice."""
    return noticeboard.read(key)


def notice_exchange(key: str, value: Any) -> Any:
    """Write a value to a notice.

    Args:
        key: The name of the notice to write to.
        value: The value to write to the notice. Must be immutable.
    """
    return noticeboard.exchange(key, value)


def notice_compare_exchange(key: str, value: Any, comparand: Any) -> Any:
    """Compare and exchange the value of a notice.

    Args:
        key: The name of the notice to write to.
        value: The new value to write to the notice. Must be immutable.
        comparand: The value to compare against.

    Returns:
        The previous value of the notice.
    """
    return noticeboard.notices[key].compare_exchange(value, comparand)
