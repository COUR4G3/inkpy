from __future__ import annotations

import json
import logging
import typing as t

from collections import defaultdict

from . import serialisation, typing
from .call_stack import PushPopType
from .choice import Choice
from .container import Container
from .control_command import ControlCommand
from .divert import Divert
from .exceptions import ExternalBindingsValidationError, StoryException
from .object import InkObject
from .path import Path
from .pointer import Pointer
from .state import State
from .value import StringValue, Value
from .variables_state import VariablesState
from .void import Void


logger = logging.getLogger("inkpy")


class Story:
    INK_VERSION_CURRENT = 21
    INK_VERSION_MINIMUM_COMPATIBLE = 18

    def __init__(self, data: str | t.TextIO | None = None):
        self.allow_external_function_fallbacks = False

        self._evaluation_content_container: Container | None = None
        self._externals: dict[str, ExternalFunction] = {}
        self._has_validated_externals = False
        self._observers: dict[str, list[typing.Observer]] = defaultdict(list)
        self._on_did_continue: typing.DidContinueHandler | None = None
        self._on_choose_path_string: typing.ChoosePathStringHandler | None = None
        self._on_error: typing.ErrorHandler | None = None
        self._on_warning: typing.WarningHandler | None = None
        self._state_snapshot_at_last_newline: State | None = None

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
        self.visit_changed_containers_due_to_divert()

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

        # check if external functions are bound
        if not self._has_validated_externals:
            self.validate_external_bindings()

        if not self.can_continue:
            raise RuntimeError(
                "Cannot continue - check can_continue beforing calling continue_"
            )

        self.state.did_safe_exit = False
        self.state.reset_output()

        self.state.variables_state.batch_observing_variable_changes = True

        while self.can_continue:
            try:
                output_stream_ends_in_newline = self._continue_single_step()
            except StoryException as e:
                self._add_error(e)
                break

            if output_stream_ends_in_newline:
                break

        if output_stream_ends_in_newline or not self.can_continue:
            # need to rewind because we've gone too far
            if self._state_snapshot_at_last_newline:
                self.restore_snapshot()

            if not self.can_continue:
                pass  # TODO: stuff

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

    def _continue_single_step(self):
        # run next step and walk through content
        self._step()

        # run out of content, see if we can follow default invisible choice
        # and not self.state.call_stack.element_evaluate_from_game
        if not self.can_continue:
            self._try_follow_default_invisible_choice()

        # don't rewind during string evaluation
        if not self.state.in_string_evaluation:
            # did we previously find a newline that was removed by glue?
            if self._state_snapshot_at_last_newline:
                change = self._check_if_newline_still_exists()

                # definitely content after newline, rewind
                if change == "extended_beyond_newline":
                    self.restore_snapshot()
                    return True

                # glue removed content, discard snapshot
                elif change == "newline_removed":
                    self.discard_snapshot()

            # current content ends in newline
            if self.state.output_stream_ends_in_newline:
                if self.can_continue:
                    if not self._state_snapshot_at_last_newline:
                        self.state_snapshot()

                else:
                    self.discard_snapshot()

        return False

    def _check_if_newline_still_exists(self):
        snapshot = self._state_snapshot_at_last_newline
        prev_text = snapshot.current_text

        still_exists = (
            len(self.state.current_text) >= len(prev_text)
            and len(prev_text) > 0
            and self.current_text[len(prev_text) - 1] == "\n"
        )

        if len(self.current_text) == len(prev_text) and still_exists:
            return "no_change"

        # TODO: tag_count

        if not still_exists:
            return "newline_removed"

        # TODO: tag count

        if len(self.current_text.rstrip()) > len(prev_text):
            return "extended_beyond_newline"

        return "no_change"

    def _try_follow_default_invisible_choice(self):
        return

    def _next_content(self):
        # divert, if applicable
        if self.state.diverted_pointer:
            self.state.current_pointer = self.state.diverted_pointer
            self.state.diverted_pointer = None

            self.visit_changed_containers_due_to_divert()

            # has valid content?
            if self.state.current_pointer:
                return

        # increment the pointer
        successful_increment = True

        pointer = self.state.current_pointer.copy()
        pointer.index += 1

        # check if past end of content, then return to the ancestor container
        while pointer.index >= len(pointer.container.content):
            successful_increment = False

            ancestor = pointer.container.parent

            if not ancestor:
                break

            try:
                index = ancestor.content.index(pointer.container)
            except IndexError:
                break

            pointer = Pointer(ancestor, index + 1)

            successful_increment = True

        if not successful_increment:
            pointer = None
        self.state.current_pointer = pointer

        if not successful_increment:
            return  # TODO: stuff

    def _step(self):
        should_add_to_stream = True

        pointer = self.state.current_pointer
        if not pointer:
            return

        container = pointer.resolve()
        while isinstance(container, Container):
            self.visit_container(container, at_start=True)

            if len(container.content) == 0:
                break

            pointer = Pointer.start_of(container)
            container = pointer.resolve()

        self.state.current_pointer = pointer

        content = pointer.resolve()
        is_logic_or_flow_control = self._perform_logic_and_flow_control(content)

        # has flow been forced to end by flow control above?
        if not pointer:
            return

        if is_logic_or_flow_control:
            should_add_to_stream = False

        # TODO: choice with condition

        # if container has no content, then it is the content itself, and skip over it
        if isinstance(content, Container):
            should_add_to_stream = False

        # content to add to evaluation stack or output stream
        if should_add_to_stream:
            # TODO: variable pointer

            # push to expression evaluation stack
            if self.state.in_expression_evaluation:
                self.state.push_evaluation_stack(content)

            # output stream content (when not evaluating expression)
            else:
                self.state.push_to_output_stream(content)

        # step to next content, and follow diverts if applicable
        self._next_content()

        # start a new thread should be done after incrementing, so that you can
        # return to the content after instruction
        if (
            isinstance(content, ControlCommand)
            and content.type == ControlCommand.CommandType.StartThread
        ):
            self.state.call_stack.push_thread()

    def _perform_logic_and_flow_control(self, content):
        if not content:
            return False

        if isinstance(content, Divert):
            if content.is_conditional:
                value = self.state.pop_evaluation_stack()

                if not self.is_truthy(value):
                    return True

            if content.has_variable_target:
                raise NotImplementedError()
            elif content.is_external:
                raise NotImplementedError()
            else:
                self.state.diverted_pointer = content.target_pointer

            if content.pushes_to_stack:
                self.state.call_stack.push(
                    content.stack_push_type,
                    output_stream_length_with_pushed=len(self.state.output_stream),
                )

            if not self.state.diverted_pointer and not content.is_external:
                self._add_error(f"Divert resolution failed: {content!r}")

            return True

        elif isinstance(content, ControlCommand):
            if content.type == ControlCommand.CommandType.EvalStart:
                assert not self.state.in_expression_evaluation
                self.state.in_expression_evaluation = True
            elif content.type == ControlCommand.CommandType.EvalEnd:
                assert self.state.in_expression_evaluation
                self.state.in_expression_evaluation = False
            elif content.type == ControlCommand.CommandType.EvalOutput:
                if len(self.state.evaluation_stack) > 0:
                    output = self.state.pop_evaluation_stack()

                    # functions may evaluation to void
                    if not isinstance(output, Void):
                        text = StringValue(str(output))

                        self.state.push_to_output_stream(text)
            elif content.type == ControlCommand.CommandType.NoOp:
                pass
            elif content.type == ControlCommand.CommandType.Duplicate:
                self.state.push_evaluation_stack(self.state.peek_evaluation_stack())
            elif content.type == ControlCommand.CommandType.PopEvaluatedValue:
                self.state.pop_evaluation_stack()
            elif content.type == ControlCommand.CommandType.PopFunction:
                type = PushPopType.Function

                if self.state.try_exit_function_evaluation_from_game():
                    pass
                elif not self.state.call_stack.can_pop(type):
                    message = f"Found {type}, when expected "

                    if not self.state.call_stack.can_pop():
                        message = "end of flow (-> END or choice)"
                    else:
                        message = "function return statement (~return)"

                    self._add_error(message)
                else:
                    self.state.pop_callstack()
            elif content.type == ControlCommand.CommandType.PopTunnel:
                type = PushPopType.Tunnel

                value = self.state.pop_evaluation_stack()
                if not isinstance(value, Void):
                    raise NotImplementedError()

                override_tunnel_return_target = None

                if self.state.try_exit_function_evaluation_from_game():
                    pass
                elif not self.state.call_stack.can_pop(type):
                    message = f"Found {type}, when expected "

                    if not self.state.call_stack.can_pop():
                        message = "end of flow (-> END or choice)"
                    else:
                        message = "tunnel onwards statement (->->)"

                    self._add_error(message)
                else:
                    self.state.pop_callstack()

                    if override_tunnel_return_target:
                        self.state.diverted_pointer = self.pointer_at_path(
                            override_tunnel_return_target.target_path
                        )

            elif content.type == ControlCommand.CommandType.Done:
                if self.state.call_stack.can_pop_thread:
                    self.state.call_stack.pop_thread()
                else:
                    self.state.did_safe_exit = True
                    self.state.current_pointer = None
            else:
                raise NotImplementedError(content.type)

            return True

        return False

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

    def discard_snapshot(self):
        """Discard the previous snapshot."""
        self._state_snapshot_at_last_newline = None

    def get_global_variable(self, name: str):
        """Get a named global variable."""
        return self.state.variables_state.get(name)

    get_variable = get_global_variable

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

    def is_truthy(self, value: InkObject) -> bool:
        truthy = False
        if isinstance(value, Value):
            # TODO: check for divert target value

            return bool(value)

        return truthy

    def load(self, data: str | t.TextIO):
        if isinstance(data, str):
            data = json.loads(data)
        else:
            data = json.load(data)

        try:
            version = int(data["inkVersion"])
        except KeyError:
            raise ValueError("Version of ink could not be found")
        except ValueError:
            raise ValueError(
                f"Version of ink value was malformed: {data['inkVersion']!r}"
            )

        if version > self.INK_VERSION_CURRENT:
            raise RuntimeError(
                "Version of ink used to build story was newer than the current version "
                "of the loader"
            )
        elif version < self.INK_VERSION_MINIMUM_COMPATIBLE:
            raise RuntimeError(
                "Version of ink used to build story is too old to be loaded by this "
                "version of the loader"
            )
        elif version != self.INK_VERSION_CURRENT:
            logger.warning(
                "Version of ink used to build story doesn't match current version of "
                "loader. Non-critical, but recommend synchronising.",
            )

        logger.debug("Loading ink runtime with version %s", version)

        if "root" not in data:
            raise ValueError("Root node for ink not found")

        root = serialisation.load_runtime_container(data["root"])

        list_defs = data.get("listDefs")

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
            if name not in self.state.variables_state:
                raise RuntimeError(
                    f"Cannot observe variable '{name}' as it was never delared in "
                    "the story"
                )

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

        self.state.variables_state.snapshot_defaults()

    def reset_state(self):
        """Reset story back to its initial state."""
        self.state = State(self)
        self.reset_globals()

    def reset_warnings(self):
        """Reset all warnings from execution."""
        self.state.reset_warnings()

    def restore_snapshot(self):
        """Restore the state from the previous snapshot."""
        self.state = self._state_snapshot_at_last_newline
        self._state_snapshot_at_last_newline = None

    def state_snapshot(self):
        """Take a snapshot of the current state."""
        self._state_snapshot_at_last_newline = self.state
        self.state = self.state.copy()

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

    @property
    def variables_state(self) -> VariablesState:
        return self.state.variables_state

    def visit_container(self, container, at_start=True):
        return

    def visit_changed_containers_due_to_divert(self):
        return


class ExternalFunction:
    """An external function called by the story."""

    def __init__(self, name: str, f: t.Callable, lookahead_unsafe: bool = False):
        self.name = name
        self.f = f
        self.lookahead_unsafe = lookahead_unsafe

    def __call__(self, *args, **kwargs):
        return self.f(*args, **kwargs)
