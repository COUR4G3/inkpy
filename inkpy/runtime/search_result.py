import typing as t

from dataclasses import dataclass

from .object import InkObject


if t.TYPE_CHECKING:
    from .container import Container


@dataclass
class SearchResult:
    obj: t.Optional[InkObject] = None
    approximate: t.Optional[bool] = False

    @property
    def container(self) -> t.Optional["Container"]:
        return type(self.obj).__name__ == "Container" and self.obj or None

    @property
    def correct_obj(self) -> t.Optional[InkObject]:
        return not self.approximate and self.obj or None
