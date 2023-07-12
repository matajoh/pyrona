"""Region tests."""

import pyrona as pr


class TestObject:
    """Basic object used for testing."""
    pass


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


def test_region_ownership():
    r1 = pr.Region("r1")
    r2 = pr.Region("r2")
    r3 = pr.Region("r3")
    with r1, r2:
        r1.f = r3    # OK, r3 becomes owned by r1
        r2.f = r3    # Throws exception since r3 is already owned by r1
