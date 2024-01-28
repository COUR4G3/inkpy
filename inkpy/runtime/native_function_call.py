import math
import operator
import typing as t

from .exceptions import StoryException
from .object import InkObject
from .value import BoolValue, IntValue, ListValue, Value, ValueType
from .void import Void


class NativeFunctionCall(InkObject):
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

    _native_functions = {}

    def __init__(self, name: str, number_of_parameters: int = 0):
        super().__init__()

        if not number_of_parameters:
            self.generate_native_functions_if_necessary()

        self.name = name
        self.number_of_parameters = number_of_parameters
        self._operator_functions = {}

    @classmethod
    def add_float_binary_op(cls, name: str, op: t.Callable):
        cls.add_op_to_native_func(name, 2, ValueType.Float, op)

    @classmethod
    def add_float_unary_op(cls, name: str, op: t.Callable):
        cls.add_op_to_native_func(name, 1, ValueType.Float, op)

    @classmethod
    def add_int_binary_op(cls, name: str, op: t.Callable):
        cls.add_op_to_native_func(name, 2, ValueType.Int, op)

    @classmethod
    def add_int_unary_op(cls, name: str, op: t.Callable):
        cls.add_op_to_native_func(name, 1, ValueType.Int, op)

    @classmethod
    def add_list_binary_op(cls, name: str, op: t.Callable):
        cls.add_op_to_native_func(name, 2, ValueType.List, op)

    @classmethod
    def add_list_unary_op(cls, name: str, op: t.Callable):
        cls.add_op_to_native_func(name, 1, ValueType.List, op)

    @classmethod
    def add_string_binary_op(cls, name: str, op: t.Callable):
        cls.add_op_to_native_func(name, 2, ValueType.String, op)

    def add_op_func_for_type(self, type: ValueType, op: t.Callable):
        self._operator_functions[type] = op

    @classmethod
    def add_op_to_native_func(
        cls, name: str, parameter_count: int, type: ValueType, op: t.Callable
    ):
        native_func = cls._native_functions.get(name)
        if not native_func:
            native_func = cls(name, parameter_count)
            cls._native_functions[name] = native_func

        native_func.add_op_func_for_type(type, op)

    @classmethod
    def call_exists_with_name(cls, name: str):
        cls.generate_native_functions_if_necessary()
        return name in cls._native_functions

    @classmethod
    def call_with_name(cls, name: str):
        cls.generate_native_functions_if_necessary()
        return cls._native_functions[name].copy()

    def call(self, parameters: list[InkObject]):
        if self.number_of_parameters != len(parameters):
            raise RuntimeError(
                f"Unexpected number of parameters: {len(parameters)}, expected "
                f"{self.number_of_parameters} for '{self.name}' operation"
            )

        has_list_value = False
        for p in parameters:
            if isinstance(p, Void):
                raise StoryException(
                    "Attempting to perform an operation on a void value. Did you "
                    'forget to "return" a value from a function you called here?'
                )
            elif isinstance(p, ListValue):
                has_list_value = True

        if len(parameters) == 2 and has_list_value:
            return self.call_binary_list_operation(parameters)

        coerced_params = self.coerce_values_to_single_type(parameters)
        coerced_type = coerced_params[0].type

        op_for_type = self._operator_functions.get(coerced_type)
        if not op_for_type:
            raise StoryException(
                f"Cannot perform operation '{self.name}' on '{coerced_type}'"
            )

        if self.number_of_parameters == 2:
            value1, value2 = parameters
            result = op_for_type(value1.value, value2.value)
        else:
            result = op_for_type(value1.value)

        return Value.create(result)

    def call_binary_list_operator(self, parameters: list[InkObject]):
        value1, value2 = parameters

        if (
            self.name in (self.Add, self.Subtract)
            and isinstance(value1, ListValue)
            and isinstance(value2, IntValue)
        ):
            return self.call_list_increment_operation(value1, value2)

        if (
            self.name in (self.And, self.Or)
            and value1.type != ValueType.List
            or value2.type != ValueType.List
        ):
            result = self.op(value1.is_truthy, value2.is_thruthy)
            return BoolValue(result)

        if value1.type == ValueType.List and value2.type == ValueType.List:
            return self.call_type([value1, value2])

        raise StoryException(
            f"Cannot use {self.name} operation on {value1.type!r} and {value2.type!r}"
        )

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

    def copy(self) -> "NativeFunctionCall":
        func = NativeFunctionCall(self.name, self.number_of_parameters)
        func._operator_functions = self._operator_functions
        return func

    @classmethod
    def generate_native_functions_if_necessary(cls):
        if cls._native_functions:
            return

        # integer operators
        cls.add_int_binary_op(cls.Add, operator.add)
        cls.add_int_binary_op(cls.Subtract, operator.sub)
        cls.add_int_binary_op(cls.Multiply, operator.mul)
        cls.add_int_binary_op(cls.Divide, operator.truediv)
        cls.add_int_binary_op(cls.Mod, operator.mod)
        cls.add_int_unary_op(cls.Negate, operator.neg)

        cls.add_int_binary_op(cls.Equal, operator.eq)
        cls.add_int_binary_op(cls.Greater, operator.gt)
        cls.add_int_binary_op(cls.Less, operator.lt)
        cls.add_int_binary_op(cls.GreaterThanOrEquals, operator.ge)
        cls.add_int_binary_op(cls.LessThanOrEquals, operator.le)
        cls.add_int_binary_op(cls.NotEquals, operator.ne)
        cls.add_int_unary_op(cls.Not, operator.not_)

        cls.add_int_binary_op(cls.And, operator.and_)
        cls.add_int_binary_op(cls.Or, operator.or_)

        cls.add_int_binary_op(cls.Max, max)
        cls.add_int_binary_op(cls.Min, min)

        cls.add_int_binary_op(cls.Pow, operator.pow)
        cls.add_int_unary_op(cls.Floor, cls.identity)
        cls.add_int_unary_op(cls.Ceiling, cls.identity)
        cls.add_int_unary_op(cls.Int, cls.identity)
        cls.add_int_unary_op(cls.Float, float)

        # float operators
        cls.add_float_binary_op(cls.Add, operator.add)
        cls.add_float_binary_op(cls.Subtract, operator.sub)
        cls.add_float_binary_op(cls.Multiply, operator.mul)
        cls.add_float_binary_op(cls.Divide, operator.truediv)
        cls.add_float_binary_op(cls.Mod, operator.mod)
        cls.add_float_unary_op(cls.Negate, operator.neg)

        cls.add_float_binary_op(cls.Equal, operator.eq)
        cls.add_float_binary_op(cls.Greater, operator.gt)
        cls.add_float_binary_op(cls.Less, operator.lt)
        cls.add_float_binary_op(cls.GreaterThanOrEquals, operator.ge)
        cls.add_float_binary_op(cls.LessThanOrEquals, operator.le)
        cls.add_float_binary_op(cls.NotEquals, operator.ne)
        cls.add_float_unary_op(cls.Not, operator.not_)

        cls.add_float_binary_op(cls.And, operator.and_)
        cls.add_float_binary_op(cls.Or, operator.or_)

        cls.add_float_binary_op(cls.Max, max)
        cls.add_float_binary_op(cls.Min, min)

        cls.add_float_binary_op(cls.Pow, operator.pow)
        cls.add_float_unary_op(cls.Floor, math.floor)
        cls.add_float_unary_op(cls.Ceiling, math.ceil)
        cls.add_float_unary_op(cls.Int, int)
        cls.add_float_unary_op(cls.Float, cls.identity)

        # string operators
        cls.add_string_binary_op(cls.Add, operator.add)
        cls.add_string_binary_op(cls.Equal, operator.eq)
        cls.add_string_binary_op(cls.NotEquals, operator.ne)
        cls.add_string_binary_op(cls.Has, operator.contains)
        cls.add_string_binary_op(
            cls.Hasnt, lambda x, y: operator.not_(operator.contains(x, y))
        )

        # list operators
        cls.add_list_binary_op(cls.Add, operator.add)
        cls.add_list_binary_op(cls.Subtract, operator.sub)
        cls.add_string_binary_op(cls.Has, operator.contains)
        cls.add_string_binary_op(
            cls.Hasnt, lambda x, y: operator.not_(operator.contains(x, y))
        )
        cls.add_string_binary_op(cls.Intersect, operator.contains)

        cls.add_list_binary_op(cls.Equal, operator.eq)
        cls.add_list_binary_op(cls.Greater, operator.gt)
        cls.add_list_binary_op(cls.Less, operator.lt)
        cls.add_list_binary_op(cls.GreaterThanOrEquals, operator.ge)
        cls.add_list_binary_op(cls.LessThanOrEquals, operator.le)
        cls.add_list_binary_op(cls.NotEquals, operator.ne)

        cls.add_list_binary_op(cls.And, lambda x, y: len(x) > 0 and len(y) > 0)
        cls.add_list_binary_op(cls.Or, lambda x, y: len(x) > 0 or len(y) > 0)

        cls.add_list_unary_op(cls.Not, lambda x: len(x) == 0 and 1 or 0)

        cls.add_list_binary_op(cls.Invert, lambda x: x.inverse())
        cls.add_list_unary_op(cls.All, lambda x: x.all())
        cls.add_list_unary_op(cls.ListMin, lambda x: x.min)
        cls.add_list_unary_op(cls.ListMax, lambda x: x.min)
        cls.add_list_unary_op(cls.Count, len)
        cls.add_list_unary_op(cls.ValueOfList, lambda x: x.max.value)

        # TODO: divert targets

    @staticmethod
    def identity(value: Value):
        return value
