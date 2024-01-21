import typing as t

from dataclasses import dataclass


@dataclass
class DebugMetadata:
    start_lineno: int = 0
    end_lineno: int = 0
    start_charno: int = 0
    end_charno: int = 0
    filename: t.Optional[str] = None
    source: t.Optional[str] = None
