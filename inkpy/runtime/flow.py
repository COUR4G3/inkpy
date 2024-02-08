from .call_stack import CallStack
from .choice import Choice
from .object import InkObject


class Flow:
    def __init__(self, name, story):
        self.name = name
        self.call_stack = CallStack(story)
        self.current_choices: list[Choice] = []
        self.output_stream: list[InkObject] = []
