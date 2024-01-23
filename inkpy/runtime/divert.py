import typing as t

from .container import Container
from .object import InkObject
from .path import Path
from .push_pop import PushPopType
from .pointer import Pointer


class Divert(InkObject):
    def __init__(self, type: t.Optional[PushPopType] = None):
        super().__init__()

        self.pushes_to_stack = type is not None
        self.stack_push_type: PushPopType

        self.external_args: int = 0
        self.is_conditional: bool = False
        self.is_external: bool = False
        self.variable_divert_name: t.Optional[str] = None

    def __str__(self):
        if self.has_variable_target:
            return f"Divert(variable: {self.variable_divert_name})"
        elif not self.target_path:
            return "Divert(null)"
        else:
            string = "Divert"

            if self.is_conditional:
                string += "?"

            if self.pushes_to_stack:
                if self.stack_push_type == PushPopType.Function:
                    string += " function"
                elif self.stack_push_type == PushPopType.Tunnel:
                    string += " tunnel"
                else:
                    string += f" {str(self.stack_push_type).lower()}"

            string += " -> "
            string += self.target_path_string
            string += f" ({self.target_path})"

            return string

    @property
    def has_variable_target(self) -> bool:
        return self.variable_divert_name is not None

    @property
    def target_path(self) -> t.Optional[Path]:
        if self._target_path and self._target_path.is_relative:
            target_object = self.target_pointer.resolve()
            if target_object:
                self._target_path = target_object.path
        return self._target_path

    @target_path.setter
    def target_path(self, path: t.Optional[Path]):
        self._target_path = path
        self._target_pointer = None

    @property
    def target_path_string(self) -> str:
        if self.target_path:
            return self.compact_path_string(self.target_path)

    @target_path_string.setter
    def target_path_string(self, path: str):
        if path:
            path = Path(path)
        self.target_path = path

    @property
    def target_pointer(self) -> t.Optional[Pointer]:
        if not self._target_pointer:
            target_object = self.resolve_path(self._target_path).obj
            if self._target_path.last_component.is_index:
                if isinstance(target_object.parent, Container):
                    container = target_object.parent
                else:
                    container = None

                index = self._target_path.last_component.index
                self._target_pointer = Pointer(container, index)
            else:
                if isinstance(target_object, Container):
                    self._target_pointer = Pointer.start_of(target_object)
                else:
                    self._target_pointer = Pointer.start_of(None)

        return self._target_pointer and self._target_pointer.copy() or None
