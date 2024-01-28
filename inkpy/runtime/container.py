import typing as t

from enum import IntEnum

from .named_content import NamedContent
from .object import InkObject
from .path import Path
from .value import StringValue

if t.TYPE_CHECKING:
    from .search_result import SearchResult


class Container(NamedContent):
    class CountFlags(IntEnum):
        Visits = 1
        Turns = 2
        CountStartOnly = 4

    def __init__(self, name: t.Optional[str] = None, **kwargs):
        self.name = name

        self._content: list[InkObject] = []
        self.named_content: dict[str, NamedContent] = {}

        self.visits_should_be_counted: bool = False
        self.turn_index_should_be_counted: bool = False
        self.count_at_start_only: bool = False

        self._path_to_first_leaf_content: t.Optional[Path] = None

        super().__init__(**kwargs)

    def __repr__(self):
        return self.build_string_of_heirachy()

    def add_content(self, content: t.Union["InkObject", list["InkObject"]]):
        if isinstance(content, list):
            for item in content:
                self.add_content(item)
        else:
            self.content.append(content)

            # TODO: remove this when done testing
            if content is None:
                return

            if content.parent:
                raise RuntimeError(
                    f"Content '{content}' is already in '{content.parent}'"
                )

            content.parent = self

            self.try_add_named_content(content)

    def add_to_named_content_only(self, content: NamedContent):
        content.parent = self

        self.named_content[content.name] = content

    def build_string_of_heirachy(
        self, current_object: InkObject | None = None, indent: int = 0
    ) -> str:
        text = f"{indent*' '}["

        if self.has_valid_name:
            text += f" ({self.name})"

        if self is current_object:
            text += " <---"

        text += "\n"

        indent += 2

        text += f"{indent*' '}[\n"

        indent += 2

        for content in self.content:
            if isinstance(content, Container):
                text += content.build_string_of_heirachy(current_object, indent) + "\n"
            elif isinstance(content, StringValue):
                text += f'{indent*" "}"' + content.value.replace("\n", "\\n") + '",\n'
            else:
                text += f"{indent*' '}{content!r},\n"

        indent -= 2

        text += f"{indent*' '}],\n"

        named_only_content = self.named_only_content
        if named_only_content:
            text += f"{indent*' '}-- named: --\n"

            for content in named_only_content.values():
                text += content.build_string_of_heirachy(current_object, indent) + "\n"

        indent -= 2

        text += f"{indent*' '}]{indent and ',' or ''}"

        return text

    @property
    def content(self) -> list[InkObject]:
        return self._content

    @content.setter
    def content(self, content: t.Union["InkObject", list["InkObject"]]):
        self.add_content(content)

    def content_at_path(
        self, path: Path, start: int = 0, length: int = -1
    ) -> "SearchResult":
        if length == -1:
            length = len(path)

        from .search_result import SearchResult

        result = SearchResult(approximate=False)

        container = self
        current_object = self

        for component in path.components[start - 1 : length]:
            if not isinstance(container, Container):
                result.approximate = True
                break

            object = container.content_with_path_component(component)

            if object is None:
                result.approximate = True
                break

            current_object = object
            container = object

        result.obj = current_object

        return result

    def content_with_path_component(self, component: Path.Component) -> InkObject:
        if component.is_index:
            if component.index >= 0 and component.index < len(self.content):
                return self.content[component.index]
        elif component.is_parent:
            return self.parent
        else:
            content = self.named_content.get(component.name)
            return content

    @property
    def count_flags(self) -> "Container.CountFlags":
        flags = 0

        if self.visits_should_be_counted:
            flags |= Container.CountFlags.Visits
        if self.turn_index_should_be_counted:
            flags |= Container.CountFlags.Turns
        if self.count_at_start_only:
            flags |= Container.CountFlags.CountStartOnly

        if flags == Container.CountFlags.CountStartOnly:
            flags = 0

        return flags

    @count_flags.setter
    def count_flags(self, value: "Container.CountFlags"):
        if value & Container.CountFlags.Visits > 0:
            self.visits_should_be_counted = True
        if value & Container.CountFlags.Turns > 0:
            self.visits_should_be_counted = True
        if value & Container.CountFlags.CountStartOnly > 0:
            self.count_at_start_only = True

    @property
    def named_only_content(self) -> dict[str, NamedContent]:
        named_only_content = self.named_content.copy()

        for c in self.content:
            if isinstance(c, NamedContent) and c.has_valid_name:
                named_only_content.pop(c.name, None)

        return named_only_content

    @named_only_content.setter
    def named_only_content(self, value: t.Optional[dict[str, NamedContent]] = None):
        for key in self.named_only_content:
            self.named_content.pop(key)

        if value is None:
            return

        for value in value.values():
            if isinstance(value, NamedContent):
                self.add_to_named_content_only(value)

    @property
    def path_to_first_leaf_content(self) -> Path:
        components = []
        container = self

        while isinstance(container, Container):
            if len(container.content) > 0:
                components.append(Path.Component(0))
                container = container.content[0]

        return Path(components)

    def try_add_named_content(self, content: InkObject):
        if isinstance(content, NamedContent) and content.has_valid_name:
            self.add_to_named_content_only(content)
