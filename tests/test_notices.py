"""Tests for the noticeboard."""

import random
from threading import Event
from time import sleep

from pyrona import (
    notice_changed,
    notice_clear,
    notice_read,
    notice_write,
    Region,
    wait,
    when
)


def test_caching():
    notice_clear()

    @when()
    def _():
        assert notice_read("foo") is None

        notice_write("foo", 42)
        assert notice_read("foo") is None

        for i in range(10):
            r = Region()
            with r:
                r.value = i

            r.make_shareable()

            @when(r)
            def _(r):
                notice_write("foo", r.value)

        sleep(0.5)
        assert notice_read("foo") is None

    def check_for_value(value):
        assert value is not None

    notice_changed("foo", check_for_value)

    wait()


def test_conditions():
    notice_clear()
    notice_write("count", 0)
    for i in range(10):
        r = Region()
        with r:
            r.value = i

        r.make_shareable()

        @when(r)
        def _(r):
            notice_write("count", r.value, lambda a, b: a is None or a < b)

    wait()

    def check_for_value(value):
        assert value == 9

    notice_changed("count", check_for_value)
    wait()


def test_not_immutable():
    try:
        notice_write("foo", [])
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError.")


def test_write_once():
    notice_clear()
    count = 0

    event = Event()

    def callback():
        nonlocal count
        count += 1
        event.set()

    output = Region()
    with output:
        output.callback = callback

    output.make_shareable()

    for i in range(10):
        r = Region()
        with r:
            r.i = i

        r.make_shareable()

        @when(r)
        def _(r):
            def callback(old, _):
                if old is None:
                    @when(output)
                    def _():
                        output.callback()

                    return True
                else:
                    return False

            sleep(random.random())
            notice_write("foo", r.i, callback)

    wait()

    event.wait(2)
    assert count == 1
