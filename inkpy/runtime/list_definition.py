import typing as t

from collections import UserDict

from .ink_list import InkListItem


class ListDefinition(UserDict[str, int]):
    def __init__(
        self, name: t.Optional[str] = None, items: t.Optional[dict[str, int]] = None
    ):
        self.name = name
        self.items: dict[InkListItem, int] = {}
        super().__init__(items)

    def __contains__(self, item: InkListItem | str):
        if isinstance(item, InkListItem):
            item = item.item_name
        return super().__contains__(item)

    def get(self, item: InkListItem | str, default: int | None = None) -> int | None:
        if isinstance(item, InkListItem):
            item = item.item_name
        return super().get(item, default)
