"""Region tests."""

import json

from pyrona import Region, region, RegionIsolationError


class MockObject:
    """Mock object used for testing."""
    def __str__(self) -> str:
        """Produces a simple representation of the object graph."""
        return json.dumps(self.__dict__)


def test_creation():
    r = Region()   # closed, free and private
    o = MockObject()  # free

    with r:
        r.f = o       # o becomes owned by r

    assert region(o) == r


def test_ownership():
    r1 = Region("Bank1")
    r2 = Region("Bank2")
    with r1, r2:
        r1.accounts = {"Alice": 1000}
        try:
            r2.accounts = r1.accounts
        except RegionIsolationError:
            # ownership exception
            pass
        else:
            raise AssertionError


def test_isolation():
    r1 = Region("Bank1")
    x = None
    with r1:
        r1.accounts = {"Alice": 1000}
        x = r1.accounts

    try:
        print(x["Alice"].balance)
    except RegionIsolationError:
        # the region not open
        pass
    else:
        raise AssertionError


def test_with_shared():
    r1 = Region("Bank1").make_shareable()
    try:
        with r1:
            r1.accounts = {"Alice": 1000}
    except RegionIsolationError:
        # shared region needs when
        pass
    else:
        raise AssertionError


def test_region_ownership():
    r1 = Region("r1")
    r2 = Region("r2")
    r3 = Region("r3")

    with r1, r2:
        r1.f = r3        # OK, r3 becomes owned by r1
        try:
            r2.f = r3    # Throws exception since r3 is already owned by r1
        except RegionIsolationError:
            pass
        else:
            raise AssertionError


def test_ownership_with_merging():
    r1 = Region()
    r2 = Region()

    with r1, r2:
        o1 = MockObject()      # free object
        o2 = MockObject()      # free object
        o1.f = o2              # o1 and o2 are in the same implicit region
        r1.f = o1              # o1 becomes owned by r1, as does o2
        try:
            r2.f = o2          # Throws an exception as o2 is in r1
        except RegionIsolationError:
            pass
        else:
            raise AssertionError


def test_merge():
    r1 = Region()
    r2 = Region()

    with r1:
        r1.o1 = MockObject()
        r1.o1.field = "r1"

        with r2:
            r2.o2 = MockObject()
            r2.o2.field = "r2"

        merged = r1.merge(r2)            # merge the two regions
        r1.o2 = merged.o2                # create edges
        print(r1.o2)                     # verify it exists
        assert region(r2.o2) == r1       # validate r2 is an alias for r1
