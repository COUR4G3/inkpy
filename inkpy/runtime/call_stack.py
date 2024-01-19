import typing as t

from collections import UserList
from dataclasses import dataclass, field
from enum import Enum

from .pointer import Pointer

if t.TYPE_CHECKING:
    from .story import Story


class PushPopType(Enum):
    Tunnel = "Tunnel"
    Function = "Function"
    FunctionEvaluationFromGame = "FunctionEvaluationFromGame"


class CallStack:
    @dataclass
    class Element:
        type: PushPopType
        current_pointer: Pointer
        in_expression_evaluation: bool = False
        eval_stack_height_when_pushed: int = -1
        function_start_in_output_stream: int = -1
        temp: dict[str, t.Any] = field(default_factory=dict)

        def copy(self) -> "CallStack.Element":
            element = self.__class__(
                self.type, self.current_pointer, self.in_expression_evaluation
            )

            element.temp = self.temp.copy()
            element.eval_stack_height_when_pushed = self.eval_stack_height_when_pushed
            element.function_start_in_output_stream = (
                self.function_start_in_output_stream
            )

            return element

    @dataclass
    class Thread:
        callstack: list["CallStack.Element"] = field(default_factory=list)
        previous_pointer: t.Optional[Pointer] = None

        def copy(self) -> "CallStack.Thread":
            thread = self.__class__()
            for element in self.callstack:
                thread.callstack.append(element.copy())
            thread.previous_pointer = self.previous_pointer
            return thread

    def __init__(self, story: t.Optional["Story"] = None):
        if story:
            self._root = Pointer.start_of(story.root)
            self.reset()
        else:
            self._threads: list["CallStack.Thread"] = []

    @property
    def call_stack(self):
        return self.current_thread.callstack

    def call_stack_trace(self):
        trace = ""

        for i, thread in enumerate(self._threads):
            trace += f"=== THREAD {i+1}/{len(self._threads)} "
            if thread == self.current_thread:
                trace += "(current) "
            trace += "===\n"

            for element in thread.callstack:
                if element.type == PushPopType.Function:
                    trace += "  [FUNCTION] "
                else:
                    trace += "  [TUNNEL] "

                if element.current_pointer:
                    trace += "<SOMEWHERE IN "
                    trace += str(element.current_pointer.container.path)
                    trace += ">\n"

        return trace

    @property
    def can_pop_(self) -> bool:
        return len(self.call_stack) > 1

    def can_pop(self, type: t.Optional[PushPopType] = None) -> bool:
        if not self.can_pop_:
            return False
        if type is None:
            return True

        return self.current_element.type == type

    @property
    def can_pop_thread(self) -> bool:
        return len(self._threads) > 1 and not self.element_is_evaluate_from_game

    def context_for_variable_named(self, name: str):
        if name in self.current_element.temp:
            return self.current_element_index + 1

        return 0

    def copy(self) -> "CallStack":
        call_stack = self.__class__()
        for thread in call_stack._threads:
            call_stack._threads.append(thread.copy())
        return call_stack

    @property
    def current_element(self) -> "Element":
        thread = self.current_thread
        callstack = thread.callstack
        return callstack[-1]

    @property
    def current_element_index(self) -> int:
        return len(self.elements) - 1

    @property
    def current_thread(self) -> "Thread":
        return self._threads[-1]

    @current_thread.setter
    def current_thread(self, value):
        assert (
            len(self._threads) == 1
        ), "We shouldn't directly set the current thread when we have a stack of them"

        self._threads.clear()
        self._threads.append(value)

    @property
    def depth(self) -> int:
        return len(self.elements)

    @property
    def element_is_evaluate_from_game(self) -> bool:
        return self.current_element.type == PushPopType.FunctionEvaluationFromGame

    @property
    def elements(self) -> list[Element]:
        return self.call_stack

    def get_temporary_variable_with_name(self, name: str, index: int = -1):
        if index == -1:
            index = self.current_element_index + 1

        element = self.call_stack[index - 1]

        return element.temp.get(name)

    def fork_thread(self) -> Thread:
        forked_thread = self.current_thread.copy()
        self._threads.append(forked_thread)

    def format_call_stack_trace(self):
        return self.call_stack_trace()

    def print_call_stack_trace(self):
        return print(self.format_call_stack_trace())

    def pop(self, type: t.Optional[PushPopType] = None):
        if self.can_pop(type):
            self.call_stack.pop(-1)
        else:
            raise Exception("Mismatched push/pop in Callstack")

    def pop_thread(self):
        if self.can_pop_thread:
            self._threads.remove(self.current_thread)
        else:
            raise Exception("Can't pop thread")

    def push(
        self,
        type: PushPopType,
        external_eval_stack_height: int = 0,
        ouput_stream_length_when_pushed: int = 0,
    ):
        element = self.Element(type, self.current_element.current_pointer, False)

        element.eval_stack_height_when_pushed = external_eval_stack_height
        element.function_start_in_output_stream = ouput_stream_length_when_pushed

        self.call_stack.append(element)

    def push_thread(self) -> Thread:
        new_thread = self.current_thread.copy()
        self._threads.append(new_thread)

    def reset(self):
        self._threads = []
        self._threads.append(self.Thread())
        self._threads[0].callstack.append(self.Element(PushPopType.Tunnel, self._root))

    def set_temporary_variable(
        self, name: str, value: t.Any, declare_new: bool, index: int = -1
    ):
        if index == -1:
            index = self.current_element_index + 1

        element = self.call_stack[index - 1]

        if not declare_new and name not in element.temp:
            raise Exception(f"Could not find temporary variable tot set: {name}")

        old_value = element.temp.get(name)
        # ListValue.RetainListOriginsForAssignment (oldValue, value);

        element.temp[name] = value

    def thread_with_index(self, index: int) -> Thread:
        return self._threads[index]
