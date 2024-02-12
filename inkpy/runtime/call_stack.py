import typing as t

from enum import Enum

from .pointer import Pointer

if t.TYPE_CHECKING:
    from .object import InkObject
    from .story import Story
    from .value import Value


class PushPopType(Enum):
    Function = "Function"
    FunctionEvaluationFromGame = "FunctionEvaluationFromGame"
    Tunnel = "Tunnel"


class CallStack:
    class Element:
        def __init__(
            self,
            type: PushPopType,
            pointer: "Pointer",
            in_expression_evaluation: bool = False,
        ):
            self.type = type
            self.current_pointer = pointer
            self.temporary_variables: dict[str, "InkObject"] = {}
            self.in_expression_evaluation = in_expression_evaluation

            self.evaluation_stack_height_when_pushed: int = -1
            self.function_start_in_output_stream: int = -1

        def copy(self) -> "CallStack.Element":
            current_pointer = (
                self.current_pointer and self.current_pointer.copy() or None
            )

            copy = CallStack.Element(
                self.type, current_pointer, self.in_expression_evaluation
            )

            copy.evaluation_stack_height_when_pushed = (
                self.evaluation_stack_height_when_pushed
            )
            copy.function_start_in_output_stream = self.function_start_in_output_stream

            return copy

    class Thread:
        def __init__(self):
            self.callstack: list[CallStack.Element] = []
            self.index: int = -1
            self.previous_pointer: t.Optional["Pointer"] = None

        def copy(self):
            copy = CallStack.Thread()
            copy.index = self.index
            for element in self.callstack:
                copy.callstack.append(element.copy())
            copy.previous_pointer = self.previous_pointer
            return copy

    def __init__(self, story: t.Optional["Story"] = None):
        self.threads: list[CallStack.Thread] = []

        if story:
            self.start_of_root = Pointer.start_of(story.root_content_container)
            self.reset()

    def __len__(self):
        return len(self.elements)

    @property
    def call_stack(self) -> list[Element]:
        return self.current_thread.callstack

    def copy(self) -> "CallStack":
        call_stack = CallStack()

        call_stack.threads = [t.copy() for t in self.threads]

        return call_stack

    @property
    def current_element(self) -> "Element":
        thread = self.threads[-1]
        elements = thread.callstack
        return elements[-1]

    @property
    def current_element_index(self) -> int:
        return len(self.call_stack) - 1

    @property
    def current_thread(self) -> "Thread":
        return self.threads[-1]

    @current_thread.setter
    def current_thread(self, value: "Thread"):
        if len(self.threads) != 1:
            raise RuntimeError(
                "Shouldn't be directly setting the current thread when we have a "
                "stack of them"
            )

        self.threads.clear()
        self.threads.append(value)

    @property
    def depth(self) -> int:
        return len(self.elements)

    @property
    def elements(self) -> list["CallStack.Element"]:
        return self.call_stack

    def get_temporary_variable(self, name: str, index: int = -1) -> "Value":
        if index == -1:
            index = self.current_element_index + 1

        context_element = self.call_stack[index - 1]

        if name in context_element.temporary_variables:
            return context_element.temporary_variables[name]

    def reset(self):
        thread = CallStack.Thread()
        thread.callstack.append(
            CallStack.Element(PushPopType.Tunnel, self.start_of_root)
        )
        self.threads: list["CallStack.Thread"] = [thread]

    def set_temporary_variable(
        self, name: str, value: "Value", declare_new: bool = False, index: int = -1
    ):
        if index == -1:
            index = self.current_element_index + 1

        context_element = self.call_stack[index - 1]

        if not declare_new and name not in context_element.temporary_variables:
            raise RuntimeError(f"Could not find temporary variable to set: {name}")

        if old_value := context_element.temporary_variables.get(name):
            # TODO: retain old value for list
            pass

        context_element.temporary_variables[name] = value
