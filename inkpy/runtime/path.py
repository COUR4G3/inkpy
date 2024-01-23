import typing as t


class Path:
    PARENT_ID: str = "^"

    class Component:
        def __init__(self, index_or_name: int | str):
            if isinstance(index_or_name, int):
                self.index = index_or_name
                self.name = None
            else:
                self.index = -1
                self.name = index_or_name

        def __eq__(self, other: "Path.Component"):
            if isinstance(other, Path.Component) and other.is_index == self.is_index:
                if self.is_index:
                    return self.is_index == other.is_index
                else:
                    return self.name == other.name

            return False

        def __str__(self):
            if self.is_index:
                return str(self.index)
            else:
                return self.name

        @property
        def is_index(self) -> bool:
            return self.index >= 0

        @property
        def is_parent(self) -> bool:
            return self.name == Path.PARENT_ID

        @staticmethod
        def to_parent():
            return Path.Component(Path.PARENT_ID)

    def __init__(
        self,
        components: t.Optional[
            t.Union[list["Path.Component"], "Path.Component", str]
        ] = None,
        tail: t.Optional["Path"] = None,
        is_relative: bool = False,
    ):
        self.components: list[Path.Component] = []

        if isinstance(components, list):
            self.components.extend(components)
        elif isinstance(components, str):
            if components.startswith("."):
                is_relative = True
                components = components[1:]

            components = components.split(".")
            for component in components:
                try:
                    index = int(component)
                except ValueError:
                    self.components.append(Path.Component(component))
                else:
                    self.components.append(Path.Component(index))
        elif components:
            self.components.append(components)

        if tail:
            self.components = self.components.extend(tail.components)

        self.is_relative = is_relative

    def __add__(self, other: t.Union["Path", "Path.Component"]) -> "Path":
        if isinstance(other, Path):
            return self.path_by_appending_path(other)
        elif isinstance(other, Path.Component):
            return self.path_by_appending_component(other)
        else:
            raise TypeError(f"Cannot append '{type(other)}' to path")

    def __iter__(self):
        return iter(self.components)

    def __len__(self) -> int:
        return len(self.components)

    def __str__(self):
        path_string = ".".join(str(c) for c in self.components)
        if self.is_relative:
            path_string = f".{path_string}"
        return path_string

    def __truediv__(self, other: t.Union["Path", "Path.Component"]) -> "Path":
        if isinstance(other, Path):
            return self.path_by_appending_path(other)
        elif isinstance(other, Path.Component):
            return self.path_by_appending_component(other)
        else:
            raise TypeError(f"Cannot append '{type(other)}' to path")

    @property
    def last_component(self) -> t.Optional["Path.Component"]:
        if self.components:
            return self.components[-1]

    def path_by_appending_component(self, component: "Path.Component") -> "Path":
        path = Path()
        path.components.extend(self.components)
        path.components.append(component)
        return path

    def path_by_appending_path(self, path: "Path") -> "Path":
        p = Path()

        upward_moves = 0
        for component in path.components:
            if component.is_parent:
                upward_moves += 1
            else:
                break

        for component in self.components[:-upward_moves]:
            p.components.append(component)

        for component in path.components[upward_moves:]:
            p.components.append(component)

        return p

    @property
    def tail(self) -> "Path":
        if len(self.components) >= 2:
            return Path(self.components[1:])
        else:
            path = Path()
            path.is_relative = True
            return path
