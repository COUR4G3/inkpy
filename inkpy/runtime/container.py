import typing as t

from enum import IntEnum

from .object import InkObject
from .path import Path
from .search_result import SearchResult


class Container(InkObject):
    class CountFlags(IntEnum):
        Visits = 1
        Turns = 2
        CountStartOnly = 4

    def __init__(self, name: t.Optional[str] = None):
        self.name = name

        self._content: list[InkObject] = []
        self.named_content: dict[str, InkObject] = {}

        self.visits_should_be_counted: bool = False
        self.turn_index_should_be_counted: bool = False
        self.count_at_start_only: bool = False

        super().__init__()

    def add_content(self, value: list[InkObject] | InkObject):
        if isinstance(value, list):
            for content in value:
                self.add_content(content)
        else:
            self._content.append(value)

            if value.parent:
                raise RuntimeError(f"Content is already in {value.parent}")

            value.parent = self

            self.try_add_named_content(value)

    def add_to_named_content_only(self, content: InkObject):
        self.named_content[content.name] = content

    @property
    def content(self) -> list[InkObject]:
        return self._content

    @content.setter
    def content(self, value: list[InkObject]):
        self.add_content(value)

    def content_at_path(
        self, path: Path, start: int = 0, end: int = -1
    ) -> SearchResult:
        if end == -1:
            end = len(path)

        result = SearchResult(approximate=False)

        current_container = current_object = self
        for component in path.components[start:end]:
            if not current_container:
                result.approximate = True
                break

            object = current_container.content_with_path_component(component)
            if not object:
                result.approximate = True
                break

            current_object = object
            current_container = isinstance(object, Container) and object or None

        result.obj = current_object
        return result

    def content_with_path_component(
        self, component: Path.Component
    ) -> t.Optional[InkObject]:
        if component.is_index:
            if component.index >= 0 and component.index < len(self.content):
                return self.content[component.index]
            else:
                return
        elif component.is_parent:
            return self.parent
        else:
            return self.named_content.get(component.name)

    @property
    def count_flags(self) -> CountFlags:
        flags = 0

        if self.visits_should_be_counted:
            flags |= Container.CountFlags.Visits
        if self.turn_index_should_be_counted:
            flags |= Container.CountFlags.Turns
        if self.count_at_start_only:
            flags |= Container.CountFlags.CountStartOnly

        if flags == Container.CountFlags.CountStartOnly:
            flags = 0

        return flags

    @count_flags.setter
    def count_flags(self, value: int):
        if value & Container.CountFlags.Visits:
            self.visits_should_be_counted = True
        if value & Container.CountFlags.Turns:
            self.turn_index_should_be_counted = True
        if value & Container.CountFlags.CountStartOnly:
            self.count_at_start_only = True

    @property
    def named_only_content(self) -> dict[str, InkObject]:
        return {
            k: v for k, v in self.named_content.items() if getattr(v, "name", False)
        }

    @named_only_content.setter
    def named_only_content(self, value: t.Optional[dict[str, InkObject]]):
        for key in self.named_only_content.keys():
            del self.named_content[key]

        if not value:
            return

        for val in value.values():
            self.add_to_named_content_only(val)

    def try_add_named_content(self, content: InkObject):
        if hasattr(content, "name"):
            self.add_to_named_content_only(content)
