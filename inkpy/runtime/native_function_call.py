from enum import Enum

from .object import InkObject


class NativeFunctionCall(InkObject):
    class FunctionType(Enum):
        Add = "+"
        Subtract = "-"
        Divide = "/"
        Multiply = "*"
        Mod = "%"
        Negate = "_"

        Equal = "=="
        Greater = ">"
        Less = "<"
        GreaterThanOrEquals = ">="
        LessThanOrEquals = "<="
        NotEquals = "!="
        Not = "!"

        And = "&&"
        Or = "||"

        Min = "MIN"
        Max = "MAX"

        Pow = "POW"
        Floor = "FLOOR"
        Ceiling = "CEILING"
        Int = "INT"
        Float = "FLOAT"

        Has = "?"
        Hasnt = "!?"
        Intersect = "^"

        ListMin = "LIST_MIN"
        ListMax = "LIST_MAX"
        All = "LIST_ALL"
        Count = "LIST_COUNT"
        ValueOfList = "LIST_VALUE"
        Invert = "LIST_INVERT"

    def __init__(self, type: FunctionType):
        self.type = type

        super().__init__()

    @staticmethod
    def call_with_name(name: str) -> "NativeFunctionCall":
        return NativeFunctionCall(
            NativeFunctionCall.FunctionType._value2member_map_[name]
        )

    @staticmethod
    def call_exists_with_name(name: str) -> bool:
        return name in NativeFunctionCall.FunctionType._value2member_map_

    @property
    def name(self):
        return self.type.name
