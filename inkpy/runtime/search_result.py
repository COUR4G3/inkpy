from dataclasses import dataclass

from .object import InkObject


@dataclass
class SearchResult:
    approximate: bool = False
    content: InkObject | None = None
