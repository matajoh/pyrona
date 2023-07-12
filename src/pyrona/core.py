"""Module providing the Region object."""

from collections import namedtuple
from functools import partial
import inspect
from typing import Any, List, Mapping, NamedTuple, Set, Union
import uuid


class RegionIsolationError(Exception):
    """Error raised for issues related to region isolation."""
    pass


class FreezeException(Exception):
    """Error raised for issues related to region isolation."""
    pass


def _get_attr_as_item(self, name):
    return getattr(self, name)


class Freezer:
    """Class providing methods for freezing objects."""

    @staticmethod
    def freeze_object(obj: object) -> NamedTuple:
        """Freezes an object."""
        members = [(name, value) for name, value in inspect.getmembers(obj)
                   if not name.startswith("__")]
        methods = [(name, value) for name, value in members if inspect.ismethod(value)]
        data = [(name, value) for name, value in members if not inspect.ismethod(value)]
        names = [name for name, _ in data]
        frozen_name = "FrozenRegion" if isinstance(obj, Region.Root) else "Frozen" + obj.__class__.__name__
        frozentype = namedtuple(frozen_name, names)
        for name, value in methods:
            setattr(frozentype, name, partial(value))

        args = [Freezer.freeze_value(value) for _, value in data]
        return frozentype(*args)

    @staticmethod
    def freeze_list(lst: list) -> tuple:
        """Freezes all of the values in a list."""
        return tuple([Freezer.freeze_value(x) for x in lst])

    @staticmethod
    def freeze_set(s: set) -> frozenset:
        """Freezes all of the values in a set."""
        return frozenset([Freezer.freeze_value(x) for x in s])

    @staticmethod
    def freeze_dict(d: dict) -> NamedTuple:
        """Freezes all the values in a dictionary."""
        names = list(d.keys())
        frozentype = namedtuple("FrozenDict", names)
        frozentype.__getitem__ = _get_attr_as_item
        return frozentype(*[d[name] for name in names])

    @staticmethod
    def freeze_tuple(t: tuple) -> tuple:
        """Freezes all the values in a tuple."""
        return tuple([Freezer.freeze_value(x) for x in t])

    @staticmethod
    def freeze_value(value):
        """Freezes a value, using an appropriate methodoloogy."""
        if isinstance(value, RegionIsolatedObject):
            value = value.__inner__

        if is_imm(value):
            return value

        if isinstance(value, list):
            return Freezer.freeze_list(value)

        if isinstance(value, bytearray):
            return bytes(value)

        if isinstance(value, set):
            return Freezer.freeze_set(value)

        if isinstance(value, dict):
            return Freezer.freeze_dict(value)

        if isinstance(value, tuple):
            return Freezer.freeze_tuple(value)

        if isinstance(value, Region):
            return value.freeze()

        return Freezer.freeze_object(value)


class RegionIsolatedObject:
    """An object in an explicitly created region."""

    def __init__(self, r: "Region", obj: Any):
        """Constructor."""
        object.__setattr__(self, "__region__", r.name)
        object.__setattr__(self, "__inner__", obj)
        r.capture(obj)

    def can_assign(self, r: "Region") -> bool:
        """Determines whether this region can be assigned to this object."""
        return (r.is_shared or
                region(self) == r or
                region(self).owns(r) or
                (r.is_free and root_region(self) != r))

    def move(self, r: "Region"):
        """Move this object to a new region."""
        object.__setattr__(self, "__region__", r.name)
        r.capture(self.__inner__)

    def __str__(self):
        """Proxy."""
        assert region(self).is_open
        return self.__inner__.__str__()

    def __setattr__(self, name: str, value: Any):
        """Sets an attribute of the inner object.

        This method will raise a RegionIsolationError if its region is
        not open, or if the value being assigned belongs to a different
        region.
        """
        if not region(self).is_open:
            raise RegionIsolationError("Region is not open")

        if isinstance(value, Region):
            if self.can_assign(value):
                region(self).add_child(value)
            else:
                raise RegionIsolationError("Invalid region assignment")
        else:
            rset = regions(self, value).union([None, region(self)])
            if len(rset) > 2:
                raise RegionIsolationError("Invalid assignment")

            if not is_imm(value) and not isinstance(value, RegionIsolatedObject):
                value = RegionIsolatedObject(region(self), value)

        self.__inner__.__setattr__(name, value)

    def __getattr__(self, name: str):
        """Gets an attribute of the inner object.

        This method will raise a RegionIsolationError if its region is
        not open.
        """
        if not region(self).is_open:
            raise RegionIsolationError("Region is not open")

        value = getattr(self.__inner__, name)
        if is_imm(value) or isinstance(value, (Region, RegionIsolatedObject)):
            return value

        return RegionIsolatedObject(region(self), value)


_regions: Mapping[str, "Region"] = {}
_stack: List[str] = []


class Region:
    """An object that reifies a region and permits manipulations of the entire region."""

    class Root:
        """Object used as the root of the Region object graph."""
        pass

    def __init__(self, name: str = None):
        """Constructor."""
        if name is None:
            name = str(uuid.uuid4())

        if name in _regions:
            raise AttributeError("Region name must be unique ({} already exists)".format(name))

        object.__setattr__(self, "name", name)
        _regions[self.name] = self

        root = RegionIsolatedObject(self, Region.Root())

        object.__setattr__(self, "is_open", False)
        object.__setattr__(self, "is_shared_", False)
        object.__setattr__(self, "__region__", None)
        object.__setattr__(self, "root", root)
        object.__setattr__(self, "children", [])

    def capture(self, obj: Any):
        """Captures an object, placing it in the Region."""
        if is_imm(obj):
            return

        if isinstance(obj, RegionIsolatedObject):
            obj.move(self)
            return

        if isinstance(obj, (list, tuple)):
            for item in obj:
                self.capture(item)
        elif isinstance(obj, dict):
            for name in obj:
                self.capture(obj[name])
        elif isinstance(obj, Region):
            if obj.is_free:
                self.add_child(obj)
            elif not self.owns(obj):
                raise RegionIsolationError("Region already attached to a different region graph")
        else:
            object.__setattr__(obj, "__region__", self.name)
            for name in dir(obj):
                if not name.startswith("__"):
                    self.capture(getattr(obj, name))

    def owns(self, other: "Region") -> bool:
        """Determines whether this region owns the other region."""
        return any(other == child or child.owns(other)
                   for child in self.children)

    def add_child(self, other: "Region"):
        """Adds the other region as a child of this region."""
        if not other.is_free:
            raise RegionIsolationError("Region is not free")

        self.children.append(other)
        object.__setattr__(other, "__region__", self.name)

    def remove_child(self, other: "Region"):
        """Removes the other region."""
        if region(other) != self:
            raise RegionIsolationError("Region is not a child of this region")

        self.children.remove(other)
        object.__setattr__(other, "__region__", None)

    @property
    def is_shared(self) -> bool:
        """Whether this region is shareable."""
        return self.is_shared_

    @property
    def is_free(self) -> bool:
        """Whether this is a free region."""
        return region(self) is None

    def make_shareable(self):
        """Makes the region shareable."""
        object.__setattr__(self, "is_shared_", True)

    def __hash__(self) -> int:
        """Hash function based on the region name."""
        return hash(self.name)

    def __eq__(self, other: "Region") -> bool:
        """Equality based upon the region name."""
        if isinstance(other, Region):
            return self.name == other.name

        return False

    def __enter__(self):
        """Enter the region."""
        if len(_stack) > 0:
            if self.is_free:
                _regions[_stack[-1]].add_child(self)
            elif _stack[-1] != self.__region__:
                raise RegionIsolationError("Invalid nesting: region already has a parent")

        _stack.append(self.name)
        object.__setattr__(self, "is_open", True)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Exit the region."""
        _stack.pop()
        object.__setattr__(self, "is_open", False)

    def __setattr__(self, attr_name, value):
        """Set an attribute of the region object."""
        self.root.__setattr__(attr_name, value)

    def __getattr__(self, attr_name):
        """Get an attribute of the region object."""
        return getattr(self.root, attr_name)

    def merge(self, other: "Region") -> List[Union["Region", RegionIsolatedObject]]:
        """Merge the other region into this one.

        This function will raise an error if this region is not open.
        The end result is that all objects and regions in the other region
        will be in this one, and the other region will be empty.
        """
        if not self.is_open:
            raise RegionIsolationError("Region is not open")

        merged = []
        for name in dir(other.root.__inner__):
            if name.startswith("__") and name.endswith("__"):
                continue

            value = getattr(other.__inner__, name)
            if isinstance(value, RegionIsolatedObject):
                value.move(self)
                merged.append(value)
                object.__setattr__(self.root, name, value)
            elif isinstance(value, Region):
                other.remove_child(value)
                self.add_child(value)
                merged.append(value)
                object.__setattr__(self.root, name, value)

        object.__setattr__(other, "root", RegionIsolatedObject(other, Region.Root()))
        return merged

    def freeze(self) -> NamedTuple:
        """Freezes the data within an object, making it immutable and making the region empty and free."""
        if self.is_open:
            raise FreezeException("Region must be closed")

        frozen = Freezer.freeze_object(self.root.__inner__)
        object.__setattr__(self, "root", RegionIsolatedObject(self, Region.Root()))
        object.__setattr__(self, "__region__", None)
        return frozen


def region(x: Any) -> Region:
    """Returns the region for an object."""
    return _regions.get(getattr(x, "__region__", None), None)


def regions(*args) -> Set[Region]:
    """Returns the set of regions which contain the arguments."""
    return set([region(a) for a in args])


ImmutableBuiltins = (
    type(None),
    bool,
    int,
    float,
    complex,
    str,
    bytes,
    range,
)


ImmutableSequences = (
    frozenset,
    tuple,
)


def is_imm(x: Any) -> bool:
    """Returns whether x is an immutable object."""
    if isinstance(x, ImmutableBuiltins):
        return True

    if isinstance(x, ImmutableSequences):
        return all(is_imm(y) for y in x)

    return False


def root_region(x: Any) -> Region:
    """Returns the root of the region graph that contains x."""
    r = region(x)
    if r is None:
        return None

    while not r.is_free:
        r = region(r)

    return r
