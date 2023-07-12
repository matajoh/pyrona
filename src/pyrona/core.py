"""Module providing the Region object."""

from typing import Any, Set
import uuid


class RegionIsolationError(Exception):
    """Error raised for issues related to region isolation."""
    pass


class RegionIsolatedObject:
    """An object in an explicitly created region."""

    def __init__(self, region: "Region", obj: Any):
        """Constructor."""
        object.__setattr__(self, "__region__", region)
        object.__setattr__(self, "__inner__", obj)
        obj.__setattr__("__region__", region)

    def can_assign(self, r: "Region") -> bool:
        """Determines whether this region can be assigned to this object."""
        return (r.is_shared or
                region(self) == r or
                region(self).owns(r) or
                (r.is_free and root_region(self) != r))

    def __setattr__(self, name: str, value: Any):
        """Sets an attribute of the inner object.

        This method will raise a RegionIsolationError if its region is
        not open, or if the value being assigned belongs to a different
        region.
        """
        if not self.__region__.is_open:
            raise RegionIsolationError("Region is not open")

        if isinstance(value, Region):
            if self.can_assign(value):
                self.__region__.add_child(value)
            else:
                raise RegionIsolationError("Invalid region assignment")
        else:
            rset = regions(self, value).union([None, self.__region__])
            if len(rset) > 2:
                raise RegionIsolationError("Invalid assignment")

            if not is_imm(value) and not isinstance(value, RegionIsolatedObject):
                value = RegionIsolatedObject(self.__region__, value)

        self.__inner__.__setattr__(name, value)

    def __getattr__(self, name: str):
        """Gets an attribute of the inner object.

        This method will raise a RegionIsolationError if its region is
        not open.
        """
        if not self.__region__.is_open:
            raise RegionIsolationError("Region is not open")

        value = getattr(self.__inner__, name)
        if is_imm(value) or isinstance(value, RegionIsolatedObject):
            return value

        return RegionIsolatedObject(self.__region__, value)


class Region:
    """An object that reifies a region and permits manipulations of the entire region."""

    class Root:
        """Object used as the root of the Region object graph."""
        pass

    def __init__(self, name: str = None):
        """Constructor."""
        if name is None:
            name = uuid.uuid4()

        root = RegionIsolatedObject(self, Region.Root())

        object.__setattr__(self, "name", name)
        object.__setattr__(self, "is_open", False)
        object.__setattr__(self, "is_shared_", False)
        object.__setattr__(self, "__region__", None)
        object.__setattr__(self, "root", root)
        object.__setattr__(self, "children", [])

    def owns(self, other: "Region") -> bool:
        """Determines whether this region owns the other region."""
        return any(other == child or child.owns(other)
                   for child in self.children)

    def add_child(self, other: "Region"):
        """Adds the other region as a child of this region."""
        if not other.is_free:
            raise RegionIsolationError("Region is not free")

        self.children.append(other)

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
        object.__setattr__(self, "is_open", True)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Exit the region."""
        object.__setattr__(self, "is_open", False)

    def __setattr__(self, attr_name, value):
        """Set an attribute of the region object."""
        self.root.__setattr__(attr_name, value)

    def __getattr__(self, attr_name):
        """Get an attribute of the region object."""
        return getattr(self.root, attr_name)


def region(x: Any) -> Region:
    """Returns the region for an object."""
    return getattr(x, "__region__", None)


def regions(*args) -> Set[Region]:
    """Returns the set of regions which contain the arguments."""
    return set([region(a) for a in args])


ImmutableBuiltins = set([
    None,
    bool,
    int,
    float,
    complex,
    str,
    bytes,
])


ImmutableSequences = set([
    frozenset,
    tuple,
])


def is_namedtuple_instance(x: Any) -> bool:
    """Returns whether x is a likely result of calling namedtuple."""
    t = type(x)
    b = t.__bases__
    if len(b) != 1 or b[0] != tuple:
        return False

    f = getattr(t, "_fields", None)
    if not isinstance(f, tuple):
        return False

    return all(type(n) == str for n in f)


def is_imm(x: Any) -> bool:
    """Returns whether x is an immutable object."""
    if type(x) in ImmutableBuiltins:
        return True

    if type(x) in ImmutableSequences or is_namedtuple_instance(x):
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
