import typing as t

from .debug import DebugMetadata
from .path import Path


if t.TYPE_CHECKING:
    from .container import Container
    from .search_result import SearchResult


class InkObject:
    def __init__(self, parent: t.Optional["InkObject"] = None):
        self.parent = parent
        self._debug: t.Optional[DebugMetadata] = None
        self._path: t.Optional["Path"] = None

    def compact_path_string(self, path: Path) -> str:
        if path.is_relative:
            relative_path_string = str(path)
            global_path_string = str(self.path.path_by_appending_path(path))
        else:
            relative_path = self.convert_path_to_relative(path)
            relative_path_string = str(relative_path)
            global_path_string = str(path)

        if len(relative_path_string) < len(global_path_string):
            return relative_path_string
        else:
            return global_path_string

    def convert_path_to_relative(self, global_path: Path) -> Path:
        own_path = self.path

        last_shared_path_comp_index = -1

        for i, (own, other) in enumerate(zip(own_path, global_path)):
            if own == other:
                last_shared_path_comp_index = i
            else:
                break

        if last_shared_path_comp_index == -1:
            return global_path

        num_upward_moves = len(own_path) - 1 - last_shared_path_comp_index

        new_path_components = []
        for _ in range(num_upward_moves):
            new_path_components.append(Path.Component.to_parent())

        for down in range(last_shared_path_comp_index + 2, len(global_path)):
            new_path_components.append(global_path[down])

        relative_path = Path(new_path_components, is_relative=True)
        return relative_path

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
                container = (
                    isinstance(child.parent, t.Type["Container"]) and child.parent
                )

                while container:
                    if child.name:
                        components.insert(0, Path.Component(child.name))
                    else:
                        components.insert(0, Path.Component(child.content.index(child)))

                    child = container
                    container = (
                        isinstance(container.parent, t.Type["Container"])
                        and container.parent
                    )

                self._path = Path(components)

        return self._path

    @path.setter
    def path(self, path: Path):
        self._path = path

    def resolve_path(self, path: Path) -> "SearchResult":
        if path.is_relative:
            nearest_container = type(self) == "Container" and self
            if not nearest_container:
                assert (
                    self.parent
                ), "Can't resolve relative path because we don't have a parent"

                nearest_container = type(self) == "Container" and self.parent
                assert nearest_container, "Expected parent to be a container"
                assert path.components[0].is_parent

                path = path.tail

            return nearest_container.content_at_path(path)
        else:
            content_container = self.root
            return content_container.content_at_path(path)

    @property
    def root(self) -> t.Optional["Container"]:
        ancestor = self
        while ancestor.parent:
            ancestor = ancestor.parent
        return type(ancestor).__name__ == "Container" and ancestor or None

    def set_child(self, obj: "InkObject", name: str, value: t.Optional["InkObject"]):
        setattr(obj, name, value)

        if value:
            getattr(obj, name).parent = self
