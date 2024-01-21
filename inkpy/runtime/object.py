import typing as t

from dataclasses import dataclass

from .container import Container
from .debug import DebugMetadata
from .path import Path


@dataclass
class InkObject:
    parent: t.Optional["InkObject"] = None

    _debug: t.Optional[DebugMetadata] = None
    _path: t.Optional["Path"] = None

    @property
    def debug(self) -> t.Optional[DebugMetadata]:
        return self._debug or (self.parent and self.parent.debug)

    @debug.setter
    def debug(self, metadata: DebugMetadata):
        self._debug = metadata

    @property
    def path(self) -> t.Optional[Path]:
        if not self._path:
            if not self.parent:
                self._path = Path()
            else:
                components = []

                child = self
                container = isinstance(child.parent, Container) and child.parent

                while container:
                    if child.name:
                        components.insert(0, Path.Component(child.name))
                    else:
                        components.insert(0, Path.Component(child.content.index(child)))

                    child = container
                    container = (
                        isinstance(container.parent, Container) and container.parent
                    )

                self._path = Path(components)

        return self._path

    @path.setter
    def path(self, path: Path):
        self._path = path

    @property
    def root(self) -> t.Optional[Container]:
        ancestor = self
        while ancestor.parent:
            ancestor = ancestor.parent
        return isinstance(ancestor, Container) and ancestor

    def set_child(self, obj: "InkObject", name: str, value: "InkObject" | None):
        setattr(obj, name, value)

        if value:
            getattr(obj, name).parent = self
