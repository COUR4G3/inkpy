import logging
import typing as t

from collections import defaultdict
from contextlib import contextmanager

from ..parser.json import JsonParser
from .choice_point import ChoicePoint
from .container import Container
from .control_command import ControlCommand
from .divert import Divert
from .exceptions import StoryException
from .list_definition import ListDefinition
from .native_function_call import NativeFunctionCall
from .object import InkObject
from .path import Path
from .pointer import Pointer
from .profiler import Profiler
from .push_pop import PushPopType
from .state import State
from .tag import Tag
from .value import VariablePointerValue
from .variable_assignment import VariableAssignment
from .variable_reference import VariableReference


logger = logging.getLogger()


class ExternalFunctionDefinition:
    def __init__(self, function: t.Callable, lookahead_safe: bool = True):
        self.function = function
        self.lookahead_safe = lookahead_safe

    def __call__(self, *args):
        return self.function(*args)


class Story(InkObject):
    def __init__(self, input: str | t.TextIO):
        super().__init__()

        self.allow_external_function_callbacks = True
        self.external_functions: dict[str, ExternalFunctionDefinition] = {}
        self.observers: dict[str, list[t.Callable]] = defaultdict(list)

        parser = JsonParser()
        root, list_definitions = parser.parse(input)

        self._has_validated_externals = False
        self.list_definitions: list[ListDefinition] = list_definitions
        self._main_content_container: Container = root

        self._on_did_continue = None
        self._on_error = None
        self._profiler: t.Optional[Profiler] = None
        self._recursive_continue_count: int = 0
        self._saw_lookahead_unsafe_function_after_newline: bool = False
        self._state_snapshot_at_last_newline: t.Optional[State] = None

        self.reset_state()

    def add_error(self, message: str):
        self.state.errors.append(message)
        logger.error(message)

    def add_warning(self, message: str):
        self.state.warnings.append(message)
        logger.warning(message)

    def bind_external_function(
        self, name: str, f: t.Callable = None, lookahead_safe: bool = True
    ):
        def decorator(f):
            self.external_functions[name] = ExternalFunctionDefinition(
                f, lookahead_safe=lookahead_safe
            )
            return f

        return f and decorator(f) or decorator

    @property
    def can_continue(self) -> bool:
        return self.state.can_continue

    def choose_path(self, path: Path, incrementing_turn_index: bool = True):
        self.state.set_chosen_path(path, incrementing_turn_index)
        self.visit_changed_containers_due_to_divert()

    def continue_(self) -> str:
        if not self._has_validated_externals:
            self.validate_external_bindings()

        self._continue()

        return self.current_text

    def _continue(self):
        if self._profiler:
            self._profiler.pre_continue()

        self._recursive_continue_count += 1

        if not self.can_continue:
            raise RuntimeError(
                "Can't continue - should check can_continue before calling continue_"
            )

        self.state.did_safe_exit = False
        self.state.reset_output()

        # batch observers for the outermost call
        if self._recursive_continue_count == 1:
            self.state.variables_state.batch_observing_variable_changes = True

        output_stream_ends_in_newline = False
        self._saw_lookahead_unsafe_function_after_newline = False

        while self.can_continue:
            try:
                output_stream_ends_in_newline = self.continue_single_step()
            except StoryException as e:
                self.add_error(e.message, use_end_line_number=e.use_end_line_number)
                break

            if output_stream_ends_in_newline:
                break

        if output_stream_ends_in_newline or not self.can_continue:
            # TODO: need to rewind
            # TODO: check if finished a section of content or reached choice point

            self.state.did_safe_exit = False
            self._saw_lookahead_unsafe_function_after_newline = False

            if self._recursive_continue_count == 1:
                self.state.variables_state.batch_observing_variable_changes = False

            if self._on_did_continue:
                self._on_did_continue()

        self._recursive_continue_count -= 1

        if self._profiler:
            self._profiler.post_continue()

        # report any errors that occured during evaluation
        if self.state.has_error or self.state.has_warning:
            # use on_error handler or throw an exception
            if self._on_error:
                for error in self.state.errors:
                    self._on_error(error)
                for warning in self.state.warnings:
                    self._on_error(warning, True)

                self.reset_errors()
            else:
                if self.state.has_error:
                    first_issue = self.state.errors[0]
                else:
                    first_issue = self.state.warnings[0]

                message = (
                    f"Ink had {len(self.state.errors)} error(s) and "
                    f"{len(self.state.warnings)} warning(s). It is strongly "
                    "suggested you assign an error handler with story.on_error. "
                    f"The first issue was: {first_issue}"
                )

                raise StoryException(message)

    def continue_maximally(self) -> t.Generator[str, None, None]:
        while self.can_continue:
            yield self.continue_()

    def continue_single_step(self) -> bool:
        if self._profiler:
            self._profiler.pre_step()

        self.step()

        if self._profiler:
            self._profiler.post_step()

        if (
            not self.can_continue
            and not self.state.call_stack.element_is_evaluate_from_game
        ):
            self.try_follow_default_invisible_choice()

        if self._profiler:
            self._profiler.pre_snapshot()

        # don't save/rewind during string evaluation i.e. during choices
        if not self.state.in_string_eval:
            # we previously found a new line, but we need to double check that it wasn't
            # removed by glue
            if self._state_snapshot_at_last_newline:
                # has proper text or a tag been added? then we know that the newline
                # previously added is definitely the end of the line
                change = self.calculate_newline_output_state_change(
                    self._state_snapshot_at_last_newline.current_text,
                    self.state.current_text,
                    len(self._state_snapshot_at_last_newline.current_tags),
                    len(self.state.current_tags),
                )

                # the last time we saw a newline, it was definitely the end of the line,
                # so we want to rewind to that point.
                if (
                    change == OutputStateChange.ExtendedBeyondNewline
                    or self._saw_lookahead_unsafe_function_after_newline
                ):
                    self.restore_state_snapshot()

                    # hit newline for sure, we're done!
                    return True

                # newline was removed e.g. glue was encountered
                elif change == OutputStateChange.NewlineRemoved:
                    self.discard_snapshot()

            # current context ends in newline - approaching end of evaluation
            if self.state.output_stream_ends_in_newline:
                # if we can continue evaluation for a bit, create a snapshot in case
                # we need to rewind. we are looking for glue or some non-text content
                if self.can_continue:
                    if not self._state_snapshot_at_last_newline:
                        self.state_snapshot()

                # can't continue, so we're going to exit and get rid of snapshot
                else:
                    self.discard_snapshot()

        if self._profiler:
            self._profiler.post_snapshot()

        return False

    @property
    def current_text(self):
        return self.state.current_text

    def end_profiling(self):
        self._profiler = None

    @property
    def has_error(self) -> bool:
        return self.state.has_error

    @property
    def has_warning(self) -> bool:
        return self.state.has_warning

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

    @property
    def main_content_container(self) -> Container | None:
        return self._main_content_container

    def next_content(self):
        self.state.previous_pointer = self.state.current_pointer

        if self.state.diverted_pointer:
            self.state.current_pointer = self.state.diverted_pointer
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
                if self.state.in_expression_eval:
                    self.state.push_eval_stack(Void())

                did_pop = True
            elif self.state.call_stack.can_pop_thread:
                self.state.call_stack.pop_thread()

                did_pop = True
            else:
                self.state.try_exit_function_eval_from_game()

            if did_pop and self.state.current_pointer:
                self.next_content()

    def observe(self, name: str, f: t.Callable[[str, t.Any], None] = None):
        if name not in self.state.variables_state:
            raise Exception("")

        def decorator(f):
            self.observers[name].append(f)
            return f

        return f and decorator(f) or decorator

    def observes(self, *names: str, f: t.Callable[[str, t.Any], None] = None):
        def decorator(f):
            for name in names:
                self.observe(name, f)
            return f

        return f and decorator(f) or decorator

    def perform_logic_and_flow_control(self, object: InkObject) -> bool:
        logger.debug("perform_logic_and_flow_control: %s", object)

        if isinstance(object, Divert):
            if object.is_conditional:
                condition_value = self.state.pop_eval_stack()

                if not self.is_truthy(condition_value):
                    return True

            if object.has_variable_target:
                name = object.variable_divert_name
                content = self.state.variables_state.get(name)

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
                if object and object.debug.source:
                    self.add_error(
                        f"Divert target doesn't exist: {object.debug.source}"
                    )
                else:
                    self.add_error(f"Divert resolution failed: {object}")

            return True

        elif isinstance(object, ControlCommand):
            if object.type == ControlCommand.CommandType.EvalStart:
                assert (
                    not self.state.in_expression_eval
                ), "Already in expression evaluation"
                self.state.in_expression_eval = True
            elif object.type == ControlCommand.CommandType.EvalEnd:
                assert self.state.in_expression_eval, "Not in expression evaluation"
                self.state.in_expression_eval = False
            elif object.type == ControlCommand.CommandType.EvalOutput:
                if self.state.eval_stack:
                    output = self.state.pop_eval_stack()
                    if output:
                        text = StringValue(output)
                        self.state.push_to_output_stream(text)
            elif object.type == ControlCommand.CommandType.NoOp:
                pass
            elif object.type == ControlCommand.CommandType.Duplicate:
                self.state.push_eval_stack(self.state.peek_eval_stack())
            elif object.type == ControlCommand.CommandType.PopEvaluatedValue:
                self.state.pop_eval_stack()
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
                    value = self.state.pop_eval_stack()
                    if isinstance(value, DivertTargetvalue):
                        override_tunnel_return_target = value
                    else:
                        assert (
                            value == Void()
                        ), "Expected void if ->-> doesn't override target"

                if self.state.try_exit_function_evaluation_from_game():
                    pass
                elif (
                    self.state.call_stack.current_element.type != pop_type
                    or self.state.call_stack.can_pop()
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
                    self.state.in_expression_eval
                ), "Expected to be in an expression evaluating a string"
                self.state.in_expression_eval = False
            elif object.type == ControlCommand.CommandType.BeginTag:
                self.state.push_to_output_stream(object)
            elif object.type == ControlCommand.CommandType.EndTag:
                if self.state.in_string_eval:
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

                    self.state.push_eval_stack(choice_tag)
                else:
                    self.state.push_to_output_stream(object)
            elif object.type == ControlCommand.CommandType.EndString:
                raise Exception(object.type)
            elif object.type == ControlCommand.CommandType.ChoiceCount:
                raise Exception(object.type)
            elif object.type == ControlCommand.CommandType.Turns:
                raise Exception(object.type)
            elif object.type == ControlCommand.CommandType.TurnsSince:
                raise Exception(object.type)
            elif object.type == ControlCommand.CommandType.ReadCount:
                raise Exception(object.type)
            elif object.type == ControlCommand.CommandType.Random:
                raise Exception(object.type)
            elif object.type == ControlCommand.CommandType.SeedRandom:
                raise Exception(object.type)
            elif object.type == ControlCommand.CommandType.VisitIndex:
                raise Exception(object.type)
            elif object.type == ControlCommand.CommandType.SequenceShuffleIndex:
                raise Exception(object.type)
            elif object.type == ControlCommand.CommandType.StartThread:
                raise Exception(object.type)
            elif object.type == ControlCommand.CommandType.Done:
                raise Exception(object.type)
            elif object.type == ControlCommand.CommandType.End:
                raise Exception(object.type)
            elif object.type == ControlCommand.CommandType.ListFromInt:
                raise Exception(object.type)
            elif object.type == ControlCommand.CommandType.ListRange:
                raise Exception(object.type)
            elif object.type == ControlCommand.CommandType.ListRandom:
                raise Exception(object.type)
            else:
                self.add_error(f"Unhandled control command: {object.type}")

            return True

        elif isinstance(object, VariableAssignment):
            value = self.state.pop_eval_stack()

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

            self.state.push_eval_stack(value)

            return True

        elif isinstance(object, NativeFunctionCall):
            params = self.state.pop_eval_stack(object.number_of_parameters)
            result = object.call(params)
            self.state.push_eval_stack(result)
            return True

        # No control content, must be ordinary content
        return False

    @contextmanager
    def profile(self):
        self.start_profiling()

        try:
            yield
        finally:
            self.end_profiling()

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

    def remove_flow(self, name: str):
        self.state._remove_flow(name)

    def reset_callstack(self):
        self.state.force_end()

    def reset_errors(self):
        self.state.reset_errors()

    def reset_globals(self):
        if "global decl" in self._main_content_container.named_content:
            original_pointer = self.state.current_pointer

            self.choose_path(Path("global decl"), incrementing_turn_index=False)

            self._continue()

            self.state.current_pointer = original_pointer

        self.state.variables_state.snapshot_default_variables()

    def reset_state(self):
        self.state = State(self)

        self.reset_globals()

    def start_profiling(self):
        self._profiler = Profiler()

    def state_snapshot(self):
        self._state_snapshot_at_newline = self.state
        self.state = self.state.copy_and_start_patching()

    def step(self):
        should_add_to_stream = True

        # get current content
        pointer = self.state.current_pointer
        if not pointer:
            return

        # step to first element of content in container
        container = pointer.resolve()
        while isinstance(container, Container):
            # mark container as being entered
            self.visit_container(container, at_start=True)

            # no content - step past it
            if len(container.content) == 0:
                break

            pointer = Pointer.start_of(container)
            container = pointer.resolve()

        self.state.current_pointer = pointer

        if self._profiler:
            self._profiler.step(self.state.call_stack)

        current_object = pointer.resolve()
        is_logic_or_flow_control = self.perform_logic_and_flow_control(current_object)

        # has flow eneded?
        if not self.state.current_pointer:
            return

        if is_logic_or_flow_control:
            should_add_to_stream = False

        # choice with condition?
        if isinstance(current_object, ChoicePoint):
            choice = self.process_choice(current_object)
            if choice:
                self.state.generated_choices.append(choice)

            current_object = None
            should_add_to_stream = False

        # skip over container
        if isinstance(current_object, Container):
            should_add_to_stream = False

        # content to add to evaluation stack or output
        if should_add_to_stream:
            # if we're pushing a variable pointer onto the evaluation stack, ensure the
            # index is set to our current temporary content index and make a copy
            if (
                isinstance(current_object, VariablePointerValue)
                and current_object.index == -1
            ):
                # create a new pointer so we don't overwrite story data
                index = self.state.call_stack.context_for_variable_named(
                    current_object.variable_name
                )
                current_object = VariablePointerValue(
                    current_object.variable_name, index
                )

            if self.state.in_expression_eval:
                self.state.push_eval_stack(current_object)
            else:
                self.state.push_to_output_stream(current_object)

        self.next_content()

        if (
            isinstance(current_object, ControlCommand)
            and current_object.type == ControlCommand.CommandType.StartThread
        ):
            self.state.call_stack.push_thread()

    def switch_flow(self, name: str):
        self.state._switch_flow(name)

    def switch_to_default_flow(self):
        self.state._switch_to_default_flow()

    def try_follow_default_invisible_choice(self) -> bool:
        logger.debug("try_follow_default_invisible_choice")

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

    def unbind_external_function(self, name: str):
        del self.external_functions[name]

    def validate_external_bindings(
        self,
        container: t.Optional[Container] = None,
        object: t.Optional[InkObject] = None,
        missing: t.Optional[set[str]] = None,
    ):
        if missing is None:
            missing = set()

        if container:
            for content in container.content:
                if not isinstance(content, Container):
                    continue
                self.validate_external_bindings(container=content, missing=missing)
            for value in container.named_content.values():
                if not isinstance(value, InkObject):
                    continue
                self.validate_external_bindings(object=value, missing=missing)
        elif object:
            if not isinstance(object, Divert) or not object.is_external:
                return

            name = object.target_path_string

            if name not in self.external_functions:
                if self.allow_external_function_callbacks:
                    if name not in self.main_content_container.named_content:
                        missing.add(name)
                else:
                    missing.add(name)
        else:
            self.validate_external_bindings(
                container=self._main_content_container, missing=missing
            )

            self._has_validated_externals = True

            if missing:
                message = f"Missing function binding(s) for external(s): '"
                message += "', '".join(missing)
                message += "'"

                if self.allow_external_function_callbacks:
                    message += ", and no fallback ink function(s) found."
                else:
                    message += " (ink function fallbacks disabled)"

                self.add_error(message)

    def visit_container(self, container: Container, at_start: bool):
        logger.debug("Visited container %s", container)

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
