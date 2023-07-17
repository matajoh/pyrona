"""Tests for when constructors."""

import json

from pyrona import Region, RegionIsolationError, wait, when


class MockObject:
    """Mock object used for testing."""
    def __str__(self) -> str:
        """Produces a simple representation of the object graph."""
        return json.dumps(self.__dict__)


def test_shareable():
    r = Region().make_shareable()
    assert r.is_shared


def test_when():
    my_account = Region()
    your_account = Region()

    with my_account, your_account:
        my_account.balance = 100
        your_account.balance = 0

    my_account.make_shareable()
    your_account.make_shareable()

    # when my_account, your_account as m, y:
    @when(my_account, your_account)
    def _(m, y):
        m.balance, y.balance = y.balance, m.balance

    # when my_account, your_account as m, y:
    @when(my_account, your_account)
    def _():
        assert my_account.balance == 0
        assert your_account.balance == 100

    wait()


def test_detach():
    c1 = Region("c1")
    c2 = Region("c2")

    with c1, c2:
        c1.a = "foo"
        c2.b = "bar"

    c1.make_shareable()
    c2.make_shareable()

    # when c1, c2:
    @when(c1, c2)
    def _():
        r1, r2 = c1.detach_all("r1"), c2.detach_all("r2")
        merge = c1.merge(r2)
        c1.b = merge.b
        merge = c2.merge(r1)
        c2.a = merge.a

    # when c1, c2:
    @when(c1, c2)
    def _():
        assert c1.b == "bar"
        assert c2.a == "foo"

    wait()


def test_when_private():
    r1 = Region("Bank1")
    r2 = Region("Bank2")

    try:
        # when r1
        @when(r1)
        def _():
            r1.nested_bank = r2
    except RegionIsolationError:
        # private region needs with
        pass
    else:
        raise AssertionError


def test_nested():
    r1 = Region("Bank1")
    r2 = Region("Bank2")
    r3 = Region("Bank3")

    with r1:
        r1.nested_bank = r2

    r1.make_shareable()

    # when r1:
    @when(r1)
    def _():
        r1.other_nested_bank = r3  # ok — r3 is free, r1 acquired
        try:
            r2.field = MockObject()
        except RegionIsolationError:
            # not ok — r2 neither free nor acquired
            pass
        else:
            raise AssertionError

    wait()
