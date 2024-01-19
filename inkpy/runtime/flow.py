import typing as t

from dataclasses import dataclass, field

from .call_stack import CallStack
from .choice import Choice


if t.TYPE_CHECKING:
    from .story import Story


@dataclass
class Flow:
    name: str
    story: "Story"
    call_stack: CallStack = field(init=False)
    choices: list[Choice] = field(default_factory=list)

    def __post_init__(self):
        self.call_stack = CallStack(self.story)
