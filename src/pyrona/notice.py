"""Implementation of a concurrent-safe notice system."""

from threading import current_thread
from typing import Any, Callable

from .core import is_imm, Region
from .when import when


current_nb = {}
notice = Region("__notice__")
with notice:
    notice.callbacks = {}

notice.make_shareable()


def notice_read(key: str) -> Any:
    """Read the value of a notice."""
    thread = current_thread()
    if not hasattr(thread, "noticeboard"):
        thread.noticeboard = current_nb.copy()

    return thread.noticeboard.get(key, None)


def notice_changed(key: str, callback: Callable[[Any], None]):
    """Ask to be notified when the noticeboard next changes."""
    cb = Region()
    with cb:
        cb.key = key
        cb.callback = callback

    cb.make_shareable()

    @when(notice, cb)
    def _():
        if cb.key not in notice.callbacks:
            notice.callbacks[cb.key] = []

        notice.callbacks[cb.key].append(cb)


def notice_write(key: str, value: Any, condition: Callable[[Any, Any], bool] = None):
    """Write a value to a notice.

    Args:
        key: The name of the notice to write to.
        value: The value to write to the notice. Must be immutable.
        condition: A condition that must be met for the write to occur.
    """
    if not is_imm(value):
        raise ValueError("Value must be immutable.")

    r = Region()
    with r:
        r.key = key
        r.value = value
        r.condition = condition

    r.make_shareable()

    @when(r, notice)
    def _():
        global current_nb
        if r.condition is not None:
            old_value = current_nb.get(r.key, None)
            if not r.condition(old_value, r.value):
                return

        current_nb = current_nb.copy()
        current_nb[r.key] = r.value
        if r.key in notice.callbacks:
            for cb in notice.callbacks[r.key]:
                @when(cb, r)
                def _(cb, r):
                    cb.callback(r.value)

            del notice.callbacks[r.key]


def notice_clear():
    """Clear the current notice board."""
    @when(notice)
    def _():
        global current_nb
        current_nb = {}
