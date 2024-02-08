import typing as t


if t.TYPE_CHECKING:
    from .container import Container
    from .object import InkObject


class Pointer:
    def __init__(self, container: t.Optional["Container"] = None, index: int = -1):
        self.container = container
        self.index = index

    def __bool__(self):
        return self.container is not None

    def __eq__(self, other):
        if isinstance(other, Pointer):
            return self.container == other.container and self.index == other.index

        return False

    def __repr__(self):
        container = self.container and str(self.container.path) or None

        return f"Pointer({container}, {self.index})"

    def copy(self) -> "Pointer":
        return Pointer(self.container, self.index)

    def resolve(self) -> "InkObject":
        if self.container is None:
            return
        elif self.index < 0:
            return self.container
        elif self.index > len(self.container.content):
            return

        return self.container.content[self.index]

    @staticmethod
    def start_of(container: "Container") -> "Pointer":
        return Pointer(container, 0)
