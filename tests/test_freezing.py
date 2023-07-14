"""Tests for the freezing functionality."""

import pyrona as pr


class MockObject:
    """Mock object for testing purposes."""
    def __init__(self, name: str):
        """Constructor."""
        self.name_ = name

    @property
    def name(self) -> str:
        """Property exposing the name of the object."""
        return self.name_

    @name.setter
    def name(self, value: str):
        self.name_ = value

    def secret(self):
        """Returns the name in reverse."""
        return "".join(reversed(self.name))


def test_freezing():
    r2 = pr.Region()
    r3 = pr.Region()
    with r2:
        r2.field = [47, r3]
        with r3:
            r3.field = 11

    x = r2.freeze()
    assert pr.is_imm(x)
    assert r2.is_free
    assert r3.is_free

    with r2:
        try:
            print(r2.field)
        except AttributeError:
            pass
        else:
            raise AssertionError

    with r3:
        try:
            print(r3.field)
        except AttributeError:
            pass
        else:
            raise AssertionError

    print(x)


def test_frozen_list():
    r = pr.Region()
    with r:
        r.a = [0, "two", None, True]

    x = r.freeze()
    assert isinstance(x.a, tuple)
    assert x.a[0] == 0
    assert x.a[1] == "two"
    assert x.a[2] is None
    assert x.a[3]


def test_frozen_dict():
    r = pr.Region()
    with r:
        r.a = {
            "one": 1,
            "two": False,
            "three": None,
            "four": "four",
        }

    x = r.freeze()
    assert isinstance(x.a, tuple)
    assert x.a["one"] == 1
    assert not x.a["two"]
    assert x.a["three"] is None
    assert x.a["four"] == "four"


def test_frozen_set():
    r = pr.Region()
    with r:
        r.a = set([0, 1, 2, 2, 3, 3, 3])

    x = r.freeze()
    assert isinstance(x.a, frozenset)
    assert len(x.a) == 4
    assert 0 in x.a and 1 in x.a and 2 in x.a and 3 in x.a


def test_frozen_tuple():
    r = pr.Region()
    with r:
        r.a = tuple([0, "two", None, True])

    x = r.freeze()
    assert isinstance(x.a, tuple)
    assert x.a[0] == 0
    assert x.a[1] == "two"
    assert x.a[2] is None
    assert x.a[3]


def test_frozen_object():
    a = MockObject("abcd")
    b = MockObject("efgh")
    a.c = [0, b, (2, b), {"3": b}]
    a.d = tuple(a.c)
    a.e = set(a.c[:3])
    r = pr.Region()
    with r:
        r.a = a
        r.a.b = b

    x = r.freeze()
    assert isinstance(x.a, tuple)
    assert x.a.c[0] == 0
    assert x.a.c[1].name == "efgh"
    assert x.a.c[2][0] == 2
    assert x.a.c[3]["3"].secret() == "hgfe"
    assert isinstance(x.a.d, tuple)
    assert isinstance(x.a.e, frozenset)
    try:
        x.a.name = "foo"
    except AttributeError:
        pass
    else:
        raise AssertionError
