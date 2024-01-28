import typing as t

from .object import InkObject


class VariableAssignment(InkObject):
    def __init__(
        self, variable_name: t.Optional[str] = None, is_new_decl: bool = False
    ):
        super().__init__()

        self.variable_name = variable_name
        self.is_new_decl = is_new_decl
        self.is_global = False

    def __repr__(self):
        return f"VarAssign to '{self.variable_name}'"
