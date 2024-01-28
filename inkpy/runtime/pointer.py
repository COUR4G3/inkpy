import typing as t


from .path import Path


if t.TYPE_CHECKING:
    from .container import Container


class Pointer:
    def __init__(self, container: t.Optional["Container"] = None, index: int = -1):
        self.container = container
        self.index = index

    def __bool__(self):
        return self.container is not None

    def __repr__(self):
        return f"Ink Pointer -> {self.container.path} -- index {self.index}"

    def copy(self) -> "Pointer":
        return Pointer(self.container, self.index)

    @property
    def path(self) -> Path:
        if self.container is None:
            return

        if self.index >= 0:
            return self.container.path.path_by_appending_path(
                Path.Component(self.index)
            )
        else:
            return self.container.path

    def resolve(self):
        if self.index < 0:
            return self.container
        if self.container is None:
            return
        if len(self.container.content) == 0:
            return self.container
        if self.index >= len(self.container.content):
            return

        return self.container.content[self.index]

    @staticmethod
    def start_of(container: t.Optional["Container"] = None) -> "Pointer":
        return Pointer(container, 0)
