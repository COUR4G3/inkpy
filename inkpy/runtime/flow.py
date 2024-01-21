import typing as t

from .call_stack import CallStack
from .choice import Choice
from .object import InkObject


if t.TYPE_CHECKING:
    from .story import Story


class Flow:
    def __init__(self, name: str, story: "Story"):
        self.name = name
        self.call_stack = CallStack(story)
        self.current_choices: list[Choice] = []
        self.output_stream: list[InkObject] = []
