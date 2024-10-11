"""Tests for the noticeboard."""

from pyrona import (
    notice_compare_exchange,
    notice_exchange,
    notice_read,
    notice_register,
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


def test_not_immutable():
    notice_register(["foo"])

    try:
        notice_exchange("foo", [])
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError.")
