import json
import typing as t
import warnings

from collections import defaultdict
from contextlib import contextmanager

import json_stream

from ..parser.json import JsonParser
from .container import Container
from .list_definition import ListDefinition
from .profiler import Profiler
from .state import State


class ExternalFunctionDefinition:
    def __init__(self, function: t.Callable, lookahead_safe: bool = True):
        self.function = function
        self.lookahead_safe = lookahead_safe

    def __call__(self, *args):
        return self.function(*args)


class Story:
    def __init__(self, input: str | t.TextIO):
        self.external_functions: dict[str, ExternalFunctionDefinition] = {}
        self.observers: dict[str, list[t.Callable]] = defaultdict(list)

        parser = JsonParser()
        root, list_definitions = parser.parse(input)

        self._has_validated_externals = False
        self.list_definitions: list[ListDefinition] = list_definitions
        self._main_content_container: Container = root

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
        if not self._has_validated_externals:
            self.validate_external_bindings()

        return

    def continue_maximally(self) -> t.Generator[str, None, None]:
        while self.can_continue:
            yield self.continue_()

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

    def validate_external_bindings(self):
        self._has_validated_externals = True
