from __future__ import annotations

import logging
import typing as t

from .call_stack import CallStack
from .choice import Choice
from .flow import Flow
from .object import InkObject
from .pointer import Pointer


if t.TYPE_CHECKING:
    from .story import Story


logger = logging.getLogger("inkpy")


class State:
    DEFAULT_FLOW_NAME = "DEFAULT_FLOW"

    def __init__(self, story: "Story"):
        self.story = story

        self.current_errors: list[str] = []
        self.current_flow = Flow(self.DEFAULT_FLOW_NAME, story)
        self.current_turn_index: int = 0
        self.current_warnings: list[str] = []
        self.did_safe_exit: bool = False
        self.diverted_pointer: Pointer | None = None
        self.evaluation_stack: list[InkObject] = []

        self._current_tags: list[str] = []
        self._current_text: str = ""
        self._output_stream_tags_dirty = False
        self._output_stream_text_dirty = False

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
        return self.current_pointer and not self.has_error

    def copy(self) -> "State":
        state = State(self.story)

        state.current_flow = Flow(self.current_flow.name, self.story)
        state.diverted_pointer = self.diverted_pointer

        self.current_errors.extend(self.current_errors)

        self.current_warnings.extend(self.current_warnings)

        state.output_stream.extend(self.output_stream)
        state._current_tags.extend(self._current_tags)
        state._current_text = self._current_text
        state._output_stream_tags_dirty = self._output_stream_tags_dirty
        state._output_stream_text_dirty = self._output_stream_text_dirty

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
            self._output_stream_tags_dirty = False

        return self._current_tags

    @property
    def current_text(self) -> str:
        if self._output_stream_text_dirty:
            self._output_stream_text_dirty = False

        return self._current_text

    def force_end(self):
        self.current_pointer = None

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

    def mark_output_stream_dirty(self):
        self._output_stream_tags_dirty = True
        self._output_stream_text_dirty = True

    @property
    def output_stream(self) -> list[InkObject]:
        return self.current_flow.output_stream

    @property
    def previous_pointer(self) -> Pointer | None:
        return self.call_stack.current_thread.previous_pointer

    @previous_pointer.setter
    def previous_pointer(self, value: Pointer | None):
        self.call_stack.current_thread.previous_pointer = value

    def reset_errors(self):
        self.current_errors.clear()

    def reset_output(self, content: list[InkObject]):
        self.output_stream.clear()
        if content:
            self.output_stream.extend(content)

    def reset_warnings(self):
        self.current_warnings.clear()
