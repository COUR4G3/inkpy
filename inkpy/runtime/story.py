from __future__ import annotations

import asyncio
import logging
import typing as t

from collections import defaultdict

from . import serialisation, typing
from .choice import Choice
from .container import Container
from .divert import Divert
from .exceptions import ExternalBindingsValidationError, StoryException
from .object import InkObject
from .path import Path
from .state import State


logger = logging.getLogger("inkpy")


class Story:
    def __init__(self, data: str | t.TextIO | None = None):
        self.allow_external_function_fallbacks = False

        self._evaluation_content_container: Container | None = None
        self._externals: dict[str, ExternalFunction] = {}
        self._has_validated_externals = False
        self._observers: dict[str, list[typing.Observer]] = defaultdict(list)
        self._on_choose_path_string: typing.ChoosePathStringHandler | None = None
        self._on_error: typing.ErrorHandler | None = None
        self._on_warning: typing.WarningHandler | None = None

        if data:
            self.load(data)

    def _add_error(self, message):
        self.state.current_errors.append(message)
        logger.error(message)

    def _add_warning(self, message):
        self.state.current_warnings.append(message)
        logger.warning(message)

    def _assert(condition: bool, message: str):
        if not condition:
            raise StoryException(message)

    def bind_external_function(
        self, name: str, f: t.Callable | None = None, lookahead_unsafe: bool = False
    ):
        """Bind an external function."""

        def decorator(f):
            self._externals[name] = ExternalFunction(name, f, lookahead_unsafe)
            return f

        return f and decorator(f) or decorator

    @property
    def can_continue(self) -> bool:
        return self.state.can_continue

    def choose_path(self, path: Path, incrementing_turn_index: bool = True):
        self.state.set_chosen_path(path, incrementing_turn_index)

        # take note of newly visited container for read counts, turns etc.
        self.visit_changed_container_due_to_divert()

    def choose_path_string(
        self, path: str, reset_callstack: bool = True, args: list | None = None
    ):
        """Change the current position of the story to the given path."""
        if args is None:
            args = []

        if self._on_choose_path_string:
            self._on_choose_path_string(path, args)

        if reset_callstack:
            self.reset_callstack()
        else:
            current_element = self.state.call_stack.current_element
            if current_element.type == PushPopType.Function:
                container = current_element.current_pointer.container
                trace = self.state.call_stack.call_stack_trace

                raise RuntimeError(
                    f"Story was running a function ({container.path}) when you called "
                    f"choose_path_string({path}) - this is almost certainly not what "
                    f"you want! Full stack trace: \n{trace}"
                )

        self.state.pass_arguments_to_evaulation_stack(args)
        self.choose_path(Path(path))

    def continue_(self):
        """Continue story execution and return the next line of text."""

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.continue_async())
        else:
            return loop.run_until_complete(self.continue_async())

    async def continue_async(self):
        """Continue story execution asynchronously and return the next line of text."""

        if not self._has_validated_externals:
            self.validate_external_bindings()

        if not self.can_continue:
            raise RuntimeError(
                "Cannot continue - check can_continue beforing continuing"
            )

        self.state.variables_state.batch_observing_variable_changes = True

        while self.can_continue:
            try:
                output_stream_ends_in_newline = self._continue_single_step()
            except StoryException as e:
                self._add_error(e)
                break

            if output_stream_ends_in_newline:
                break

            await asyncio.sleep(0)

        if self._state_snapshot_at_last_newline:
            self.restore_state_snapshot()

        if not self.can_continue:
            pass

        self.state.did_safe_exit = False
        self._saw_lookahead_unsafe_function_after_newline = False

        if self._on_did_continue:
            self._on_did_continue()

        self.state.variables_state.batch_observing_variable_changes = False

        if self.state.has_error or self.state.has_warning:
            if self._on_error:
                for error in self.state.current_errors:
                    self._on_error(error)

                self.reset_errors()
            else:
                raise StoryException(
                    f"Ink had {len(self.state.current_errors)} error(s) and "
                    f"{len(self.state.current_warnings)} warning(s). The first error "
                    f"was: {self.state.current_errors[0]}"
                )

            if self._on_warning:
                for warning in self.state.current_warnings:
                    self._on_warning(warning)

                self.reset_warnings()

        return self.current_text

    def continue_maximally(self) -> t.Generator[None, None, str]:
        """Continue story execution until user interaction required or it ends."""
        while self.can_continue:
            yield self.continue_()

    @property
    def current_choices(self) -> list[Choice]:
        """List of choices available at the current point in the story."""
        choices = []
        for choice in self.state.current_choices:
            if not choice.is_invisible_default:
                continue
            choice.index = len(choices)
            choices.append(choice)

        return choices

    @property
    def current_errors(self) -> list[str]:
        """Any errors during evaluation of the story."""
        return self.state.current_errors

    @property
    def current_tags(self) -> list[str]:
        """Get the latest list of tags seen during the last continue_() call."""
        return self.state.current_tags

    @property
    def current_text(self) -> str:
        """Get the last line of text generated by the last continue_() call."""
        return self.state.current_text

    @property
    def current_warnings(self) -> list[str]:
        """Any warnings during evaluation of the story."""
        return self.state.current_warnings

    @property
    def global_tags(self) -> list[str]:
        """Any global tags associated with the story."""
        return self.tags_for_content_at_path("")

    @property
    def has_error(self) -> bool:
        """Encountered errors during evaluation of the story."""
        return self.state.has_error

    has_errors = has_error

    @property
    def has_warning(self) -> bool:
        """Encountered warnings during evaluation of the story."""
        return self.state.has_warning

    has_warnings = has_warning

    def load(self, data: dict | str | t.TextIO):
        root, list_defs = serialisation.load(data)

        self.root_content_container = root
        self._main_content_container = root

        self.list_defs = list_defs

        self.reset_state()

    @property
    def main_content_container(self):
        if self._evaluation_content_container:
            return self._evaluation_content_container

        return self._main_content_container

    def observe_variable(self, name: str, f: typing.Observer | None = None):
        """Observe a variable for changes."""

        def decorator(f):
            self._observers[name].append(f)
            return f

        return f and decorator(f) or decorator

    def observe_variables(self, *names: str, f: typing.Observer | None = None):
        """Observe multiple variables for changes."""

        def decorator(f):
            for name in names:
                self.observe_variable(name, f)
            return f

        return f and decorator(f) or decorator

    def on_error(self, f: t.Callable[[str], None] | None = None):
        """Register a handler for errors."""

        def decorator(f):
            self._on_error = f
            return f

        return f and decorator(f) or decorator

    def on_warning(self, f: t.Callable[[str], None] | None = None):
        """Register a handler for warnings."""

        def decorator(f):
            self._on_warning = f
            return f

        return f and decorator(f) or decorator

    def reset_callstack(self):
        """Unwinds the callstack to reset story evaluation without changing state."""
        self.state.force_end()

    def reset_errors(self):
        """Reset all errors from execution."""
        self.state.reset_errors()

    def reset_globals(self):
        """Reset global variables back to their initial defaults."""

        if "global decl" in self.root_content_container.named_content:
            original_pointer = self.state.current_pointer

            self.choose_path(Path("global decl"))
            self.continue_()

            self.state.current_pointer = original_pointer

        # self.state.variables_state.snapshot_default_globals()

    def reset_state(self):
        """Reset story back to its initial state."""

        self.state = State(self)
        self.reset_globals()

    def reset_warnings(self):
        """Reset all warnings from execution."""
        self.state.reset_warnings()

    def unbind_external_function(self, name: str):
        """Unbind a previously bound external function."""
        del self._externals[name]

    def validate_external_bindings(
        self, obj: Container | InkObject | None = None, missing: set | None = None
    ):
        """Validate all external functions are bound (or there are fallbacks)."""
        if missing is None:
            missing = set()

        if isinstance(obj, Container):
            for content in obj.content:
                self.validate_external_bindings(content, missing)
            for content in obj.named_only_content.values():
                self.validate_external_bindings(content, missing)

        elif isinstance(obj, InkObject):
            if isinstance(obj, Divert) and obj.is_external:
                name = obj.target_path_string
                if name not in self._externals:
                    if self.allow_external_function_fallbacks:
                        if name not in self.main_content_container.named_content:
                            missing.add(name)
                    else:
                        missing.add(name)

        elif missing:
            raise ExternalBindingsValidationError(
                missing, self.allow_external_function_fallbacks
            )

        self._has_validated_externals = True


class ExternalFunction:
    """An external function called by the story."""

    def __init__(self, name: str, f: t.Callable, lookahead_unsafe: bool = False):
        self.name = name
        self.f = f
        self.lookahead_unsafe = lookahead_unsafe

    def __call__(self, *args, **kwargs):
        return self.f(*args, **kwargs)
