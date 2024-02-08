import typing as t


class Path:
    PARENT_ID = "^"

    class Component:
        def __init__(self, index_or_name: int | str):
            if isinstance(index_or_name, int):
                self.index = index_or_name
                self.name = None
            elif isinstance(index_or_name, str):
                self.index = None
                self.name = index_or_name

        def __str__(self):
            return self.is_index and str(self.index) or self.name

        @property
        def is_index(self) -> bool:
            return self.name is None and self.index is not None

        @property
        def is_parent(self) -> bool:
            return self.name == Path.PARENT_ID

        @staticmethod
        def parent() -> "Path.Component":
            return Path.Component(Path.PARENT_ID)

    def __init__(self, *components: Component | int | str, is_relative: bool = False):
        self.components: list[Path.Component] = []
        self.is_relative = is_relative

        for i, component in enumerate(components):
            if isinstance(component, str):
                if i == 0 and component.startswith("."):
                    self.is_relative = True

                for c in component.split("."):
                    if not c:
                        continue

                    self.components.append(Path.Component(c))

                continue

            elif not isinstance(component, Path.Component):
                component = Path.Component(component)

            self.components.append(component)

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

    def __getitem__(self, key: int) -> Component:
        return self.components[key]

    def __iter__(self):
        return iter(self.components)

    def __len__(self):
        return len(self.components)

    def __repr__(self):
        return f"Path({self})"

    def __str__(self):
        return f"{self.is_relative and '.' or ''}{'.'.join(self.components)}"

    def __truediv__(self, other: Component | t.Type["Path"] | int | str):
        if isinstance(other, Path):
            return self.path_by_appending_path(other)
        else:
            return self.path_by_appending_component(other)

    @property
    def last_component(self) -> t.Optional[Component]:
        if self.components:
            return self.components[-1]

    def path_by_appending_component(self, component: Component | int | str) -> "Path":
        if not isinstance(component, Path.Component):
            component = Path.Component(component)

        return Path(*self.components, component, is_relative=self.is_relative)

    def path_by_appending_path(self, path: t.Type["Path"] | int | str) -> "Path":
        p = Path()

        upward_moves = 0
        for component in path.components:
            if component.is_parent:
                upward_moves += 1
            else:
                break

        for component in self.components[1 : -upward_moves - 1]:
            p.components.append(component)

        for component in path.components[upward_moves:]:
            p.components.append(component)

        return p

    @staticmethod
    def self() -> "Path":
        return Path(is_relative=True)

    @property
    def tail(self) -> "Path":
        if len(self.components) >= 2:
            return Path(self.components[1:])
        else:
            return Path.self()
