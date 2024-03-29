import typing as t

from .call_stack import PushPopType
from .object import InkObject
from .path import Path
from .pointer import Pointer


class Divert(InkObject):
    def __init__(self, stack_push_type: PushPopType | None = None):
        self.pushes_to_stack = stack_push_type is not None
        self.stack_push_type = stack_push_type

        self.external_args = 0
        self.is_conditional = False
        self.is_external = False
        self.variable_divert_name: str | None = None

        self._target_path = None
        self._target_pointer = None

        super().__init__()

    def __eq__(self, other):
        if isinstance(other, Divert):
            if self.has_variable_target == other.has_variable_target:
                if self.has_variable_target:
                    return self.variable_divert_name == other.variable_divert_name
                else:
                    return self.target_path == other.target_path

    def __repr__(self):
        if self.has_variable_target:
            return f"Divert(variable:{self.variable_divert_name})"
        elif not self.target_path:
            return "Divert(null)"
        else:
            return (
                f"Divert{self.is_conditional and '?' or ''} "
                f"{self.stack_push_type.value} -> {self.target_path_string!r} "
                f"({self.target_path!r})"
            )

    @property
    def has_variable_target(self):
        return self.variable_divert_name is not None

    @property
    def target_path(self):
        if self._target_path and self._target_path.is_relative:
            target = self.target_pointer.resolve()
            if target:
                self._target_path = target.path

        return self._target_path

    @target_path.setter
    def target_path(self, value: Path):
        self._target_path = value
        self._target_pointer = None

    @property
    def target_path_string(self) -> str | None:
        if self.target_path is None:
            return

        return self.compact_path_string(self.target_path)

    @target_path_string.setter
    def target_path_string(self, value: str | None):
        if value is None:
            self.target_path = None
        else:
            self.target_path = Path(value)

    @property
    def target_pointer(self):
        if not self._target_pointer:
            target = self.resolve_path(self._target_path).content

            last_component = self._target_path.last_component
            if last_component.is_index:
                self._target_pointer = Pointer(target.parent, last_component.index)
            else:
                self._target_pointer = Pointer.start_of(target)

        return self._target_pointer
