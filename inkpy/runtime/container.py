import typing as t

from dataclasses import dataclass, field
from enum import IntEnum

from .object import InkObject


@dataclass
class Container(InkObject):
    class CountFlags(IntEnum):
        Visits = 1
        Turns = 2
        CountStartOnly = 4

    name: t.Optional[str] = None

    content: list[t.Any] = field(default_factory=list)
    named_content: dict[str, t.Any] = field(default_factory=dict)

    visits_should_be_counted: bool = False
    turn_index_should_be_counted: bool = False
    count_at_start_only: bool = False

    @property
    def count_flags(self) -> CountFlags:
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
    def count_flags(self, value: int):
        if value & Container.CountFlags.Visits:
            self.visits_should_be_counted = True
        if value & Container.CountFlags.Turns:
            self.turn_index_should_be_counted = True
        if value & Container.CountFlags.CountStartOnly:
            self.count_at_start_only = True
