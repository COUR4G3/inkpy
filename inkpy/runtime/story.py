import typing as t

from collections import defaultdict
from contextlib import contextmanager

from ..parser.json import JsonParser
from .container import Container
from .divert import Divert
from .list_definition import ListDefinition
from .object import InkObject
from .profiler import Profiler
from .state import State


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
                "Can't continue - should chdck can_continue before calling continue_"
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
                output_stream_ends_in_newline = self._continue_single_step()
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

    def _continue_single_step(self) -> bool:
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

    def switch_flow(self, name: str):
        self.state._switch_flow(name)

    def switch_to_default_flow(self):
        self.state._switch_to_default_flow()

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
