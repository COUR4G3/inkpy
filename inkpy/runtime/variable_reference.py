from .object import InkObject
from .path import Path


class VariableReference(InkObject):
    def __init__(self, name: str | None = None):
        self.path_for_count: Path | None = None

        super().__init__(name=name)

    def __repr__(self):
        if self.name:
            return f"var({self.name})"
        else:
            return f"read_count({self.path_string_for_count})"

    @property
    def path_string_for_count(self) -> str:
        if self.path_for_count is None:
            return None

        return self.compact_path_string(self.path_for_count)

    @path_string_for_count.setter
    def path_string_for_count(self, value: str | None):
        if value is None:
            self.path_for_count = None
        else:
            self.path_for_count = value
