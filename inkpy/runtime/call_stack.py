import typing as t

from .ink_list import InkList
from .object import InkObject
from .pointer import Pointer
from .push_pop import PushPopType

if t.TYPE_CHECKING:
    from .story import Story


class CallStack:
    class Element:
        def __init__(
            self, type: PushPopType, pointer: Pointer, in_expression_eval: bool = False
        ):
            self.type = type
            self.current_pointer = pointer
            self.temporary_variables: dict[str, InkObject] = {}
            self.in_expression_eval = in_expression_eval

            self.evaluation_stack_height_when_pushed: int = -1
            self.function_start_in_output_stream: int = -1

        def copy(self) -> "CallStack.Element":
            copy = CallStack.Element(
                self.type, self.current_pointer, self.in_expression_eval
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
            self.previous_pointer: t.Optional[Pointer] = None

        def copy(self):
            copy = CallStack.Thread()
            copy.index = self.index
            for element in self.callstack:
                copy.callstack.append(element.copy())
            copy.previous_pointer = self.previous_pointer
            return copy

    def __init__(self, story: t.Optional["Story"] = None):
        if story:
            self.start_of_root = Pointer.start_of(story.root_content_container)
            self.reset()

    @property
    def call_stack(self) -> list[Element]:
        return self.current_thread.callstack

    @property
    def call_stack_trace(self) -> str:
        trace = ""

        for i, thread in enumerate(self.threads):
            trace += f"=== THREAD {i+1}/{len(self.threads)}"
            if thread == self.current_thread:
                trace += "(current) "
            trace += "===\n"

            for element in thread.callstack:
                if element.type == PushPopType.Function:
                    trace += "  [FUNCTION] "
                elif element.type == PushPopType.Tunnel:
                    trace += "  [TUNNEL] "
                else:
                    trace += f"  [{element.type.upper()}]"

                pointer = element.current_pointer
                if pointer:
                    trace += "<SOMEWHERE IN "
                    trace += str(pointer.container.path)
                    trace += ">\n"

        return trace

    def can_pop(self, type: t.Optional[PushPopType] = None) -> bool:
        if len(self.call_stack) <= 1:
            return False
        if type == None:
            return True

        return self.current_element.type == type

    @property
    def can_pop_thread(self) -> bool:
        return len(self.threads) > 1 and not self.element_is_evaluate_from_game

    def context_for_variable_named(self, name: str) -> int:
        if name in self.current_element.temporary_variables:
            return self.current_element_index + 1
        else:
            return 0

    def copy(self) -> "CallStack":
        callstack = CallStack()
        for thread in self.threads:
            callstack.threads.append(thread.copy())
        callstack.start_of_root = self.start_of_root
        return callstack

    @property
    def current_element(self) -> Element:
        thread = self.threads[-1]
        callstack = thread.callstack
        return callstack[-1]

    @property
    def current_element_index(self) -> int:
        return len(self.call_stack) - 1

    @property
    def current_thread(self) -> Thread:
        return self.threads[-1]

    @current_thread.setter
    def current_thread(self, thread: Thread):
        assert (
            len(self.threads) == 1
        ), "Shouldn't be directly setting the current thread when we have a stack of them"
        self.threads.clear()
        self.threads.append(thread)

    @property
    def depth(self) -> int:
        return len(self.elements)

    @property
    def element_is_evaluate_from_game(self) -> bool:
        return self.current_element.type == PushPopType.FunctionEvaluationFromGame

    @property
    def elements(self) -> list[Element]:
        return self.call_stack

    def fork_thread(self) -> Thread:
        thread = self.current_thread.copy()
        thread.index = len(self.threads)
        self.threads.append(thread)
        return thread

    def get_temporary_variable_with_name(self, name: str, index: int = -1):
        if index == -1:
            index = self.current_element_index + 1

        context_element = self.call_stack[index - 1]
        return context_element.temporary_variables.get(name)

    def pop(self, type: t.Optional[PushPopType] = None):
        if self.can_pop(type):
            self.call_stack.pop(-1)
        else:
            raise RuntimeError("Mistmatched push/pop in callstack")

    def pop_thread(self):
        if self.can_pop_thread:
            self.threads.remove(self.current_thread)
        else:
            raise RuntimeError("Can't pop thread")

    def push(
        self,
        type: PushPopType,
        external_evaluation_stack_height: int = 0,
        output_stream_length_with_pushed: int = 0,
    ):
        element = CallStack.Element(
            type,
            self.current_element.current_pointer,
            in_expression_eval=False,
        )

        element.evaluation_stack_height_when_pushed = external_evaluation_stack_height
        element.function_start_in_output_stream = output_stream_length_with_pushed

        self.call_stack.append(element)

    def push_thread(self):
        thread = self.current_thread.copy()
        thread.index = len(self.threads)
        self.threads.append(thread)

    def reset(self):
        thread = CallStack.Thread()
        thread.callstack.append(
            CallStack.Element(PushPopType.Tunnel, self.start_of_root)
        )
        self.threads: list["CallStack.Thread"] = [thread]

    def set_temporary_variable(
        self, name: str, value: t.Any, declare_new: bool = False, index: int = -1
    ):
        if index == -1:
            index = self.current_element_index + 1

        context_element = self.call_stack[index - 1]

        if not declare_new and name in context_element.temporary_variables:
            raise RuntimeError(f"Could not find temporary variable to set: '{name}'")

        old_value = context_element.temporary_variables.get(name)

        if isinstance(old_value, InkList) and isinstance(value, InkList):
            value.set_initial_origin_names(old_value.origin_names)

        context_element.temporary_variables[name] = value

    def thread_with_index(self, index: int) -> t.Optional[Thread]:
        for thread in self.threads:
            if thread.index == index:
                return thread
