"""Region tests."""

import json

import pyrona as pr


class TestObject:
    """Basic object used for testing."""
    def __str__(self) -> str:
        """Produces a simple representation of the object graph."""
        return json.dumps(self.__dict__)


def test_creation():
    r = pr.Region()   # closed, free and private
    o = TestObject()   # free
    with r:        # open r
        r.f = o      # o becomes owned by r
        assert pr.region(o) == r


def test_shareable():
    r = pr.Region()
    r.make_shareable()
    assert r.is_shared


def test_ownership():
    r1 = pr.Region("r1")
    r2 = pr.Region("r2")
    r3 = pr.Region("r3")
    with r1, r2:
        r1.f = r3    # OK, r3 becomes owned by r1
        try:
            r2.f = r3    # Throws exception since r3 is already owned by r1
        except pr.RegionIsolationError:
            pass
        else:
            raise AssertionError


def test_ownership_with_merging():
    r1 = pr.Region()
    r2 = pr.Region()
    with r1, r2:
        o1 = TestObject()      # free object
        o2 = TestObject()      # free object
        o1.f = o2              # o1 and o2 are in the same implicit region
        r1.f = o1              # o1 becomes owned by r1, as does o2
        try:
            r2.f = o2          # Throws an exception as o2 is in r1
        except pr.RegionIsolationError:
            pass
        else:
            raise AssertionError


def test_merge():
    r1 = pr.Region()
    r2 = pr.Region()
    with r1:
        r1.o1 = TestObject()
        r1.o1.field = "r1"
        with r2:
            r2.o2 = TestObject()
            r2.o2.field = "r2"

        r1.merge(r2)
        print(r1.o2)

        with r2:
            try:
                print(r2.o2)
            except AttributeError:
                pass
            else:
                raise AssertionError


def test_nesting():
    r1 = pr.Region()
    r2 = pr.Region()
    with r1:
        r1.field = 1
        with r2:
            r2.field = 2

    assert pr.region(r2) == r1

    with r1:
        with r2:
            print(r2.field)
