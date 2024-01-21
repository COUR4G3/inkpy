import sys
import typing as t

from collections import UserDict


if t.TYPE_CHECKING:
    from .list_definition import ListDefinition


class InkListItem:
    origin_name: t.Optional[str] = None
    item_name: t.Optional[str] = None

    def __init__(self, name: str, item_name: t.Optional[str] = None):
        if item_name:
            self.origin_name = name
            self.item_name = item_name
        else:
            self.origin_name, self.item_name = name.split(".")

    def __bool__(self):
        return self.origin_name or self.item_name

    def __eq__(self, other):
        if isinstance(other, InkListItem):
            return (
                self.item_name == other.item_name
                and self.origin_name == other.origin_name
            )

        return False

    def __hash__(self) -> int:
        return hash((self.origin_name, self.item_name))

    def __repr__(self):
        return f"<InkListItem: {self.full_name}>"

    def __str__(self):
        return self.full_name

    def copy(self) -> "InkListItem":
        return InkListItem(self.origin_name, self.item_name)

    @property
    def full_name(self):
        return f"{self.origin_name or '?'}.{self.item_name}"


class InkList(UserDict[InkListItem, int]):
    def __init__(self, other: t.Optional["InkList"] = None):
        if other:
            self.origin_names = other.origin_names.copy()
            self.origins = other.origins.copy()
        else:
            self.origin_names: list[str] = []
            self.origins: list["ListDefinition"] = []

        super().__init__(other)

    def __contains__(self, item: InkListItem | str):
        if isinstance(item, str):
            return any(i.item_name == item for i in self.keys())
        return super().__contains__(item)

    def __eq__(self, other):
        if not isinstance(other, InkList):
            return False
        if not other:
            return False

        for key in other.keys():
            if key not in other:
                return False

        return True

    def __setitem__(self, key: InkListItem, item: int):
        if key in self:
            raise Exception(f"The list already contains an entry for '{key:!r}'")

        super().__setitem__(key, item)

    def __str__(self):
        return ", ".join(item.name for item, _ in self.ordered())

    def add_item(self, item_or_name: InkListItem | str):
        if isinstance(item_or_name, InkListItem):
            item = item_or_name
            if not item.origin_name:
                self.add_item(item.item_name)
                return

            for origin in self.origins:
                if origin.name == item.origin_name:
                    value = origin.get(item, None)
                    if value is None:
                        raise Exception(
                            f"Could not add item '{item:!r}' to this list because it "
                            "doesn't exist in the original list definition in ink."
                        )
                    self[item] = value
            else:
                raise Exception(
                    "Failed to add item to list because the item was from a new list "
                    "definition that wasn't previously known to this list. Only items "
                    "from previously known lists can be used, so that the int value "
                    "can be found"
                )

        else:
            item_name = item_or_name

            found_list_def = None

            for origin in self.origins:
                if item_name in origin:
                    if found_list_def:
                        raise Exception(
                            f"Could not add the item '{item_name}' to the list because "
                            f"it could from either '{origin.name}' or "
                            f"'{found_list_def.name}'"
                        )
                    else:
                        found_list_def = origin

            if not found_list_def:
                raise Exception(
                    f"Could not add the item '{item_name}' to this list because it is "
                    "isn't known to any list definitions previously associated with "
                    "this list."
                )

            item = InkListItem(found_list_def.name, item_name)
            item_value = found_list_def.get(item)
            self[item] = item_value

    def all(self) -> "InkList":
        list = InkList()

        for origin in self.origins:
            for item, value in origin.items():
                list[item] = value

        return list

    def has_intersection(self, other: "InkList") -> bool:
        for key, value in self.items():
            if key in other:
                return True
        return False

    def intersect(self, other: "InkList") -> "InkList":
        intersection = InkList()

        for key, value in self.items():
            if key in other:
                intersection[key] = value

        return intersection

    def inverse(self) -> "InkList":
        list = InkList()

        for origin in self.origins:
            for item, value in origin.items():
                if item not in self:
                    list[item] = value

        return list

    def list_with_subrange(
        self,
        min_bound: t.Type["InkList"] | int = 0,
        max_bound: t.Type["InkList"] | int = sys.maxsize,
    ) -> "InkList":
        ordered = self.ordered()

        if isinstance(min_bound, InkList):
            min_bound = min_bound and min_bound.min[1] or 0

        if isinstance(max_bound, InkList):
            max_bound = max_bound and max_bound.max[1] or sys.maxsize

        sublist = InkList()
        sublist.set_initial_origin_names(self.origin_names)
        for key, value in ordered:
            if value >= min_bound and value <= max_bound:
                sublist[key] = value

        return sublist

    @property
    def max(self) -> tuple[InkListItem, int]:
        max = None

        for key, value in self.items():
            if not max or value > max[1]:
                max = (key, value)

        return max

    def max_as_list(self) -> "InkList":
        list = InkList()
        if len(self) > 0:
            key, value = self.max
            list[key] = value
        return list

    @property
    def min(self) -> tuple[InkListItem, int]:
        min = None

        for key, value in self.items():
            if not min or value < min[1]:
                min = (key, value)

        return min

    def min_as_list(self) -> "InkList":
        list = InkList()
        if len(self) > 0:
            key, value = self.min
            list[key] = value
        return list

    def ordered(self) -> list[tuple[InkListItem, int]]:
        ordered = []

        for key, value in self.items():
            ordered.append((key, value))

        ordered.sort(key=lambda item: (item[0].origin_name, item[1]))

        return ordered

    @property
    def origin_of_max_item(self) -> t.Optional["ListDefinition"]:
        max_origin_name = self.max[0].origin_name
        for origin in self.origins:
            if origin.name == max_origin_name:
                return origin

    def set_initial_origin_name(self, origin_name: str):
        self.origin_names = [origin_name]

    def set_initial_origin_names(self, origin_names: list[str]):
        self.origin_names = origin_names.copy()

    def union(self, other: "InkList") -> "InkList":
        union = InkList(self)

        for key, value in other.items():
            union[key] = value

        return union

    def without(self, other: "InkList") -> "InkList":
        without = InkList(self)

        for key, value in other.items():
            del without[key]

        return without
