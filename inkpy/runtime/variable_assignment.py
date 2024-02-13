from .object import InkObject


class VariableAssignment(InkObject):
    def __init__(self, variable_name: str, is_new_declaration: bool = False):
        self.variable_name = variable_name
        self.is_new_declaration = is_new_declaration
        self.is_global = False

        super().__init__()

    def __repr__(self):
        return f"VarAssign to {self.variable_name}"
