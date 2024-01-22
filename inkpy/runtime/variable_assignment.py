import typing as t

from .object import InkObject


class VariableAssignment(InkObject):
    def __init__(self, name: t.Optional[str] = None, is_new_declaration: bool = False):
        self.variable_name = name
        self.is_new_declaration = is_new_declaration
        self.is_global = False

    def __str__(self):
        return f"VarAssign to {self.variable_name}"
