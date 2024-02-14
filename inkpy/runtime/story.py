from __future__ import annotations

import json
import logging
import typing as t

from collections import defaultdict

from . import serialisation, typing
from .call_stack import PushPopType
from .choice import Choice
from .choice_point import ChoicePoint
from .container import Container
from .control_command import ControlCommand
from .divert import Divert
from .exceptions import ExternalBindingsValidationError, StoryException
from .object import InkObject
from .path import Path
from .pointer import Pointer
from .search_result import SearchResult
from .state import State
from .value import DivertTargetValue, IntValue, StringValue, Value, VariablePointerValue
from .variable_assignment import VariableAssignment
from .variable_reference import VariableReference
from .variables_state import VariablesState
from .void import Void


logger = logging.getLogger("inkpy")


class Story(InkObject):
    INK_VERSION_CURRENT = 21
    INK_VERSION_MINIMUM_COMPATIBLE = 18

    def __init__(self, data: str | t.TextIO | None = None):
        super().__init__()

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
        self._temporary_evaluation_container: Container | None = None

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

    def choose_choice_index(self, index: int):
        assert index >= 0 and index < len(self.state.generated_choices)

        choice = self.state.generated_choices[index]

        # if self._on_make_choice:
        #     self._on_make_choice(choice)

        self.state.call_stack.current_thread = choice.thread_at_generation

        self.choose_path(choice.target_path)

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

        self.state.pass_arguments_to_evaluation_stack(args)
        self.choose_path(Path(path))

    def content_at_path(self, path: Path) -> SearchResult:
        return self.main_content_container.content_at_path(path)

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
                if self.state.call_stack.can_pop_thread:
                    self._add_error(
                        "Thread available to pop, threads should always be flat by the "
                        "end of evaluation?"
                    )

                if (
                    not self.state.generated_choices
                    and not self.state.did_safe_exit
                    and not self._temporary_evaluation_container
                ):
                    if self.state.call_stack.can_pop(PushPopType.Tunnel):
                        self._add_error(
                            "Unexpectedly reached end of content. Do you need a '->->' "
                            "to return from a tunnel?"
                        )
                    elif self.state.call_stack.can_pop(PushPopType.Function):
                        self._add_error(
                            "Unexpectedly reached end of content. Do you need a "
                            "'~return'?"
                        )
                    elif not self.state.call_stack.can_pop():
                        self._add_error(
                            "Ran out of content. Do you need a '->DONE' or '-> END'?"
                        )
                    else:
                        self._add_error(
                            "Unexpectedly reached end of content for unknown reason"
                        )

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
            elif self.state.has_error:
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
            self.state.current_pointer = self.state.diverted_pointer.copy()
            self.state.diverted_pointer = None

            self.visit_changed_containers_due_to_divert()

            # has valid content?
            if self.state.current_pointer:
                return

        # increment the pointer
        if self.state.current_pointer:
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
        else:
            successful_increment = False

        if not successful_increment:
            did_pop = False

            if self.state.call_stack.can_pop(PushPopType.Function):
                self.state.pop_callstack(PushPopType.Function)

                # this pop was due to a function that didn't return anything
                if self.state.in_expression_evaluation:
                    self.state.push_evaluation_stack(Void())

                did_pop = True
            elif self.state.call_stack.can_pop_thread:
                self.state.call_stack.pop_thread()

                did_pop = True
            else:
                self.state.try_exit_function_evaluation_from_game()

            if did_pop and self.state.current_pointer:
                self._next_content()

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

        # choice with condition
        if isinstance(content, ChoicePoint):
            choice = self.process_choice(content)
            if choice:
                self.state.generated_choices.append(choice)

            content = None
            should_add_to_stream = False

        # if container has no content, then it is the content itself, and skip over it
        if isinstance(content, Container):
            should_add_to_stream = False

        # content to add to evaluation stack or output stream
        if should_add_to_stream:
            # if we push a variable pointer value, we duplicate it so we can update the
            # content index
            if isinstance(content, VariablePointerValue) and content.index == -1:
                index = self.state.call_stack.context_for_variable_named(
                    content.variable_name
                )
                content = VariablePointerValue(content.variable_name, index)

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
        if content is None:
            return False

        if isinstance(content, Divert):
            if content.is_conditional:
                value = self.state.pop_evaluation_stack()

                if not self.is_truthy(value):
                    return True

            if content.has_variable_target:
                name = content.variable_divert_name
                value = self.state.variables_state.get(name)

                if value is None:
                    self._add_error(
                        "Tried to divert using a target from a variable that could not "
                        f"found ({name})"
                    )
                elif not isinstance(value, DivertTargetValue):
                    message = (
                        "Tried to divert to a target from a variable, but the variable "
                        f"({name}) didn't contain a divert target, it "
                    )

                    if isinstance(value, IntValue) and value.value == 0:
                        message += "was empty/null (the value 0)."
                    else:
                        message += f"contained '{value!r}'"

                    self._add_error(message)

                self.state.diverted_pointer = self.pointer_at_path(value.target_path)

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
                    message = f"Found {type.value}, when expected "

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

                override_tunnel_return_target = None
                if isinstance(value, DivertTargetValue):
                    override_tunnel_return_target = value
                elif not isinstance(value, Void):
                    self._add_error("Expected void if ->-> doesn't override target")
                    return True

                if self.state.try_exit_function_evaluation_from_game():
                    pass
                elif not self.state.call_stack.can_pop(type):
                    message = f"Found {type.value}, when expected "

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

            elif content.type == ControlCommand.CommandType.BeginString:
                self.state.push_to_output_stream(content)

                assert (
                    self.state.in_expression_evaluation
                ), "Expected to be in an expression when evaluating a string"
                self.state.in_expression_evaluation = False

            elif content.type == ControlCommand.CommandType.BeginTag:
                self.state.push_to_output_stream(content)

            elif content.type == ControlCommand.CommandType.EndString:
                content_for_string = []
                content_to_retain = []

                while self.state.output_stream:
                    o = self.state.output_stream.pop()

                    if (
                        isinstance(o, ControlCommand)
                        and o.type == ControlCommand.CommandType.BeginString
                    ):
                        break

                    # TODO: retain tags

                    if isinstance(o, StringValue):
                        content_for_string.append(o)

                for o in content_to_retain:
                    self.state.push_to_output_stream(o)

                value = StringValue("".join(map(str, content_for_string)))

                self.state.in_expression_evaluation = True
                self.state.push_evaluation_stack(value)

            elif content.type == ControlCommand.CommandType.EndTag:
                if self.state.in_string_evaluation:
                    raise NotImplementedError()
                else:
                    self.state.push_to_output_stream(content)

            elif content.type == ControlCommand.CommandType.End:
                self.state.force_end()

            else:
                raise NotImplementedError(content.type)

            return True

        elif isinstance(content, VariableAssignment):
            value = self.state.pop_evaluation_stack()
            self.state.variables_state.assign(content, value)

            return True

        elif isinstance(content, VariableReference):
            if content.path_for_count:
                container = content.container_for_count
                count = self.state.visit_count_for_container(container)
                value = IntValue(count)
            else:
                value = self.state.variables_state.get(content.name)

                if value is None:
                    self._add_warning(
                        f"Variable not found: '{content.name}'. Using default value "
                        "of 0 (false). This can happen with temporary variables if "
                        "the declaration hasn't yet been hit. Globals are always "
                        "given a default value on load if a value doesn't exist in "
                        "the save state."
                    )

                    value = IntValue(0)

            self.state.push_evaluation_stack(value)

            return True

        return False

    def pop_choice_string_and_tags(self) -> tuple[str, list[str]]:
        choice_only_string = self.state.pop_evaluation_stack()

        # while( state.evaluationStack.Count > 0 && state.PeekEvaluationStack() is Tag ) {
        #             if( tags == null ) tags = new List<string>();
        #             var tag = (Tag)state.PopEvaluationStack ();
        #             tags.Insert(0, tag.text); // popped in reverse order
        #         }

        return choice_only_string.value, []

    def process_choice(self, choice_point: ChoicePoint):
        show_choice = True

        if choice_point.has_condition:
            value = self.state.pop_evaluation_stack()
            if self.is_truthy(value):
                show_choice = False

        start_tags = []
        start_text = ""
        choice_only_tags = []
        choice_only_text = ""

        if choice_point.has_choice_only_content:
            choice_only_text, choice_only_tags = self.pop_choice_string_and_tags()

        if choice_point.has_start_content:
            start_text, start_tags = self.pop_choice_string_and_tags()

        if choice_point.once_only:
            count = self.state.visit_count_for_container(choice_point.choice_target)
            if count > 0:
                show_choice = False

        if not show_choice:
            return

        choice = Choice()
        choice.target_path = choice_point.path_on_choice
        choice.source_path = str(choice_point.path)
        choice.is_invisible_default = choice_point.is_invisible_default
        choice.tags = choice_only_tags + start_tags
        choice.thread_at_generation = self.state.call_stack.fork_thread()
        choice.text = (start_text + choice_only_text).strip()

        return choice

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
        if isinstance(value, DivertTargetValue):
            self._add_error(
                f"Shouldn't use a divert target (to {value.target_path}) as a "
                "conditional value. Did you intend a function call 'likeThis()' or "
                "a read count check 'likeThis'? (no arrows)"
            )

            return False
        elif isinstance(value, Value):
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

    def pointer_at_path(self, path: Path) -> Pointer:
        length = len(path)
        if length == 0:
            return

        pointer = Pointer()

        if path.last_component.is_index:
            length = length - 1
            result = self.main_content_container.content_at_path(path, length=length)
            pointer.container = result.container
            pointer.index = path.last_component.index
        else:
            result = self.main_content_container.content_at_path(path)
            pointer.container = result.container
            pointer.index = -1

        if (
            result.content is None
            or result.content == self.main_content_container
            and length > 0
        ):
            self._add_error(
                f"Failed to find content at path '{path}', and no approximation of "
                "it was possible."
            )
        elif result.approximate:
            self._add_warning(
                f"Failed to find content at path '{path}', so it was approximated to: "
                f"'{result.content.path}'"
            )

        return pointer

    def reset_callstack(self):
        """Unwinds the callstack to reset story evaluation without changing state."""
        self.state.force_end()

    def reset_errors(self):
        """Reset all errors from execution."""
        self.state.reset_errors()

    def reset_globals(self):
        """Reset global variables back to their initial defaults."""

        if "global decl" in self._main_content_container.named_content:
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

    def tags_for_content_at_path(self, path: str) -> list[str]:
        """Gets any tags associated with a knot or stitch defined at the beginning."""
        path = Path(path)

        container = self.content_at_path(path).container

        # get first piece of content
        while True:
            try:
                content = container.content[0]
            except IndexError:
                break

            if isinstance(content, Container):
                container = content
            else:
                break

        in_tag = False
        tags = []

        for content in container.content:
            if isinstance(content, ControlCommand):
                if content.type == ControlCommand.CommandType.BeginTag:
                    in_tag = True
                elif content.type == ControlCommand.CommandType.EndTag:
                    in_tag = False

            # gather all tags
            elif in_tag:
                if not isinstance(content, StringValue):
                    self._add_warning('"Main" tags contained non-text content')
                tags.append(content)

            # TODO: shouldn't we handle Tag?

            # anything else, we're done, we only recognise initial tags
            else:
                break

        return tags

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
