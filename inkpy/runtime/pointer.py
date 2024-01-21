from .container import Container
from .path import Path


class Pointer:
    def __init__(self, container: Container, index: int):
        self.container = container
        self.index = index

    def __bool__(self):
        return self.container is not None

    def __str__(self):
        if not self.container:
            return "Ink Pointer (null)"
        return f"Ink Pointer -> {self.container.path} -- index {self.index}"

    @property
    def path(self) -> Path:
        if self.index >= 0:
            return self.container.path.path_by_appending_component(
                Path.Component(self.index)
            )
        else:
            return self.container.path

    @staticmethod
    def start_of(container: Container) -> "Pointer":
        return Pointer(container, index=0)
