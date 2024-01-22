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
from .object import InkObject
from .pointer import Pointer
from .profiler import Profiler
from .state import State
from .value import VariablePointerValue


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

        self.reset_state()

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

    def continue_(self) -> str:
        self._continue()
        return self.current_text

    def _continue(self):
        if not self._has_validated_externals:
            self.validate_external_bindings()

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
                message = ""

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

        return True

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

    @property
    def main_content_container(self) -> Container | None:
        return self._main_content_container

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

    @contextmanager
    def profile(self):
        self.start_profiling()

        try:
            yield
        finally:
            self.end_profiling()

    def remove_flow(self, name: str):
        self.state._remove_flow(name)

    def reset_callstack(self):
        self.state.force_end()

    def reset_errors(self):
        self.state.reset_errors()

    def reset_globals(self):
        return

    def reset_state(self):
        self.state = State(self)

        self.reset_globals()

    def start_profiling(self):
        self._profiler = Profiler()

    def step(self):
        should_add_to_stream = True

        # get current content
        pointer = self.state.current_pointer
        if not pointer:
            return

        # step to first element of content in container
        container = pointer.resolve()
        while container:
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
        is_logic_or_flow_control = self.perform_login_and_flow_control(current_object)

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
        choices = self.state.current_choices

        invisible_choices = [c for c in choices if c.is_invisible_default]
        if not invisible_choices and len(choices) > len(invisible_choices):
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
