import typing as t

from .path import Path

if t.TYPE_CHECKING:
    from .container import Container


class InkObject:
    def __init__(
        self, name: t.Optional[str] = None, parent: t.Optional["Container"] = None
    ):
        self.name = name
        self._parent = parent

        self._path: t.Optional[Path] = None

    def compact_path_string(self, path: str) -> str:
        return path

    @property
    def has_valid_name(self):
        return bool(self.name)

    @property
    def parent(self):
        return self._parent

    @parent.setter
    def parent(self, value: "InkObject"):
        if self._parent:
            raise RuntimeError(f"Content already has parent: {self._parent!r}")
        self._parent = value

    @property
    def path(self) -> Path:
        if self._path is None:
            if self.parent is None:
                self._path = Path()
            else:
                components = []

                child = self
                container = child.parent

                while container:
                    if child.has_valid_name:
                        components.insert(0, child.name)
                    else:
                        components.insert(0, container.content.index(child))

                    child = container
                    container = container.parent

                self._path = Path(*components)

        return self._path
