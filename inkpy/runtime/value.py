import locale

from abc import ABCMeta, abstractmethod
from enum import IntEnum
from functools import total_ordering

from .exceptions import StoryException
from .object import InkObject
from .path import Path


class BadCastException(StoryException):
    def __init__(self, value: "Value", type: "ValueType"):
        super().__init__(f"Can't cast {value.value!r} from {value.type!r} to {type!r}")


class ValueType(IntEnum):
    Bool = -1

    Int = 1
    Float = 2
    List = 3
    String = 4

    DivertTarget = 5
    VariablePointer = 6


@total_ordering
class Value(InkObject, metaclass=ABCMeta):
    def __init__(self, value):
        self.value = value

        super().__init__()

    def __bool__(self):
        return bool(self.value)

    def __lt__(self, other):
        if isinstance(other, Value):
            return self.value < other.value
        return self.value < other

    def __eq__(self, other):
        if isinstance(other, Value):
            return self.value == other.value
        return self.value == other

    def __repr__(self):
        return repr(self.value)

    def __str__(self):
        return str(self.value)

    @abstractmethod
    def cast(self, type: ValueType):
        raise NotImplementedError()

    def copy(self) -> "Value":
        return self.create(self.value)

    @staticmethod
    def create(value) -> "Value":
        if isinstance(value, bool):
            return BoolValue(value)
        elif isinstance(value, float):
            return FloatValue(value)
        elif isinstance(value, int):
            return IntValue(value)
        elif isinstance(value, str):
            return StringValue(value)

    @property
    @abstractmethod
    def type(self) -> ValueType:
        raise NotImplementedError()


class BoolValue(Value):
    type = ValueType.Bool
    value: bool

    def cast(self, type: ValueType) -> Value:
        if type == self.type:
            return self

        if type == ValueType.Int:
            return IntValue(self.value and 1 or 0)

        if type == ValueType.Float:
            return FloatValue(self.value and 1.0 or 0.0)

        if type == ValueType.String:
            return StringValue(self.value and "true" or "false")

        raise BadCastException(type)


class FloatValue(Value):
    type = ValueType.Float
    value: float

    def cast(self, type: ValueType) -> Value:
        if type == self.type:
            return self

        if type == ValueType.Bool:
            return IntValue(self.value == 0 and False or True)

        if type == ValueType.Int:
            return FloatValue(int(self.value))

        if type == ValueType.String:
            return StringValue(locale.str(self.value))

        raise BadCastException(type)


class IntValue(Value):
    type = ValueType.Int
    value: int

    def cast(self, type: ValueType) -> Value:
        if type == self.type:
            return self

        if type == ValueType.Bool:
            return IntValue(self.value == 0 and False or True)

        if type == ValueType.Float:
            return FloatValue(float(self.value))

        if type == ValueType.String:
            return StringValue(str(self.value))

        raise BadCastException(type)


class StringValue(Value):
    type = ValueType.String
    value: str

    def __str__(self):
        return self.value

    def cast(self, type: ValueType) -> Value:
        if type == self.type:
            return self

        if type == ValueType.Int:
            return FloatValue(int(self.value))

        if type == ValueType.Float:
            return StringValue(locale.atof(self.value))

        raise BadCastException(type)

    @property
    def is_newline(self) -> bool:
        return self.value == "\n"

    @property
    def is_non_whitespace(self) -> bool:
        return bool(self.value.strip())


class DivertTargetValue(Value):
    type = ValueType.DivertTarget
    value: Path

    def __init__(self, path: Path):
        super().__init__(path)

    def __bool__(self):
        raise RuntimeError("Shouldn't be checking the truthiness of a divert target")

    def __repr__(self):
        return f"DivertTargetValue({self.target_path})"

    def cast(self, type: ValueType) -> Value:
        if type == self.type:
            return self

        raise BadCastException(type)

    @property
    def target_path(self) -> Path:
        return self.value

    @target_path.setter
    def target_path(self, value: Path):
        self.value = value


class VariablePointerValue(Value):
    type = ValueType.VariablePointer
    value: str

    def __init__(self, name: str, index: int = -1):
        self.index = index

        super().__init__(name)

    def __bool__(self):
        raise RuntimeError("Shouldn't be checking the truthiness of a variable pointer")

    def __repr__(self):
        return f"VariablePointervalue({self.variable_name})"

    def copy(self) -> "VariablePointerValue":
        return VariablePointerValue(self.variable_name, self.index)

    def cast(self, type: ValueType) -> Value:
        if type == self.type:
            return self

        raise BadCastException(type)

    @property
    def variable_name(self) -> str:
        return self.value

    @variable_name.setter
    def variable_name(self, value: str):
        self.value = value
