import typing as t

from dataclasses import dataclass

from .container import Container
from .object import InkObject


@dataclass
class SearchResult:
    obj: InkObject
    approximate: bool

    @property
    def container(self) -> t.Optional[Container]:
        return isinstance(self.obj, Container) and self.obj or None

    @property
    def correct_obj(self) -> t.Optional[InkObject]:
        return not self.approximate and self.obj or None
