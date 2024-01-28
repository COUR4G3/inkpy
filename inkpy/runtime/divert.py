import typing as t

from .object import InkObject
from .path import Path
from .pointer import Pointer
from .push_pop import PushPopType


class Divert(InkObject):
    def __init__(self, stack_push_type: t.Optional[PushPopType] = None):
        self.pushes_to_stack = stack_push_type is not None
        self.stack_push_type = stack_push_type

        self.variable_divert_name: t.Optional[str] = None
        self.is_external: t.Optional[bool] = False
        self.external_args: int = 0
        self.is_conditional: t.Optional[bool] = False

        self._target_path: t.Optional[Path] = None
        self._target_pointer: t.Optional[Pointer] = None

        super().__init__()

    def __eq__(self, other):
        if isinstance(other, Divert):
            if self.has_variable_target == other.has_variable_target:
                if self.has_variable_target:
                    return self.variable_divert_name == other.variable_divert_name
                else:
                    return self.target_path == other.target_path
        return False

    def __repr__(self):
        if self.has_variable_target:
            return f"Divert(variable: '{self.variable_divert_name}')"
        elif self.target_path is None:
            return "Divert(null)"
        else:
            text = "Divert{}{} -> {} ({})"

            text = text.format(
                self.is_conditional and "?" or "",
                self.pushes_to_stack
                and (
                    self.stack_push_type == PushPopType.Function
                    and " function"
                    or " tunnel"
                )
                or "",
                self.target_path_string,
                self.target_path,
            )

            return text

    @property
    def has_variable_target(self):
        return bool(self.variable_divert_name)

    @property
    def target_path(self) -> Path:
        if self._target_path and self._target_path.is_relative:
            if self.target_pointer and (target_object := self.target_pointer.resolve()):
                self._target_path = target_object.path
        return self._target_path

    @target_path.setter
    def target_path(self, value: Path):
        self._target_path = value
        self._target_pointer = None

    @property
    def target_path_string(self):
        if self.target_path:
            return self.compact_path_string(self.target_path)

    @target_path_string.setter
    def target_path_string(self, value):
        if value:
            self.target_path = Path(value)
        else:
            self.target_path = None

    @property
    def target_pointer(self) -> Pointer:
        from .container import Container

        if self._target_pointer is None:
            target = self.resolve_path(self._target_path).obj

            if self._target_path.last_component.is_index:
                container = isinstance(target.path, Container) and target.parent or None
                index = self._target_path.last_component.index
                self._target_pointer = Pointer(container, index)
            else:
                self._target_pointer = Pointer.start_of(
                    isinstance(target, Container) and target or None
                )
        return self._target_pointer.copy()
