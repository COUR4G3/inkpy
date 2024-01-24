import operator

from enum import Enum

from .object import InkObject
from .value import BoolValue, ListValue, Value, ValueType
from .void import Void


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

    def call(self, params: list[InkObject]):
        if len(params) != self.number_of_parameters:
            raise RuntimeError(
                f"Unexpected number of parameters for {self.type}: {len(params)}, "
                f"expected {self.number_of_parameters}"
            )

        has_list = False
        for arg in params:
            if isinstance(arg, Void):
                raise RuntimeError(
                    "Attempting to perform operation on a void value. Did you forget to 'return' a value from a function you called here?"
                )
            if isinstance(arg, ListValue):
                has_list = True

        coerced_params = self.coerce_values_to_single_type(params)

        if self.type == NativeFunctionCall.FunctionType.Add:
            function_params = [p.value for p in coerced_params]
            return Value.create(operator.add(*function_params))
        if self.type == NativeFunctionCall.FunctionType.Equal:
            function_params = [p.value for p in coerced_params]
            return Value.create(operator.eq(*function_params))

        raise NotImplementedError()

    @staticmethod
    def call_with_name(name: str) -> "NativeFunctionCall":
        return NativeFunctionCall(
            NativeFunctionCall.FunctionType._value2member_map_[name]
        )

    @staticmethod
    def call_exists_with_name(name: str) -> bool:
        return name in NativeFunctionCall.FunctionType._value2member_map_

    def coerce_values_to_single_type(self, params: list[Value]) -> list[Value]:
        type = ValueType.Int

        special_case_list = None

        for param in params:
            if param.type > type:
                type = param.type

            if param.type == ValueType.List:
                special_case_list = param

        coerced_params = []

        if type == ValueType.List:
            raise NotImplementedError()
        else:
            for param in params:
                value = param.cast(type)
                coerced_params.append(value)

        return coerced_params

    @property
    def name(self) -> str:
        return self.type.name

    @property
    def number_of_parameters(self) -> str:
        if self.type in (
            NativeFunctionCall.FunctionType.Add,
            NativeFunctionCall.FunctionType.Equal,
        ):
            return 2

        return 0
