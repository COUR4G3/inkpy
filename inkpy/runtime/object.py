import typing as t

from .path import Path

if t.TYPE_CHECKING:
    from .container import Container
    from .search_result import SearchResult


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

    def resolve_path(self, path: "Path") -> "SearchResult":
        from .container import Container

        if path.is_relative:
            nearest_container = self
            if not isinstance(nearest_container, Container):
                assert self.parent, "Can't resolve relative path without parent"

                nearest_container = self.parent

                assert isinstance(
                    nearest_container, Container
                ), "Expected parent to be a container"

            return nearest_container.content_at_path(path)
        else:
            return self.root_content_container.content_at_path(path)

    @property
    def root_content_container(self) -> "Container":
        from .container import Container

        ancestor = self
        while ancestor.parent:
            ancestor = ancestor.parent
            assert isinstance(ancestor, Container), "Expected parent to be a container"
        return ancestor


"""<iframe src="https://scribehow.com/embed/Registering_a_Payment_for_a_Foreign_Currency_Invoice__lWwPvSx5SVaVPR4JqZ8fmQ" width="100%" height="640" allowfullscreen frameborder="0"></iframe>
https://scribehow.com/shared/Registering_a_Payment_for_a_Foreign_Currency_Invoice__lWwPvSx5SVaVPR4JqZ8fmQ"""
