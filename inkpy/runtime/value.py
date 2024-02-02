import inspect
import locale
import typing as t

from abc import ABCMeta, abstractmethod, abstractproperty
from enum import IntEnum

from .exceptions import StoryException
from .ink_list import InkList
from .object import InkObject
from .path import Path


class ValueType(IntEnum):
    Bool = -1
    Int = 0
    Float = 1
    List = 2
    String = 3
    DivertTarget = 4
    VariablePointer = 5


class Value(InkObject, metaclass=ABCMeta):
    def __init__(self, value: object):
        super().__init__()

        self.value = value

    def __bool__(self):
        return bool(self.value)

    def __repr__(self):
        curframe = inspect.currentframe()
        calframe = inspect.getouterframes(curframe, 2)
        print("caller name:", calframe[1][3])
        return repr(self.value)

    @abstractmethod
    def cast(self, type: "ValueType") -> "Value":
        ...

    @abstractproperty
    def type(self) -> ValueType:
        ...

    def copy(self) -> "Value":
        return self.create(self.value, self.type)

    @staticmethod
    def create(value: t.Any, type: t.Optional[ValueType] = None) -> "Value":
        if isinstance(value, bool) or type == ValueType.Bool:
            return BoolValue(value)
        elif isinstance(value, int) or type == ValueType.Int:
            return IntValue(value)
        elif isinstance(value, float) or type == ValueType.Float:
            return FloatValue(value)
        elif isinstance(value, str) or type == ValueType.String:
            return StringValue(value)

        return

    def BadCastException(self, type: ValueType):
        return StoryException(
            f"Can't cast '{self.value}' from '{self.type}' to '{type}'"
        )


class BoolValue(Value):
    type = ValueType.Bool

    def __init__(self, value: bool = False):
        super().__init__(value)

    def __bool__(self) -> bool:
        return self.value

    def __repr__(self):
        return self.value and "true" or "false"

    def cast(self, type: "ValueType") -> "Value":
        if type == self.type:
            return self

        if type == ValueType.Int:
            return IntValue(self.value and 1 or 0)

        if type == ValueType.Float:
            return FloatValue(self.value and 1.0 or 0.0)

        if type == ValueType.String:
            return StringValue(self.value and "true" or "false")

        raise self.BadCastException(type)


class IntValue(Value):
    type = ValueType.Int

    def __init__(self, value: int = 0):
        super().__init__(value)

    def __bool__(self) -> bool:
        return self.value != 0

    def __str__(self):
        return str(self.value)

    def cast(self, type: "ValueType") -> "Value":
        if type == self.type:
            return self

        if type == ValueType.Bool:
            return BoolValue(self.value != 0)

        if type == ValueType.Float:
            return FloatValue(float(self.value))

        if type == ValueType.String:
            return StringValue(str(self.value))

        raise self.BadCastException(type)


class FloatValue(Value):
    type = ValueType.Float

    def __init__(self, value: int = 0.0):
        super().__init__(value)

    def __bool__(self) -> bool:
        return self.value != 0.0

    def __str__(self):
        return self.value and "true" or "false"

    def cast(self, type: "ValueType") -> "Value":
        if type == self.type:
            return self

        if type == ValueType.Bool:
            return BoolValue(self.value != 0.0)

        if type == ValueType.Int:
            return IntValue(int(self.value))

        if type == ValueType.String:
            return StringValue(locale.str(self.value))

        raise self.BadCastException(type)


class StringValue(Value):
    type = ValueType.String

    def __init__(self, value: str = ""):
        self.is_newline = value == "\n"
        self.is_inline_whitespace = True

        for c in value:
            if c != " " and c != "\t":
                self.is_inline_whitespace = False
                break

        super().__init__(value)

    def __bool__(self) -> bool:
        return len(self.value) > 0

    def cast(self, type: "ValueType") -> "Value":
        if type == self.type:
            return self

        if type == ValueType.Bool:
            return BoolValue(len(self.value) > 0)

        if type == ValueType.Int:
            return IntValue(int(self.value))

        if type == ValueType.Float:
            return StringValue(locale.atof(self.value))

        raise self.BadCastException(type)

    @property
    def is_non_whitespace(self) -> bool:
        return not self.is_newline and not self.is_inline_whitespace


class DivertTargetValue(Value):
    type = ValueType.DivertTarget

    def __init__(self, value: t.Optional[Path] = None):
        super().__init__(value)

    def __bool__(self):
        raise RuntimeError("Shouldn't be checking the truthiness of a divert target")

    def __repr__(self):
        return f"DivertTargetValue({self.target_path})"

    def cast(self, type: "ValueType") -> "Value":
        if type == self.type:
            return self

        raise self.BadCastException(type)

    @property
    def target_path(self) -> str:
        return self.value

    @target_path.setter
    def target_path(self, value: str):
        self.value = value


class VariablePointerValue(Value):
    type = ValueType.VariablePointer

    def __init__(self, value: t.Optional[str] = None, index: int = -1):
        self.index = index

        super().__init__(value)

    def __bool__(self):
        raise RuntimeError("Shouldn't be checking the truthiness of a variable pointer")

    def __repr__(self):
        return f"VariablePointerValue({self.variable_name})"

    def cast(self, type: "ValueType") -> "Value":
        if type == self.type:
            return self

        raise self.BadCastException(type)

    def copy(self) -> "VariablePointerValue":
        return VariablePointerValue(self.variable_name, self.index)

    @property
    def variable_name(self) -> str:
        return self.value

    @variable_name.setter
    def variable_name(self, value: str):
        self.value = value


class ListValue(Value):
    type = ValueType.List

    def __init__(self, value: t.Optional[InkList] = None):
        self.value: InkList

        super().__init__(InkList(value))

    def __bool__(self):
        return len(self.value) > 0

    def cast(self, type: "ValueType") -> "Value":
        if type == ValueType.Int:
            max = self.value.max
            if not max:
                return IntValue(0)
            else:
                _, value = max
                return IntValue(value)
        elif type == ValueType.Float:
            max = self.value.max
            if not max:
                return FloatValue(0.0)
            else:
                _, value = max
                return FloatValue(float(value))
        elif type == ValueType.String:
            max = self.value.max
            if not max:
                return StringValue("")
            else:
                key, _ = max
                return StringValue(str(key))

        if type == self.type:
            return self

        raise self.BadCastException(type)

    def retain_list_origins_for_assignment(old: InkObject, new: InkObject):
        old_list = isinstance(old, ListValue) and old
        new_list = isinstance(new, ListValue) and new

        if old_list and new_list and len(new_list.value) == 0:
            new_list.value.set_initial_origin_names(old_list.value.origin_names)
