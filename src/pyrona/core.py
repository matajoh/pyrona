"""Module providing the Region object."""

from collections import namedtuple
from functools import partial
import inspect
import random
import string
from threading import get_ident, Lock
from typing import Any, List, Mapping, NamedTuple, Set, Union
import uuid


def _random_word(length: int, letters=string.ascii_lowercase) -> str:
    return "".join(random.choices(letters, k=length))


def _is_private(name: str) -> bool:
    return name.startswith("_")


class RegionIsolationError(Exception):
    """Error raised for issues related to region isolation."""
    pass


class FreezeException(Exception):
    """Error raised for issues related to region isolation."""
    pass


def _get_attr_as_item(self, name):
    return getattr(self, self.prefix + name)


class Freezer:
    """Class providing methods for freezing objects."""

    @staticmethod
    def freeze_object(obj: object) -> NamedTuple:
        """Freezes an object."""
        members = [(name, value) for name, value in inspect.getmembers(obj)
                   if not _is_private(name)]
        methods = [(name, value) for name, value in members if inspect.ismethod(value)]
        data = [(name, value) for name, value in members if not inspect.ismethod(value)]
        names = [name for name, _ in data]
        frozen_name = "FrozenRegion" if isinstance(obj, Region.Root) else "Frozen" + obj.__class__.__name__
        frozen_type = namedtuple(frozen_name, names)
        for name, value in methods:
            setattr(frozen_type, name, partial(value))

        args = [Freezer.freeze_value(value) for _, value in data]
        return frozen_type(*args)

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
        values = [d[name] for name in names]
        prefix = _random_word(4)
        names = [prefix + n for n in names]
        names.append("prefix")
        values.append(prefix)
        frozen_type = namedtuple("FrozenDict", names)
        frozen_type.__getitem__ = _get_attr_as_item
        return frozen_type(*values)

    @staticmethod
    def freeze_tuple(t: tuple) -> tuple:
        """Freezes all the values in a tuple."""
        return tuple([Freezer.freeze_value(x) for x in t])

    @staticmethod
    def freeze_value(value):
        """Freezes a value, using an appropriate methodology."""
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


def isolated(func):
    """Decorator for isolated class methods."""
    def _isolated(self, *args, **kwargs):
        if region(self).is_closed:
            raise RegionIsolationError("Region is closed")

        return func(self, *args, **kwargs)

    return _isolated


def proxy(func):
    """Decorator for methods which proxy to the inner class."""
    def _proxy(self, *args, **kwargs):
        if region(self).is_closed:
            raise RegionIsolationError("Region is closed")

        inner_func = getattr(self.__inner__, func.__name__)
        return inner_func(*args, **kwargs)

    return _proxy


class RegionIsolatedObject:
    """An object in an explicitly created region."""

    def __init__(self, r: "Region", obj: Any):
        """Constructor."""
        object.__setattr__(self, "__region__", identity(r))
        object.__setattr__(self, "__inner__", obj)
        r._capture(obj, False)

    def can_assign(self, r: "Region") -> bool:
        """Determines whether this region can be assigned to this object."""
        return (r.is_shared or
                region(self) == r or
                region(self).owns(r) or
                (r.is_free and root_region(self) != r))

    def move(self, r: "Region") -> "RegionIsolatedObject":
        """Move this object to a new region."""
        object.__setattr__(self, "__region__", identity(r))
        r._capture(self.__inner__, True)
        return self

    @isolated
    def __setattr__(self, name: str, value: Any):
        """Sets an attribute of the inner object.

        This method will raise a RegionIsolationError if its region is
        not open, or if the value being assigned belongs to a different
        region.
        """
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

    @isolated
    def __getattr__(self, name: str):
        """Gets an attribute of the inner object.

        This method will raise a RegionIsolationError if its region is
        not open.
        """
        if hasattr(self.__inner__, "__getattr__"):
            value = self.__inner__.__getattr__(name)
        else:
            value = getattr(self.__inner__, name)

        if is_imm(value) or isinstance(value, (Region, RegionIsolatedObject)) or inspect.ismethod(value):
            return value

        value = RegionIsolatedObject(region(self), value)
        try:
            self.__inner__.__setattr__(name, value)
        except Exception:
            pass

        return value

    @proxy
    def __str__(self):
        """Proxy."""

    @proxy
    def __call__(self, *args, **kwargs):
        """Proxy."""

    # comparison proxies
    @proxy
    def __hash__(self):
        """Proxy."""

    @proxy
    def __lt__(self, other):
        """Proxy."""

    @proxy
    def __le__(self, other):
        """Proxy."""

    @proxy
    def __eq__(self, other):
        """Proxy."""

    @proxy
    def __ne__(self, other):
        """Proxy."""

    @proxy
    def __gt__(self, other):
        """Proxy."""

    @proxy
    def __ge__(self, other):
        """Proxy."""

    # container-like proxies
    @proxy
    def __getitem__(self, key):
        """Proxy."""

    @proxy
    def __len__(self):
        """Proxy."""

    @proxy
    def __setitem__(self, key, value):
        """Proxy."""

    @proxy
    def __delitem__(self, key):
        """Proxy."""

    @proxy
    def __iter__(self):
        """Proxy."""

    @proxy
    def __contains__(self, item):
        """Proxy."""

    # numeric-like proxies
    @proxy
    def __add__(self, other):
        """Proxy."""

    @proxy
    def __sub__(self, other):
        """Proxy."""

    @proxy
    def __mul__(self, other):
        """Proxy."""

    @proxy
    def __matmul__(self, other):
        """Proxy."""

    @proxy
    def __truediv__(self, other):
        """Proxy."""

    @proxy
    def __floordiv__(self, other):
        """Proxy."""

    @proxy
    def __mod__(self, other):
        """Proxy."""

    @proxy
    def __divmod__(self, other):
        """Proxy."""

    @proxy
    def __pow__(self, other, modulo=None):
        """Proxy."""

    @proxy
    def __lshift__(self, other):
        """Proxy."""

    @proxy
    def __rshift__(self, other):
        """Proxy."""

    @proxy
    def __and__(self, other):
        """Proxy."""

    @proxy
    def __xor__(self, other):
        """Proxy."""

    @proxy
    def __or__(self, other):
        """Proxy."""


_regions: Mapping[int, "Region"] = {}

_region_aliases: Mapping[int, int] = {}

_counter = {"value": 0}


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
        object.__setattr__(self, "alias", None)
        object.__setattr__(self, "__identity__", _counter["value"])
        _regions[_counter["value"]] = self
        _counter["value"] += 1

        root = RegionIsolatedObject(self, Region.Root())

        object.__setattr__(self, "is_open_", None)
        object.__setattr__(self, "is_shared_", False)
        object.__setattr__(self, "__region__", None)
        object.__setattr__(self, "root", root)
        object.__setattr__(self, "children", [])

    def _capture(self, obj: Any, overwrite: bool):
        """Captures an object, placing it in the Region."""
        if self.alias:
            self.alias._capture(obj, overwrite)

        if is_imm(obj) or region(obj) == self:
            return

        if region(obj) is not None and not overwrite:
            raise RegionIsolationError("Object is already in another region")

        if isinstance(obj, RegionIsolatedObject):
            obj.move(self)
            return

        if isinstance(obj, (list, tuple, set)):
            for item in obj:
                self._capture(item, overwrite)
        elif isinstance(obj, dict):
            for name in obj:
                self._capture(obj[name], overwrite)
        elif isinstance(obj, Region):
            if obj.is_free:
                self.add_child(obj)
            elif not self.owns(obj):
                raise RegionIsolationError("Region already attached to a different region graph")
        else:
            object.__setattr__(obj, "__region__", identity(self))
            if region(obj) != self:
                # this object cannot be captured, bail for now
                return

            for name in obj.__dict__:
                if not _is_private(name):
                    value = getattr(obj, name)
                    if not inspect.ismethod(value):
                        self._capture(value, overwrite)

    def owns(self, other: "Region") -> bool:
        """Determines whether this region owns the other region."""
        if self.alias:
            self.alias.owns(other)

        return any(other == child or child.owns(other)
                   for child in self.children)

    def add_child(self, other: "Region"):
        """Adds the other region as a child of this region."""
        if self.alias:
            self.alias.add_child(other)

        if not other.is_free:
            raise RegionIsolationError("Region is not free")

        self.children.append(other)
        object.__setattr__(other, "__region__", identity(self))

    def remove_child(self, other: "Region"):
        """Removes the other region."""
        if self.alias:
            self.alias.remove_child(other)

        if region(other) != self:
            raise RegionIsolationError("Region is not a child of this region")

        self.children.remove(other)
        object.__setattr__(other, "__region__", None)

    @property
    def is_shared(self) -> bool:
        """Whether this region is shareable."""
        if self.alias:
            return self.alias.is_shared

        return self.is_shared_

    @property
    def is_private(self) -> bool:
        """Whether this region is private."""
        if self.alias:
            return self.alias.is_private

        return not self.is_shared_

    def _share(self):
        object.__setattr__(self, "is_shared_", True)

    def _unshare(self):
        object.__setattr__(self, "is_shared_", False)

    @property
    def is_open(self) -> bool:
        """Whether this region is currently open."""
        if self.alias:
            return self.alias.is_open

        return get_ident() == self.is_open_

    @property
    def is_closed(self) -> bool:
        """Whether this region is closed."""
        if self.alias:
            return self.alias.is_close

        return get_ident() != self.is_open_

    def _open(self):
        object.__setattr__(self, "is_open_", get_ident())

    def _close(self):
        object.__setattr__(self, "is_open_", None)

    @property
    def is_free(self) -> bool:
        """Whether this is a free region."""
        return region(self) is None

    def make_shareable(self) -> "Region":
        """Makes the region shareable."""
        if self.alias:
            self.alias.make_shareable()

        object.__setattr__(self, "last", None)
        object.__setattr__(self, "lock", Lock())
        object.__setattr__(self, "is_shared_", True)
        return self

    def __repr__(self) -> str:
        """Returns the region representation."""
        return "Region({})".format(self.name)

    def __hash__(self) -> int:
        """Hash function based on the region identity."""
        return identity(self)

    def __eq__(self, other: "Region") -> bool:
        """Equality based upon the region identity."""
        if isinstance(other, Region):
            return identity(self) == identity(other)

        return False

    def _can_open(self) -> bool:
        if self.is_open or self.is_free:
            return True

        return region(self)._can_open()

    def __lt__(self, other: "Region") -> bool:
        """Comparison based upon the region identity."""
        return identity(self) < identity(other)

    def __enter__(self):
        """Enter the region."""
        if self.alias:
            return self.alias.__enter__()

        if self.is_shared:
            raise RegionIsolationError("Region is not private")

        if self._can_open():
            self._open()
        else:
            raise RegionIsolationError("Region cannot be opened")

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Exit the region."""
        if self.alias:
            self.alias.__exit__(exc_type, exc_value, traceback)

        self._close()

    def __setattr__(self, attr_name, value):
        """Set an attribute of the region object."""
        if self.alias:
            self.alias.__setattr__(attr_name, value)

        self.root.__setattr__(attr_name, value)

    def __getattr__(self, attr_name):
        """Get an attribute of the region object."""
        if self.alias:
            return self.alias.__getattr__(attr_name)

        return getattr(self.root, attr_name)

    def merge(self, other: "Region") -> List[Union["Region", RegionIsolatedObject]]:
        """Merge the other region into this one.

        This function will raise an error if this region is not open.
        The end result is that all objects and regions in the other region
        will be in this one, and the other region will be empty.
        """
        if self.alias:
            return self.alias.merge(other)

        if self.is_closed:
            raise RegionIsolationError("Region is not open")

        if not self.is_free:
            raise RegionIsolationError("Region is not free")

        _region_aliases[identity(other)] = identity(self)
        merged = other.root.move(self)
        setattr(self.root, _random_word(8), merged)
        object.__setattr__(other, "alias", self)
        return merged

    def freeze(self) -> NamedTuple:
        """Freezes the data within an object.

        This operation returns an immutable object containing the data
        and methods of the objects stored in the region. It leaves the
        region empty and free.
        """
        if self.is_open:
            raise FreezeException("Region must be closed")

        frozen = Freezer.freeze_object(self.root.__inner__)
        object.__setattr__(self, "root", RegionIsolatedObject(self, Region.Root()))
        object.__setattr__(self, "__region__", None)
        return frozen

    def detach_all(self, name: str = None) -> "Region":
        """Detaches all objects from this region.

        The objects are returned as a new private Region, and this region
        is emptied out.
        """
        if self.is_closed:
            raise RegionIsolationError("Region must be open")

        if self.is_private:
            raise RegionIsolationError("Region must be shared")

        r = Region(name)
        root = self.root.move(r)
        object.__setattr__(r, "root", root)
        object.__setattr__(self, "root", RegionIsolatedObject(self, Region.Root()))
        return r


def identity(r: Region) -> int:
    """Returns the identity for an object."""
    if isinstance(r, Region):
        return r.__identity__

    raise TypeError


def region(x: Any) -> Region:
    """Returns the region for an object."""
    identity = getattr(x, "__region__", None)
    if identity is None:
        return None

    if identity in _region_aliases:
        parent = _region_aliases[identity]
        if parent in _region_aliases:
            _region_aliases[identity] = _region_aliases[parent]

    while identity in _region_aliases:
        identity = _region_aliases[identity]

    return _regions.get(identity, None)


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
