import typing as t

from contextlib import contextmanager

from .path import Path
from .search_result import SearchResult

if t.TYPE_CHECKING:
    from .container import Container


class InkObject:
    _disable_compact_strings: bool = False

    def __init__(self, parent: t.Optional["InkObject"] = None):
        self.parent = parent

        self._path = None

    def compact_path_string(self, other: Path) -> str:
        # disable compacting of path string (for instance, if compiling)
        if self._disable_compact_strings:
            return str(other)

        if other.is_relative:
            relative_path_string = str(other)
            global_path_string = str(self.path.path_by_appending_path(other))
        else:
            relative_path = self.convert_path_to_relative(other)
            relative_path_string = str(relative_path)
            global_path_string = str(other)

        if len(relative_path_string) < len(global_path_string):
            return relative_path_string
        else:
            return global_path_string

    def convert_path_to_relative(self, global_path: Path) -> str:
        last_shared_path_component_index = -1

        for i, (own, other) in enumerate(zip(self.path, global_path)):
            if own == other:
                last_shared_path_component_index = i
            else:
                break

        if last_shared_path_component_index == -1:
            return global_path

        num_upwards_moves = len(self.path) - 1 - last_shared_path_component_index
        components = []

        for i in range(0, num_upwards_moves + 1):
            components.append(Path.Component.to_parent())

            for other in global_path.components[last_shared_path_component_index + 1 :]:
                components.append(other)

        relative_path = Path(components, is_relative=True)
        return relative_path

    @classmethod
    @contextmanager
    def disable_compact_strings(cls):
        cls._disable_compact_strings = True
        try:
            yield
        finally:
            cls._disable_compact_strings = False

    @property
    def path(self) -> Path:
        if self._path is None:
            if self.parent is None:
                self._path = Path()
            else:
                components = []

                from .container import Container
                from .named_content import NamedContent

                child = self
                container = isinstance(child.parent, Container) and child.parent

                while container:
                    if isinstance(child, NamedContent) and child.has_valid_name:
                        components.insert(0, Path.Component(child.name))
                    else:
                        components.insert(
                            0, Path.Component(container.content.index(child))
                        )

                    child = container
                    container = (
                        isinstance(container.parent, Container) and container.parent
                    )

                self._path = Path(components)

        return self._path

    def resolve_path(self, path: Path) -> SearchResult:
        from .container import Container

        if path.is_relative:
            nearest_container = isinstance(self, Container) and self or None
            while not nearest_container:
                assert (
                    self.parent is not None
                ), "Can't resolve relative path because we don't have a parent"

                nearest_container = (
                    isinstance(self.parent, Container) and self.parent or None
                )
                assert nearest_container, "Expected parent to be a container"
                assert path.components[0].is_parent
                path = path.tail

            return nearest_container.content_at_path(path)
        else:
            return self.root_content_container.content_at_path(path)

    @property
    def root_content_container(self) -> "Container":
        ancestor = self
        while ancestor.parent:
            ancestor = ancestor.parent
        return ancestor
