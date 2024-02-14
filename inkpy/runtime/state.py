from __future__ import annotations

import logging
import typing as t

from .call_stack import CallStack, PushPopType
from .choice import Choice
from .container import Container
from .control_command import ControlCommand
from .flow import Flow
from .glue import Glue
from .object import InkObject
from .path import Path
from .pointer import Pointer
from .variables_state import VariablesState
from .value import StringValue, Value


if t.TYPE_CHECKING:
    from .story import Story


logger = logging.getLogger("inkpy")


class State:
    DEFAULT_FLOW_NAME = "DEFAULT_FLOW"
    INK_SAVE_STATE_VERSION = 10
    MIN_COMPATIBLE_LOAD_VERSION = 8

    def __init__(self, story: "Story"):
        self.story = story

        self.current_errors: list[str] = []
        self.current_flow = Flow(self.DEFAULT_FLOW_NAME, story)
        self.current_turn_index: int = -1
        self.current_warnings: list[str] = []
        self.did_safe_exit: bool = False
        self.diverted_pointer: Pointer | None = None
        self.evaluation_stack: list[InkObject] = []
        self.named_flows: dict[str, Flow] = {}
        self.variables_state = VariablesState(self.call_stack, story)

        self._current_tags: list[str] = []
        self._current_text: str = ""
        self._output_stream_tags_dirty = False
        self._output_stream_text_dirty = False
        self._turn_indices: dict[str, int] = {}
        self._visit_counts: dict[str, int] = {}

        self.goto_start()

    def add_error(self, message):
        self.current_errors.append(message)
        logger.error(message)

    def add_warning(self, message):
        self.current_warnings.append(message)
        logger.warning(message)

    @property
    def call_stack(self) -> CallStack:
        return self.current_flow.call_stack

    @property
    def call_stack_depth(self) -> int:
        return self.call_stack.depth

    @property
    def can_continue(self) -> bool:
        return bool(self.current_pointer and not self.has_error)

    def _clean_output_whitespace(self, text: str) -> str:
        output = ""

        current_whitespace_start = -1
        start_of_line = 0

        for i, c in enumerate(text):
            is_inline_whitespace = c in (" ", "\t")

            if is_inline_whitespace and current_whitespace_start == -1:
                current_whitespace_start = i

            if not is_inline_whitespace:
                if (
                    c != "\n"
                    and current_whitespace_start > 0
                    and current_whitespace_start != start_of_line
                ):
                    output += " "
                current_whitespace_start = -1

            if c == "\n":
                start_of_line = i + 1

            if not is_inline_whitespace:
                output += c

        return output

    def copy(self) -> "State":
        state = State(self.story)

        state.current_flow = Flow(self.current_flow.name, self.story)
        state.current_flow.call_stack = self.call_stack.copy()
        state.diverted_pointer = self.diverted_pointer
        state.previous_pointer = self.previous_pointer

        state.current_errors.extend(self.current_errors)
        state.current_warnings.extend(self.current_warnings)

        state.output_stream.extend(self.output_stream)
        state.mark_output_stream_dirty()

        state.variables_state = self.variables_state
        state.variables_state.call_stack = state.call_stack

        state.evaluation_stack.extend(self.evaluation_stack)

        state._visit_counts = self._visit_counts
        state._turn_indices = self._turn_indices

        state.current_turn_index = self.current_turn_index

        state.did_safe_exit = self.did_safe_exit

        return state

    @property
    def current_choices(self) -> list[Choice]:
        if self.can_continue:
            return []
        return self.current_flow.current_choices

    @property
    def current_flow_name(self) -> str:
        return self.current_flow.name

    @property
    def current_pointer(self) -> Pointer | None:
        return self.call_stack.current_element.current_pointer

    @current_pointer.setter
    def current_pointer(self, value: Pointer | None):
        previous_pointer = self.call_stack.current_element.current_pointer
        self.call_stack.current_thread.previous_pointer = previous_pointer
        self.call_stack.current_element.current_pointer = value

    @property
    def current_tags(self) -> list[str]:
        if self._output_stream_tags_dirty:
            self._current_tags.clear()

            text = []
            in_tag = False
            for content in self.output_stream:
                if isinstance(content, ControlCommand):
                    if content.type == ControlCommand.CommandType.BeginTag:
                        if in_tag and text:
                            self._current_tags.append("".join(text))
                            text.clear()
                        in_tag = True
                    elif content.type == ControlCommand.CommandType.EndTag:
                        if text:
                            self._current_tags.append("".join(text))
                            text.clear()
                        in_tag = False
                elif in_tag and isinstance(content, StringValue):
                    text.append(content.value)

                # TODO: handle Tag

            if text:
                self._current_tags.append("".join(text))

            self._output_stream_tags_dirty = False

        return self._current_tags

    @property
    def current_text(self) -> str:
        if self._output_stream_text_dirty:
            text = []

            in_tag = False
            for content in self.output_stream:
                if not in_tag and isinstance(content, StringValue):
                    text.append(content.value)
                elif isinstance(content, ControlCommand):
                    if content.type == ControlCommand.CommandType.BeginTag:
                        in_tag = True
                    elif content.type == ControlCommand.CommandType.EndTag:
                        in_tag = False

            # TODO: clean output whitespace
            self._current_text = self._clean_output_whitespace("".join(text))
            self._output_stream_text_dirty = False

        return self._current_text

    def force_end(self):
        self.call_stack.reset()
        self.current_flow.current_choices.clear()
        self.current_pointer = None
        self.previous_pointer = None
        self.did_safe_exit = True

    @property
    def generated_choices(self) -> list[Choice]:
        return self.current_flow.current_choices

    def goto_start(self):
        pointer = Pointer.start_of(self.story.main_content_container)
        self.call_stack.current_element.current_pointer = pointer

    @property
    def has_error(self) -> bool:
        return len(self.current_errors) > 0

    has_errors = has_error

    @property
    def has_warning(self) -> bool:
        return len(self.current_warnings) > 0

    has_warnings = has_warning

    @property
    def in_expression_evaluation(self) -> bool:
        return self.call_stack.current_element.in_expression_evaluation

    @in_expression_evaluation.setter
    def in_expression_evaluation(self, value: bool):
        self.call_stack.current_element.in_expression_evaluation = value

    @property
    def in_string_evaluation(self) -> bool:
        return False  # TODO: work this out

    def mark_output_stream_dirty(self):
        self._output_stream_tags_dirty = True
        self._output_stream_text_dirty = True

    @property
    def output_stream(self) -> list[InkObject]:
        return self.current_flow.output_stream

    @property
    def output_stream_contains_content(self) -> bool:
        return any(isinstance(c, StringValue) for c in self.output_stream)

    @property
    def output_stream_ends_in_newline(self) -> bool:
        for output in reversed(self.output_stream):
            # if not isinstance(output, ControlCommand):
            #     break
            if isinstance(output, StringValue):
                if output.is_newline:
                    return True
                elif output.is_non_whitespace:
                    break

        return False

    def pass_arguments_to_evaluation_stack(self, args: list):
        for arg in args:
            # TODO: check types

            self.push_evaluation_stack(Value.create(arg))

    def peek_evaluation_stack(self) -> InkObject:
        return self.evaluation_stack[-1]

    def pop_callstack(self, type: PushPopType | None = None):
        # TODO: trim whitepsace from function end

        self.call_stack.pop(type)

    def pop_evaluation_stack(self) -> InkObject:
        return self.evaluation_stack.pop()

    @property
    def previous_pointer(self) -> Pointer | None:
        return self.call_stack.current_thread.previous_pointer

    @previous_pointer.setter
    def previous_pointer(self, value: Pointer | None):
        self.call_stack.current_thread.previous_pointer = value

    def push_evaluation_stack(self, content: InkObject):
        # TODO: check if list value

        self.evaluation_stack.append(content)

    def push_to_output_stream(self, content: InkObject):
        include_in_output = True

        if isinstance(content, StringValue):
            if content.is_newline:
                if self.output_stream and isinstance(self.output_stream[-1], Glue):
                    include_in_output = False
                    self.output_stream.pop()
                    self.mark_output_stream_dirty()
                elif (
                    self.call_stack.current_element.function_start_in_output_stream > -1
                ):
                    include_in_output = False
                elif not self.output_stream_contains_content:
                    include_in_output = False
            elif not content.is_newline:
                content = StringValue(content.value)

        if include_in_output:
            self.output_stream.append(content)
            self.mark_output_stream_dirty()

    def reset_errors(self):
        self.current_errors.clear()

    def reset_output(self, content: list[InkObject] | None = None):
        self.output_stream.clear()
        if content:
            self.output_stream.extend(content)

    def reset_warnings(self):
        self.current_warnings.clear()

    def set_chosen_path(self, path: "Path", incrementing_turn_index: bool):
        self.current_flow.current_choices.clear()

        pointer = self.story.pointer_at_path(path)
        if pointer.container and pointer.index == -1:
            pointer.index = 0

        self.current_pointer = pointer

        if incrementing_turn_index:
            self.current_turn_index += 1

    def try_exit_function_evaluation_from_game(self) -> bool:
        if (
            self.call_stack.current_element.type
            == PushPopType.FunctionEvaluationFromGame
        ):
            self.current_pointer = None
            self.did_safe_exit = True
            return True

        return False

    def visit_count_for_container(self, container: Container) -> int:
        return self._visit_counts.get(container, 0)
