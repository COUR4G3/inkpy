from .container import Container
from .object import InkObject
from .path import Path


class ChoicePoint(InkObject):
    def __init__(self, once_only: bool = True):
        self.is_invisible_default = False
        self.has_choice_only_content = False
        self.has_condition = False
        self.has_start_content = False
        self.once_only = once_only

        self._path_on_choice: Path | None = None

        super().__init__()

    def __repr__(self):
        return f"Choice: -> {self.path_on_choice}"

    @property
    def choice_target(self) -> Container:
        return self.resolve_path(self._path_on_choice).container

    @property
    def flags(self) -> int:
        flags = 0

        if self.has_condition:
            flags |= 1
        if self.has_start_content:
            flags |= 2
        if self.has_choice_only_content:
            flags |= 4
        if self.is_invisible_default:
            flags |= 8
        if self.once_only:
            flags |= 16

        return flags

    @flags.setter
    def flags(self, value: int):
        self.has_condition = (value & 1) > 0
        self.has_start_content = (value & 2) > 0
        self.has_choice_only_content = (value & 4) > 0
        self.is_invisible_default = (value & 8) > 0
        self.once_only = (value & 16) > 0

    @property
    def path_on_choice(self) -> Path:
        if self._path_on_choice and self._path_on_choice.is_relative:
            if self.choice_target:
                self._path_on_choice = self.choice_target.path
        return self._path_on_choice

    @path_on_choice.setter
    def path_on_choice(self, value: Path):
        self._path_on_choice = value

    @property
    def path_string_on_choice(self) -> str:
        return self.compact_path_string(self.path_on_choice)

    @path_string_on_choice.setter
    def path_string_on_choice(self, value: str):
        self.path_on_choice = Path(value)
