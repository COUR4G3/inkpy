from __future__ import annotations

import reprlib
import typing as t

from enum import IntEnum

from .object import InkObject
from .path import Path


class Container(InkObject):
    class CountFlags(IntEnum):
        Visits = 1
        Turns = 2
        CountStartOnly = 4

    def __init__(self, name: t.Optional[str] = None, **kwargs):
        self.content: list[InkObject] = []
        self.named_content: dict[str, InkObject] = {}

        self.visits_should_be_counted: bool = False
        self.turn_index_should_be_counted: bool = False
        self.count_at_start_only: bool = False

        self._path_to_first_leaf_content: t.Optional[Path] = None

        super().__init__(name, **kwargs)

    def __contains__(self, other):
        return other in self.content or other in self.named_content.values()

    def __getitem__(self, key: int | str) -> InkObject:
        if isinstance(key, int):
            return self.content[key]
        else:
            return self.named_content[key]

    def __iter__(self):
        return iter(self.content)

    @reprlib.recursive_repr()
    def __repr__(self):
        return (
            f"Container[{self.name and f'({self.name}),' or ''}{self.content!r}, "
            f"{self.named_only_content!r}]"
        )

    def __setitem__(self, key: str, content: InkObject):
        self.named_content[key] = content

    def add_content(self, content: InkObject, name: t.Optional[str] = None):
        content.parent = self

        self.content.append(content)

        if not name:
            name = content.name

        if name:
            self.add_named_content(content, name)

    def add_named_content(self, content: InkObject, name: t.Optional[str] = None):
        if not name:
            name = content.name

        if not name:
            raise TypeError("Cannot add name content without name")

        self.named_content[name] = content

    def dump_string_hierachy(
        self, current_content: t.Optional[InkObject] = None, indent: int = 0
    ) -> str:
        line = f"{' ' * indent}["

        if self.has_valid_name:
            line += f" ({self.name})"

        if self is current_content:
            line += " <---"

        lines = [line]

        indent += 2

        for content in self.content:
            if isinstance(content, Container):
                lines.append(content.dump_string_hierachy(current_content, indent))
            else:
                lines.append(f"{' ' * indent}{content!r}")

        if len(self.named_content) > 0:
            lines.append("-- named: --")

            for content in self.named_content.values():
                content = t.cast(Container, content)
                lines.append(content.dump_string_hierachy(current_content, indent))

        indent -= 2
        lines.append(f"{' ' * indent}]")

        return "\n".join(lines)

    @property
    def flags(self) -> "Container.CountFlags":
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

    @flags.setter
    def flags(self, value: "Container.CountFlags"):
        if value & Container.CountFlags.Visits > 0:
            self.visits_should_be_counted = True
        if value & Container.CountFlags.Turns > 0:
            self.turn_index_should_be_counted = True
        if value & Container.CountFlags.CountStartOnly > 0:
            self.count_at_start_only = True

    @property
    def named_only_content(self) -> dict[str, InkObject]:
        return {k: v for k, v in self.named_content.items() if v not in self.content}

    @property
    def path_to_first_leaf_content(self) -> Path:
        if not self._path_to_first_leaf_content:
            components = []

            container = self
            while isinstance(container, Container):
                if len(container.content) > 0:
                    components.append(Path.Component(0))
                    container = container.content[0]

            relative_path = Path(components, is_relative=True)

            # TODO: convert path to absolute
            path = relative_path

            self._path_to_first_leaf_content = path

        return self._path_to_first_leaf_content

    def walk(self, depth_first: bool = True) -> t.Generator[None, None, InkObject]:
        """Walk through all content recursively depth-first (or breadth-first)."""
        for content in self.content:
            if depth_first:
                if isinstance(content, Container):
                    yield from content.walk()
            else:
                yield content

        if not depth_first:
            for content in self.content:
                if isinstance(content, Container):
                    yield from content.walk(depth_first=False)
