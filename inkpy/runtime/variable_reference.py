import typing as t

from .container import Container
from .object import InkObject
from .path import Path


class VariableReference(InkObject):
    def __init__(self, name: t.Optional[str] = None):
        super().__init__()

        self.name = name
        self.path_for_count: t.Optional[Path] = None

    def __str__(self):
        if self.name:
            return f"var({self.name})"
        else:
            return f"read_count({self.path_string_for_count})"

    @property
    def container_for_count(self) -> t.Optional[Container]:
        if self.path_for_count:
            return self.resolve_path(self.path_for_count).container

    @property
    def path_string_for_count(self) -> t.Optional[str]:
        if self.path_for_count:
            return self.compact_path_string(self.path_for_count)

    @path_string_for_count.setter
    def path_string_for_count(self, value: t.Optional[str]):
        if value:
            self.path_for_count = Path(value)
        else:
            self.path_for_count = None
