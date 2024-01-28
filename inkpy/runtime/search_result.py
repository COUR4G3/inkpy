import typing as t


if t.TYPE_CHECKING:
    from .container import Container
    from .object import InkObject


class SearchResult:
    def __init__(self, obj: t.Optional["InkObject"] = None, approximate: bool = False):
        self.obj = obj
        self.approximate = approximate

    @property
    def container(self) -> t.Optional["Container"]:
        from .container import Container

        return isinstance(self.obj, Container) and self.obj or None

    def copy(self) -> "SearchResult":
        return SearchResult(obj=self.obj, approximate=self.approximate)

    @property
    def correct_obj(self) -> t.Optional["InkObject"]:
        return self.approximate and None or self.obj
