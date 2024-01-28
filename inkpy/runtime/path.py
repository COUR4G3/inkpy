import typing as t


class Path:
    PARENT_ID = "^"

    class Component:
        def __init__(self, index_or_name: int | str):
            self.index = -1
            self.name = None

            if isinstance(index_or_name, str):
                self.name = index_or_name
            else:
                self.index = index_or_name

        def __eq__(self, other):
            if isinstance(other, Path.Component):
                if self.is_index == other.is_index:
                    if self.is_index:
                        return self.index == other.index
                    else:
                        return self.name == other.name
            return False

        def __repr__(self):
            return self.is_index and str(self.index) or self.name

        def __str__(self):
            return self.is_index and str(self.index) or self.name

        @property
        def is_index(self) -> bool:
            return self.index >= 0

        @property
        def is_parent(self) -> bool:
            return self.name == Path.PARENT_ID

        @staticmethod
        def to_parent() -> "Path.Component":
            return Path.Component(Path.PARENT_ID)

    def __init__(
        self,
        components: t.Optional[Component | str | list[Component]] = None,
        tail: t.Optional["Path"] = None,
        is_relative: bool = False,
    ):
        self._components = []
        self.is_relative = is_relative
        self.components = components
        if tail:
            self.components.append(tail)

    def __eq__(self, other):
        if not isinstance(other, Path):
            return False
        elif len(self) != len(other):
            return False
        elif self.is_relative != other.is_relative:
            return False

        for self_component, other_component in zip(self, other):
            if self_component != other_component:
                return False
        return True

    def __iter__(self):
        return iter(self._components)

    def __len__(self):
        return len(self._components)

    def __repr__(self):
        return f"{self.is_relative and '.' or ''}{'.'.join(map(repr, self.components))}"

    def __str__(self):
        return f"{self.is_relative and '.' or ''}{'.'.join(map(str, self.components))}"

    @property
    def components(self) -> list[Component]:
        return self._components

    @components.setter
    def components(self, value: Component | str | list[Component]):
        if value is None:
            self._components.clear()
        elif isinstance(value, Path.Component):
            self._components.clear()
            self._components = [Path.Component]
        elif isinstance(value, list):
            self._components = value
        else:
            if value.startswith("."):
                self.is_relative = True
                value = value[1:]
            else:
                self.is_relative = False
            for component in value.split("."):
                try:
                    self._components.append(Path.Component(int(component)))
                except ValueError:
                    self._components.append(Path.Component(component))

    @property
    def last_component(self) -> t.Optional["Path.Component"]:
        if self._components:
            return self._components[-1]

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
        if len(self._components) >= 2:
            return Path(self._components[1:])
