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

    def to_dict(self) -> dict[str, t.Any]:
        data = {
            "callstack": self.call_stack.to_dict(),
        }

        choice_threads = {}
        for choice in self.current_choices:
            choice.original_thread_index = choice.thread_at_generation.index

            if self.call_stack.thread_with_index(choice.original_thread_index) is None:
                thread = choice.thread_at_generation.to_dict()

                if choice_threads:
                    choice_threads[choice.original_thread_index] = thread
                else:
                    data[choice.original_thread_index] = thread

        if choice_threads:
            data["choiceThreads"] = choice_threads

        data["currentChoices"] = [{c.to_dict() for c in self.current_choices}]

        # writer.WriteProperty("outputStream", w => Json.WriteListRuntimeObjs(w, outputStream));

        return data
