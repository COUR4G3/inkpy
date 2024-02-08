from functools import total_ordering


@total_ordering
class Value:
    def __init__(self, value):
        self.value = value

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
    def __init__(self, value: bool | str):
        if isinstance(value, str):
            value = value != "false"
        self.value = bool(value)


class FloatValue(Value):
    def __init__(self, value: float):
        self.value = float(value)


class IntValue(Value):
    def __init__(self, value: int):
        self.value = int(value)


class StringValue(Value):
    def __init__(self, value: str):
        self.value = str(value)

    def __str__(self):
        return self.value
