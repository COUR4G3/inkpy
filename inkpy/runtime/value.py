from functools import total_ordering


from .object import InkObject


@total_ordering
class Value(InkObject):
    def __init__(self, value):
        self.value = value

        super().__init__()

    def __bool__(self):
        return self.value

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

    @staticmethod
    def create(value):
        if isinstance(value, bool):
            return BoolValue(value)
        elif isinstance(value, float):
            return FloatValue(value)
        elif isinstance(value, int):
            return IntValue(value)
        elif isinstance(value, str):
            return StringValue(value)


class BoolValue(Value):
    pass


class FloatValue(Value):
    pass


class IntValue(Value):
    pass


class StringValue(Value):
    def __str__(self):
        return self.value
