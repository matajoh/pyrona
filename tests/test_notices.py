"""Tests for the noticeboard."""

import random
from threading import Event
from time import sleep

from pyrona import (
    notice_compare_exchange,
    notice_exchange,
    notice_read,
    notice_register,
    Region,
    wait,
    when
)


def test_io():
    notice_register(["foo", "bar"])
    notice_exchange("foo", 42)
    assert notice_read("foo") == 42
    notice_exchange("bar", "baz")
    assert notice_read("bar") == "baz"


def test_counting():
    notice_register(["count"])
    notice_exchange("count", 0)

    for _ in range(10):
        @when()
        def _():
            value = notice_read("count")
            while True:
                if value == notice_compare_exchange("count", value + 1, value):
                    break

    @when()
    def _():
        assert notice_read("count") == 10

    wait()


def test_ordering():
    notice_register(["foo", "bar"])
    notice_exchange("foo", 42)
    notice_exchange("bar", 24)

    for _ in range(10):
        @when()
        def _():
            assert notice_read("foo") == 42
            assert notice_read("bar") == 24

    @when()
    def _():
        notice_exchange("foo", 24)
        notice_exchange("bar", 42)

    for _ in range(10):
        @when()
        def _():
            assert notice_read("foo") == 24
            assert notice_read("bar") == 42

    wait()


def test_not_immutable():
    notice_register(["foo"])

    try:
        notice_exchange("foo", [])
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError.")


def test_exists():
    notice_register(["foo"])

    try:
        notice_read("bar")
    except KeyError:
        pass
    else:
        raise AssertionError("Expected KeyError.")

    try:
        notice_exchange("bar", 42)
    except KeyError:
        pass
    else:
        raise AssertionError("Expected KeyError.")

    try:
        notice_compare_exchange("bar", 42, 0)
    except KeyError:
        pass
    else:
        raise AssertionError("Expected KeyError.")


def test_write_once():
    notice_register(["foo"])

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
            sleep(random.random())
            if notice_exchange("foo", r.i) is None:
                @when(output)
                def _():
                    output.callback()

    wait()

    event.wait()
    assert count == 1
