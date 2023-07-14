"""Tests for the object wrapping."""

from typing import Callable

import pyrona as pr


def test_container():
    r = pr.Region()
    with r:
        r.a = [0, 1, 2, 3]
        print(len(r.a))
        print(r.a[0])
        r.a[0] = len(r.a)
        r.a[-1] = 0
        print(r.a[0])
        del r.a[1]
        print(r.a)


class MockNumeric:
    """Mock class for testing numeric proxying."""
    def __init__(self, *values: int):
        """Constructor."""
        self._values = tuple(values)

    def __str__(self):
        """Returns the values as a tuple string."""
        return str(self._values)

    def __len__(self) -> int:
        """Number of values."""
        return len(self._values)

    def __eq__(self, other: "MockNumeric") -> bool:
        """Tuple equality."""
        return self._values == other._values

    def __hash__(self) -> int:
        """Tuple hash."""
        return hash(self._values)

    def _do_op(self, other: "MockNumeric", op: Callable[[int, int], int]):
        assert len(self) == len(other)
        values = tuple([op(x, y) for x, y in zip(self._values, other._values)])
        return MockNumeric(values)

    def __add__(self, other: "MockNumeric"):
        """Adds two tuples."""
        return self._do_op(other, lambda x, y: x + y)

    def __sub__(self, other: "MockNumeric"):
        """Subtracts two tuples."""
        return self._do_op(other, lambda x, y: x + y)


def test_maths():
    r = pr.Region()
    a = MockNumeric(0, 1, 2)
    b = MockNumeric(3, 4, 5)
    e_add = a + b
    e_sub = a - b
    with r:
        r.a = a
        r.b = b
        assert hash(r.a) == hash(a)
        assert len(r.a) == len(a)
        assert r.a == a
        assert r.a + r.b == e_add
        assert r.a - r.b == e_sub
        x = r.a

    try:
        print(x + a)
    except pr.RegionIsolationError:
        pass
    else:
        raise AssertionError
