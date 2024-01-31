import logging
import random
import time
import typing as t

from contextlib import contextmanager

from ..parser.json import JSONParser
from .choice import Choice
from .choice_point import ChoicePoint
from .container import Container
from .control_command import ControlCommand
from .divert import Divert
from .exceptions import StoryException
from .native_function_call import NativeFunctionCall
from .object import InkObject
from .path import Path
from .pointer import Pointer
from .profiler import Profiler
from .push_pop import PushPopType
from .state import State
from .tag import Tag
from .value import DivertTargetValue, IntValue, StringValue, Value, VariablePointerValue
from .variable_assignment import VariableAssignment
from .variable_reference import VariableReference
from .void import Void


logger = logging.getLogger(__name__)


class Story(InkObject):
    INK_VERSION_CURRENT: int = 21

    OnChoosePathString = t.Callable[[str, list[InkObject]], None]
    OnCompleteEvalFunc = t.Callable[[str, list[InkObject], str, InkObject], None]
    OnDidContinue = t.Callable[[], None]
    OnError = t.Callable[[str], None]
    OnEvaluateFunction = t.Callable[[str, list[InkObject]], None]
    OnMakeChoice = t.Callable[[Choice], None]

    def __init__(self, input: str | t.TextIO):
        parser = JSONParser()
        main_content_container, self.list_definitions = parser.parse(input)

        self.allow_external_function_fallbacks = True

        self._async_continue_active = False
        self._async_saving = False
        self._has_validated_externals = False
        self._main_content_container: Container = main_content_container

        self._on_choose_path_string: t.Optional[self.OnChoosePathString] = None
        self._on_complete_evaluate_function: t.Optional[self.OnCompleteEvalFunc] = None
        self._on_did_continue: t.Optional[self.OnDidContinue] = None
        self._on_error: t.Optional[self.OnError] = None
        self._on_evaluate_function: t.Optional[self.OnEvaluateFunction] = None
        self._on_make_choice: t.Optional[self.OnMakeChoice] = None

        self._profiler: t.Optional[Profiler] = None
        self._recursive_continue_count: int = 0
        self._saw_lookahead_unsafe_function_after_newline = False
        self._state_snapshot_at_last_newline: t.Optional[State] = None
        self._state: State
        self._temporary_evaluation_container: t.Optional[Container] = None

        super().__init__()

        self.reset_state()

    def __repr__(self):
        return self.build_string_of_heirachy()

    def add_error(self, message: str, is_warning: bool = False):
        if is_warning:
            level = logging.WARN
            self._state.current_warnings.append(message)
        else:
            level = logging.ERROR
            self._state.current_errors.append(message)
            self._state.force_end()

        logger.log(level, message)

    def add_warning(self, message: str):
        self.add_error(message, is_warning=True)

    @property
    def async_continue_complete(self) -> bool:
        return not self._async_continue_active

    def background_save_complete(self):
        if self._state_snapshot_at_last_newline:
            self._state.apply_any_patch()

        self._async_saving = False

    def build_string_of_heirachy(self) -> str:
        return self._main_content_container.build_string_of_heirachy(
            self._state.current_pointer.resolve()
        )

    @property
    def can_continue(self) -> bool:
        return self._state.can_continue

    def choose_choice_index(self, index: int):
        try:
            choice = self.current_choices[index]
        except IndexError:
            raise RuntimeError("Choice out of range")

        if self._on_make_choice:
            self._on_make_choice(choice)

        self.state.call_stack.current_thread = choice.thread_at_generation

        self.choose_path(choice.target_path)

    def choose_path(self, path: Path, incrementing_turn_index: bool = True):
        self.state.set_chosen_path(path, incrementing_turn_index)
        self.visit_changed_containers_due_to_divert()

    def _continue(self, limit_async: float = 0.0):
        if self._profiler:
            self._profiler.pre_continue()

        self._recursive_continue_count += 1

        if not self._async_continue_active:
            self._async_continue_active = limit_async > 0.0

            if not self.can_continue:
                raise RuntimeError(
                    "Can't continue - should check can_continue before calling continue_"
                )

            self._state.did_safe_exit = False
            self._state.reset_output()

            # we only batch calls for the outermost call
            if self._recursive_continue_count == 1:
                self._state.variables_state.batch_observing_variable_changes = True

        started = time.perf_counter()

        output_stream_ends_in_newline = False
        self._saw_lookahead_unsafe_function_after_newline = False

        while self.can_continue:
            try:
                output_stream_ends_in_newline = self.continue_single_step()
            except StoryException as e:
                self.add_error(e.message)
                break

            if output_stream_ends_in_newline:
                break

            elapsed = time.perf_counter() - started
            if self._async_continue_active and elapsed > limit_async:
                break

        if output_stream_ends_in_newline or not self.can_continue:
            pass

        self._recursive_continue_count -= 1

        if self._profiler:
            self._profiler.post_continue()

        if self._state.has_error or self._state.has_warning:
            if self._on_error:
                for error in self._state.current_errors:
                    self._on_error(error)
                for warning in self._state.current_warnings:
                    self._on_error(warning, True)

                self.reset_errors()
            else:
                if self._state.has_error:
                    first_issue = self._state.current_errors[0]
                else:
                    first_issue = self._state.current_warnings[0]

                message = (
                    f"Ink had {len(self._state.current_errors)} error(s) and "
                    f"{len(self._state.current_warnings)} warning(s). It is strongly "
                    "suggested you assign an error handler with story.on_error. "
                    f"The first issue was: {first_issue}"
                )

                raise StoryException(message)

    def continue_(self) -> str:
        self.continue_async(0.0)
        return self._state.current_text

    def continue_async(self, limit_async: float = 0.0):
        if not self._has_validated_externals:
            self.validate_external_bindings()

        self._continue(limit_async)

    def continue_maximally(self) -> str:
        self.if_async_we_cant("continue_maximally")

        text = ""
        while self.can_continue:
            text += self.continue_()
        return text

    def continue_single_step(self) -> bool:
        if self._profiler:
            self._profiler.pre_step()

        self.step()

        if self._profiler:
            self._profiler.post_step()

        if (
            not self.can_continue
            and not self._state.call_stack.element_is_evaluate_from_game
        ):
            self.try_follow_default_invisible_choice()

        if self._profiler:
            self._profiler.pre_snapshot()

        if not self.state.in_string_evaluation:
            if self._state_snapshot_at_last_newline:
                change = self.calculate_newline_output_state_change(
                    self._state_snapshot_at_last_newline.current_text,
                    self.state.current_text,
                    self._state_snapshot_at_last_newline.current_tags,
                    self.state.current_tags,
                )

                if (
                    change == OutputStateChange.ExtendedBeyondNewline
                    or self._saw_lookahead_unsafe_function_after_newline
                ):
                    self.restore_state_snapshot()

                    return True
                elif change == OutputStateChange.NewlineRemoved:
                    self.discard_snapshot()

            if self.state.output_stream_ends_in_newline:
                if self.can_continue:
                    if self._state_snapshot_at_last_newline:
                        self.state_snapshot()
                else:
                    self.discard_snapshot()

        if self._profiler:
            self._profiler.post_snapshot()

        return False

    def copy_state_for_background_thread_save(self) -> State:
        self.if_async_we_cant("start saving on a background thread")

        if self._async_saving:
            raise RuntimeError(
                "Story is already in background saving mode, can't call "
                "copy_state_for_background_thread_save again!"
            )

        state_to_save = self._state
        self._state = self._state.copy_and_start_patching()
        self._async_saving = True
        return state_to_save

    @property
    def current_choices(self) -> list[Choice]:
        return self._state.current_choices

    @property
    def current_errors(self) -> list[str]:
        return self._state.current_errors

    @property
    def current_warnings(self) -> list[str]:
        return self._state.current_warnings

    def discard_snapshot(self):
        if not self._async_saving:
            self._state.apply_any_patch()

        self._state_snapshot_at_last_newline = None

    def end_profiling(self):
        """End profiling for this story.

        You can call the :meth:`inkpy.runtime.profiler.Profiler.report` method on the
        profiler to generate a report.

        """
        self._profiler = None

    @property
    def has_error(self) -> bool:
        return len(self._state.current_errors) > 0

    has_errors = has_error

    @property
    def has_warning(self) -> bool:
        return len(self._state.current_warnings) > 0

    has_warnings = has_warning

    def if_async_we_cant(self, activity: str):
        if self._async_continue_active:
            raise RuntimeError(
                f"Can't {activity} while story is in the middle of continue_async(). "
                "Make more continue_async() calls or a single continue_() call "
                "beforehand."
            )

    def increment_content_pointer(self) -> bool:
        successful_increment = True

        pointer = self.state.call_stack.current_element.current_pointer
        pointer.index += 1

        while pointer.index >= len(pointer.container.content):
            successful_increment = False

            next_ancestor = pointer.container.parent
            if not isinstance(next_ancestor, Container):
                break

            try:
                next_ancestor_index = next_ancestor.content.index(pointer.container)
            except ValueError:
                break

            pointer = Pointer(next_ancestor, next_ancestor_index)
            pointer.index += 1

            successful_increment = True

        if not successful_increment:
            pointer = None

        self.state.call_stack.current_element.current_pointer = pointer

        return successful_increment

    def is_truthy(self, object: InkObject) -> bool:
        truthy = False
        if isinstance(object, DivertTargetValue):
            self.add_error(
                f"Shouldn't use a divert target (to '{object.target_path}') as a "
                "conditional value. Did you intend a function call 'likeThis()' "
                "or a read count check 'likeThis'? (no arrows)"
            )
            return False
        elif isinstance(object, Value):
            return bool(object)

        return truthy

    @property
    def main_content_container(self) -> Container:
        if self._temporary_evaluation_container:
            return self._temporary_evaluation_container
        else:
            return self._main_content_container

    def next_content(self):
        self.state.previous_pointer = self.state.current_pointer

        if self.state.diverted_pointer:
            self.state.current_pointer = self.state.diverted_pointer.copy()
            self.state.diverted_pointer = None

            self.visit_changed_containers_due_to_divert()

            # diverted location has valid content
            if self.state.current_pointer:
                return

            # otherwise, if divert location doesn't have valid content drop down
            # and attempt to increment
            # this can happen if the diverted path is intentionally jumping to
            # the end of the container

        successful_pointer_increment = self.increment_content_pointer()

        # ran out of content, try auto-exit
        if not successful_pointer_increment:
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
                self.state.try_exit_function_eval_from_game()

            if did_pop and self.state.current_pointer:
                self.next_content()

    def on_choose_path_string(self, f: t.Optional[OnChoosePathString] = None):
        def decorator(f):
            self._on_choose_path_string = f
            return f

        return f and decorator(f) or decorator

    def on_complete_evaluate_function(self, f: t.Optional[OnCompleteEvalFunc] = None):
        def decorator(f):
            self._on_complete_evaluate_function = f
            return f

        return f and decorator(f) or decorator

    def on_did_continue(self, f: t.Optional[OnDidContinue] = None):
        def decorator(f):
            self._on_did_continue = f
            return f

        return f and decorator(f) or decorator

    def on_error(self, f: t.Optional[OnError] = None):
        def decorator(f):
            self._on_error = f
            return f

        return f and decorator(f) or decorator

    def on_evaluate_function(self, f: t.Optional[OnEvaluateFunction] = None):
        def decorator(f):
            self._on_evaluate_function = f
            return f

        return f and decorator(f) or decorator

    def on_make_choice(self, f: t.Optional[OnMakeChoice] = None):
        def decorator(f):
            self._on_make_choice = f
            return f

        return f and decorator(f) or decorator

    def perform_logic_and_flow_control(self, object: InkObject) -> bool:
        if isinstance(object, Divert):
            if object.is_conditional:
                condition_value = self.state.pop_evaluation_stack()

                if not self.is_truthy(condition_value):
                    return True

            if object.has_variable_target:
                name = object.variable_divert_name
                content = self.state.variables_state.get_variable_with_name(name)

                if content is None:
                    self.add_error(
                        "Tried to divert using a target to a variable that "
                        f"could not be found: {name}"
                    )
                elif not isinstance(content, DivertTargetValue):
                    self.add_error(
                        f"Tried to divert to a target from a variable, but the "
                        f"variable '{name}' didn't contain a divert target, it "
                        f"contained '{content}'"
                    )

                self.state.diverted_pointer = self.pointer_at_path(content.target_path)
            elif object.is_external:
                self.call_external_function(
                    object.target_path_string, object.external_args
                )
                return True
            else:
                self.state.diverted_pointer = object.target_pointer

            if object.pushes_to_stack:
                self.state.call_stack.push(
                    object.stack_push_type,
                    output_stream_length_with_pushed=len(self.state.output_stream),
                )

            if not self.state.diverted_pointer and not object.is_external:
                # if object:  #  and object.debug.source:
                #     self.add_error(f"Divert target doesn't exist: {object}")
                # else:
                self.add_error(f"Divert resolution failed: {object}")

            return True

        elif isinstance(object, ControlCommand):
            if object.type == ControlCommand.CommandType.EvalStart:
                assert (
                    not self.state.in_expression_evaluation
                ), "Already in expression evaluation"
                self.state.in_expression_evaluation = True
            elif object.type == ControlCommand.CommandType.EvalEnd:
                assert (
                    self.state.in_expression_evaluation
                ), "Not in expression evaluation"
                self.state.in_expression_evaluation = False
            elif object.type == ControlCommand.CommandType.EvalOutput:
                if self.state.evaluation_stack:
                    output = self.state.pop_evaluation_stack()
                    if output:
                        text = StringValue(str(output))
                        self.state.push_to_output_stream(text)
            elif object.type == ControlCommand.CommandType.NoOp:
                pass
            elif object.type == ControlCommand.CommandType.Duplicate:
                self.state.push_evaluation_stack(self.state.peek_evaluation_stack())
            elif object.type == ControlCommand.CommandType.PopEvaluatedValue:
                self.state.pop_evaluation_stack()
            elif object.type in (
                ControlCommand.CommandType.PopFunction,
                ControlCommand.CommandType.PopTunnel,
            ):
                if object.type == ControlCommand.CommandType.PopFunction:
                    pop_type = PushPopType.Function
                elif object.type == ControlCommand.CommandType.PopTunnel:
                    pop_type = PushPopType.Tunnel

                override_tunnel_return_target = None
                if pop_type == PushPopType.Tunnel:
                    value = self.state.pop_evaluation_stack()
                    if isinstance(value, DivertTargetValue):
                        override_tunnel_return_target = value
                    else:
                        assert (
                            value == Void()
                        ), "Expected void if ->-> doesn't override target"

                if self.state.try_exit_function_eval_from_game():
                    pass
                elif (
                    self.state.call_stack.current_element.type != pop_type
                    or not self.state.call_stack.can_pop()
                ):
                    names = {
                        PushPopType.Function: "function return statement (~ return)",
                        PushPopType.Tunnel: "tunnel onwards statement (->->)",
                    }
                    expected = names[self.state.call_stack.current_element.type]
                    if self.state.call_stack.can_pop():
                        expected = "end of flow (-> END or choice)"

                    message = f"Found {names[pop_type]}, when expected {expected}"
                    self.add_error(message)
                else:
                    self.state.pop_callstack()
                if override_tunnel_return_target:
                    self.state.diverted_pointer = override_tunnel_return_target
            elif object.type == ControlCommand.CommandType.BeginString:
                self.state.push_to_output_stream(object)
                assert (
                    self.state.in_expression_evaluation
                ), "Expected to be in an expression evaluating a string"
                self.state.in_expression_evaluation = False
            elif object.type == ControlCommand.CommandType.BeginTag:
                self.state.push_to_output_stream(object)
            elif object.type == ControlCommand.CommandType.EndTag:
                if self.state.in_string_evaluation:
                    content_stack_for_tag = []
                    output_count_consumed = 0

                    for content in self.state.output_stream:
                        output_count_consumed += 1

                        if isinstance(content, ControlCommand):
                            if not content.type == ControlCommand.CommandType.BeginTag:
                                self.add_error(
                                    "Unexpected ControlCommand while extracting "
                                    f"tag from choice: {content.type.value}"
                                )
                            break

                        if isinstance(content, StringValue):
                            content_stack_for_tag.append(content)

                    self.state.pop_from_output_stream(output_count_consumed)

                    text = "".join(c.value for c in content_stack_for_tag)
                    choice_tag = Tag(self.state.clean_output_whitespace(text))

                    self.state.push_evaluation_stack(choice_tag)
                else:
                    self.state.push_to_output_stream(object)
            elif object.type == ControlCommand.CommandType.EndString:
                content_stack = []
                content_to_retain = []

                output_count_consumed = 0
                for content in reversed(self.state.output_stream):
                    output_count_consumed += 1

                    if (
                        isinstance(content, ControlCommand)
                        and content.type == ControlCommand.CommandType.BeginString
                    ):
                        break

                    if isinstance(content, Tag):
                        content_to_retain.append(content)
                    elif isinstance(content, StringValue):
                        content_stack.append(content)

                self.state.pop_from_output_stream(output_count_consumed)

                for tag in content_to_retain:
                    self.state.push_to_output_stream(tag)

                text = "".join(c.value for c in content_stack)
                self.state.in_expression_evaluation = True
                self.state.push_evaluation_stack(StringValue(text))

            elif object.type == ControlCommand.CommandType.ChoiceCount:
                choice_count = len(self.state.generated_choices)
                self.state.push_evaluation_stack(IntValue(choice_count))
            elif object.type == ControlCommand.CommandType.Turns:
                turn_index = self.state.current_turn_index + 1
                self.state.push_evaluation_stack(IntValue(turn_index))
            elif object.type in (
                ControlCommand.CommandType.TurnsSince,
                ControlCommand.CommandType.ReadCount,
            ):
                target = self.state.pop_evaluation_stack()
                if not isinstance(target, DivertTargetValue):
                    message = (
                        "TURNS_SINCE expected a divert target (knot, stitch, label name), but saw "
                        f"{target}"
                    )

                    if isinstance(target, IntValue):
                        message += (
                            ". Did you accidentally pass a read count ('knot_name') instead of a "
                            "target ('-> knot_name')?"
                        )

                    raise StoryException(message)

                container = self.content_at_path(target.target_path).correct_obj

                if isinstance(container, Container):
                    if object.type == ControlCommand.CommandType.TurnsSince:
                        count = self.state.turns_since_for_container(container)
                    elif object.type == ControlCommand.CommandType.ReadCount:
                        count = self.state.visit_count_for_container(container)
                else:
                    if object.type == ControlCommand.CommandType.TurnsSince:
                        count = -1  # turn count, default to never/unknown
                    else:
                        count = 0  # visit count, assume 0

                    self.add_warning(
                        f"Failed to find container for {object.type} lookup at "
                        f"{target.target_path}"
                    )

                self.state.push_evaluation_stack(IntValue(count))

            elif object.type == ControlCommand.CommandType.Random:
                max_int = self.state.pop_evaluation_stack()
                min_int = self.state.pop_evaluation_stack()

                if min_int is None:
                    raise StoryException(
                        "Invalid value for minimum parameter of RANDOM(min, max): "
                        f"{min_int}"
                    )

                if max_int is None:
                    raise StoryException(
                        "Invalid value for maximum parameter of RANDOM(min, max): "
                        f"{max_int}"
                    )

                rand_range = max_int.value - min_int.value + 1
                if -(2**31 - 1) >= rand_range >= (2**31 - 1):
                    raise StoryException(
                        "RANDOM was called with a range that exceeds the size that ink "
                        f"numbers can use: {min_int.value} <-> {max_int.value}"
                    )

                if min_int >= max_int:
                    raise StoryException(
                        f"RANDOM was called with minimum as {min_int.value} and "
                        f"maximum as {max_int.value}. The maximum must be larger."
                    )

                seed = self.state.story_seed + self.state.previous_random
                rand = random.Random(seed)
                next_rand = rand.randint(0, 2**31 - 1)
                rand_value = next_rand % rand_range + min_int.value

                self.state.push_evaluation_stack(IntValue(rand_value))
                self.state.previous_random = next_rand

            elif object.type == ControlCommand.CommandType.SeedRandom:
                seed = self.state.pop_evaluation_stack()
                if not isinstance(seed, IntValue):
                    raise StoryException("Invalid value passed to SEED_RANDOM")

                self.state.story_seed = seed.value
                self.state.previous_random = 0

                self.state.push_evaluation_stack(Void())

            elif object.type == ControlCommand.CommandType.VisitIndex:
                current_container = self.state.current_pointer.container
                count = self.state.visit_count_for_container(current_container) - 1

                self.state.push_evaluation_stack(IntValue(count))

            elif object.type == ControlCommand.CommandType.SequenceShuffleIndex:
                shuffle_index = self.next_sequence_shuffle_index()
                self.state.push_evaluation_stack(IntValue(shuffle_index))

            elif object.type == ControlCommand.CommandType.StartThread:
                pass  # handled in main step function

            elif object.type == ControlCommand.CommandType.Done:
                if self.state.call_stack.can_pop_thread:
                    self.state.call_stack.pop_thread()
                else:
                    self.did_safe_exit = True
                    self.state.current_pointer = None

            elif object.type == ControlCommand.CommandType.End:
                self.state.force_end()
            # elif object.type == ControlCommand.CommandType.ListFromInt:
            #     raise Exception(object.type)
            # elif object.type == ControlCommand.CommandType.ListRange:
            #     raise Exception(object.type)
            # elif object.type == ControlCommand.CommandType.ListRandom:
            #     raise Exception(object.type)
            else:
                self.add_error(f"Unhandled control command: {object.type}")

            return True

        elif isinstance(object, VariableAssignment):
            value = self.state.pop_evaluation_stack()

            # when in temporary evaluation, don't create new variables purely
            # within the temporary content, but attempt to create them globally

            self.state.variables_state.assign(object, value)

            return True

        elif isinstance(object, VariableReference):
            # Explicit read count value
            if object.path_for_count:
                container = object.container_for_count
                count = self.state.visit_count_for_container(container)
                value = IntValue(count)

            # Normal variable reference
            else:
                value = self.state.variables_state.get_variable_with_name(object.name)

                if value is None:
                    self.add_warning(
                        f"Variable not found: '{object.name}'. Using default value of 0 "
                        "(false). This can happen with temporary variables if "
                        "the declaration hasn't yet been hit. Globals are always "
                        "given a default value on load if a value doesn't exist "
                        "in the save state."
                    )

            self.state.push_evaluation_stack(value)

            return True

        elif isinstance(object, NativeFunctionCall):
            params = self.state.pop_evaluation_stack(object.number_of_parameters)
            result = object.call(params)
            self.state.push_evaluation_stack(result)
            return True

        # No control content, must be ordinary content
        return False

    def pointer_at_path(self, path: Path) -> t.Optional[Pointer]:
        if len(path) == 0:
            return

        path_length_to_use = len(path)

        if path.last_component.is_index:
            path_length_to_use = len(path) - 1
            result = self.main_content_container.content_at_path(
                path, length=path_length_to_use
            )
            pointer = Pointer(result.container, path.last_component.index)
        else:
            result = self.main_content_container.content_at_path(path)
            pointer = Pointer(result.container, -1)

        if (
            not result.obj
            or result.obj == self.main_content_container
            and path_length_to_use > 0
        ):
            self.add_error(
                f"Failed to find content at path '{path}', and no approximation "
                "of it was possible."
            )
        elif result.approximate:
            self.add_warning(
                f"Failed to find content at path '{path}', so it was approximated "
                f"to: '{result.obj.path}'"
            )

        return pointer

    def pop_choice_string_and_tags(self):
        tags = []
        choice_only_string_value = self.state.pop_evaluation_stack()

        while len(self.state.evaluation_stack) > 1 and isinstance(
            self.state.peek_evaluation_stack(), Tag
        ):
            tag = self.state.pop_evaluation_stack()
            tags.insert(0, tag.text)

        return choice_only_string_value.value, tags

    def process_choice(self, choice_point: ChoicePoint) -> Choice:
        show_choice = True

        if choice_point.has_condition:
            value = self.state.pop_evaluation_stack()
            if not self.is_truthy(value):
                show_choice = False

        start_text = ""
        choice_only_text = ""
        tags = []

        if choice_point.has_choice_only_content:
            choice_only_text, tags = self.pop_choice_string_and_tags()

        if choice_point.has_start_content:
            start_text, tags = self.pop_choice_string_and_tags()

        if choice_point.once_only:
            visit_count = self.state.visit_count_for_container(
                choice_point.choice_target
            )
            if visit_count > 0:
                show_choice = False

        if not show_choice:
            return

        choice = Choice()
        choice.target_path = choice_point.path_on_choice
        choice.source_path = str(choice_point.path)
        choice.is_invisible_default = choice_point.is_invisible_default
        choice.tags = tags

        choice.thread_at_generation = self.state.call_stack.fork_thread()

        choice.text = (start_text + choice_only_text).strip(" ").strip("\t")

        return choice

    @contextmanager
    def profile(self):
        """Profile the calls wrapped by this context manager."""
        profiler = self.start_profiling()

        try:
            yield profiler
        finally:
            self.end_profiling()

    def reset_callstack(self):
        """Unwinds the callstack to reset story evaluation without changing state."""
        self.if_async_we_cant("reset callstack")

        self._state.force_end()

    def reset_errors(self):
        self._state.reset_errors()

    def reset_globals(self):
        """Reset global variables back to their initial defaults."""
        if self._main_content_container.named_content.get("global decl"):
            original_pointer = self._state.current_pointer.copy()

            self.choose_path(Path("global decl"), False)

            self._continue()

            self._state.current_pointer = original_pointer

        self._state.variables_state.snapshot_default_globals()

    def reset_state(self):
        """Reset the story back to the initial starting state."""
        self.if_async_we_cant("reset state")

        self._state = State(self)

        # TODO: add variable observers

        self.reset_globals()

    def restore_state_snapshot(self):
        self._state_snapshot_at_last_newline.restore_after_patch()

        self._state = self._state_snapshot_at_last_newline
        self._state_snapshot_at_last_newline = None

        if not self._async_saving:
            self._state.apply_any_patch()

    def start_profiling(self):
        """Start recording ink profiling information for this story.

        You can call the :meth:`inkpy.runtime.profiler.Profiler.report` method on the
        profiler to generate a report or examine the attributes for profiling
        information.

        :returns: a profiler instance you can examine for profiling information.
        :rype: inkpy.runtime.profiler.Profiler

        """
        self.if_async_we_cant("start profiling")
        self._profiler = Profiler()
        return self._profiler

    @property
    def state(self) -> State:
        """The entire current state of the story.

        Including but not limited to:

        * Glboal variables
        * Temporary variables
        * Read/visit and turn counts
        * Callstack and evaluation stacks
        * Current threads

        """
        return self._state

    def state_snapshot(self):
        self._state_snapshot_at_last_newline = self._state
        self._state = self._state.copy_and_start_patching()

    def step(self):
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

        if self._profiler:
            self._profiler.step(self.state.call_stack)

        current_content = pointer.resolve()
        is_logic_or_flow_control = self.perform_logic_and_flow_control(current_content)

        # has flow been forced to end by flow control above?
        if not self.state.current_pointer:
            return

        if is_logic_or_flow_control:
            should_add_to_stream = False

        # choice with condition?
        if isinstance(current_content, ChoicePoint):
            choice = self.process_choice(current_content)
            if choice:
                self.state.generated_choices.append(choice)

            current_content = None
            should_add_to_stream = False

        # if container has no content, then it will be "content" but we'll skip it
        if isinstance(current_content, Container):
            should_add_to_stream = False

        # content to add to evaluation stack or output stream
        if should_add_to_stream:
            if (
                isinstance(current_content, VariablePointerValue)
                and current_content.index == -1
            ):
                index = self.state.call_stack.context_for_variable_named(
                    current_content.variable_name
                )
                current_content = VariablePointerValue(
                    current_content.variable_name, index
                )

            if self.state.in_expression_evaluation:
                self.state.push_evaluation_stack(current_content)
            else:
                self.state.push_to_output_stream(current_content)

        # increment the content pointer, follow diverts?
        self.next_content()

        if isinstance(current_content, ControlCommand):
            if current_content.type == ControlCommand.CommandType.StartThread:
                self.state.call_stack.push_thread()

    @contextmanager
    def suspend_profiling(self):
        """Temporary suspend recording of ink profiling information for this story.

        :raises:
            RuntimeError: story is not currently profiling.

        """
        if profiler := self._profiler:
            self._profiler = None
        else:
            raise RuntimeError("Story is not currently profiling")

        try:
            yield
        finally:
            self._profiler = profiler

    def to_json(self, output: t.Optional[t.TextIO] = None) -> t.Optional[str]:
        """Return JSON representation of the story."""
        compiler = JSONCompiler()
        return compiler.compile(self, output)

    def try_follow_default_invisible_choice(self) -> bool:
        choices = self.state.current_choices

        invisible_choices = [c for c in choices if c.is_invisible_default]
        if not invisible_choices or len(choices) > len(invisible_choices):
            return False

        choice = invisible_choices[0]

        self.state.call_stack.current_thread = choice.thread_at_generation
        if self._state_snapshot_at_last_newline:
            self.state.call_stack.current_thread = self.state.call_stack.fork_thread()

        self.choose_path(choice.target_path, incrementing_turn_index=False)

        return True

    def validate_external_bindings(
        self,
        container: Container | None = None,
        object: InkObject | None = None,
        missing: set | None = None,
    ):
        """Check all EXTERNAL ink functions have a valid bound Python function.

        This is called automatically on the first call to :meth:`continue_()`.

        """
        if missing is not None:
            missing = set()

        if not container and not object:
            self.validate_external_bindings(
                self._main_content_container, missing=missing
            )

            self._has_validated_externals = True

            if not missing:
                self._has_validated_externals = True
            else:
                message = "Missing function binding(s) for external(s): '"
                message += "', '".join(missing)

                if self.allow_external_function_fallbacks:
                    message += "' (ink fallbacks disabled)"
                else:
                    message += "', and no fallback ink function(s) found."

                raise StoryException(message)
        elif container:
            pass
        elif object:
            pass

    def visit_container(self, container: Container, at_start: bool):
        if not container.count_at_start_only or at_start:
            if container.visits_should_be_counted:
                self.state.increment_visit_count_for_container(container)

            if container.turn_index_should_be_counted:
                self.state.record_turn_index_visit_to_container(container)

    def visit_changed_containers_due_to_divert(self):
        previous_pointer = self.state.previous_pointer
        pointer = self.state.current_pointer

        if not pointer or pointer.index == -1:
            return

        pointer = pointer.copy()
        if previous_pointer:
            previous_pointer = previous_pointer.copy()

        self._prev_containers = []
        if previous_pointer:
            ancestor = previous_pointer.resolve()
            if not isinstance(ancestor, Container):
                ancestor = previous_pointer.container
            while isinstance(ancestor, Container):
                self._prev_containers.append(ancestor)
                ancestor = ancestor.parent

        current_child = pointer.resolve()
        if not current_child:
            return

        current_ancestor = current_child.parent
        all_children_entered_at_start = True

        while isinstance(current_ancestor, Container) and (
            current_ancestor not in self._prev_containers
            or current_ancestor.count_at_start_only
        ):
            entering_at_start = (
                len(current_ancestor.content) > 0
                and current_child == current_ancestor.content[0]
                and all_children_entered_at_start
            )

            if not entering_at_start:
                all_children_entered_at_start = False

            self.visit_container(current_ancestor, entering_at_start)

            current_child = current_ancestor
            current_ancestor = current_ancestor.parent
