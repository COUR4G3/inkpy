import typing as t

from .choice import Choice
from .state import State


class Story:
    ink_version_current = 21
    ink_version_minimum_compatible = 18

    def __init__(self, name: t.Optional[str | t.TextIO] = None):
        self.name = name

        self.root = None

        self.external_functions: dict[str, t.Callable] = {}
        self.state = State(self)

    def __iter__(self):
        while self.can_continue:
            yield self.continue_()

    def bind_external_function(self, name: str, f: t.Callable = None):
        def decorator(f):
            self.external_functions[name] = f
            return f

        return f and decorator(f) or decorator

    @property
    def can_continue(self) -> bool:
        return self.state.can_continue

    def continue_(self):
        return

    def continue_maximally(self):
        return

    @property
    def choices(self) -> list[Choice]:
        return self.state.choices

    def choose(self, choice: Choice | int):
        if isinstance(choice, int):
            choice = self.choices[choice]

    def choose_choice(self, choice: Choice | int):
        return self.choose(choice)

    def choose_path_string(self, path: str):
        return self.goto(path)

    @property
    def current_choices(self) -> list[Choice]:
        return self.choices

    def external_function(self, name: str):
        return self.bind_external_function(name)

    def force_end(self):
        return

    def goto(self, path: str):
        return

    def load(self, name: str | t.TextIO):
        return

    def observe(self, name: str, f: t.Callable[[str, t.Any], None] = None):
        def decorator(f):
            self.observers[name].append(f)
            return f

        return f and decorator(f) or decorator

    def observe_variable(self, name: str, f: t.Callable[[str, t.Any], None] = None):
        return self.observe(name, f=f)

    @property
    def observers(self) -> dict[str, list[t.Callable[[str, t.Any], None]]]:
        return self.state.globals.observers

    def observes(self, *names: str, f: t.Callable[[str, t.Any], None] = None):
        def decorator(f):
            for name in names:
                self.observers[name].append(f)
            return f

        return f and decorator(f) or decorator

    def reload(self, name: str | t.TextIO = None, reset: bool = False):
        if not name:
            name = self.name
            if isinstance(name, t.TextIO):
                name.seek(0)

        self.load(name)

        if reset:
            self.reset_state()

    def remove_flow(self, name: str):
        self.state._remove_flow(name)

    def reset_callstack(self):
        self.state.force_end()

    def reset_errors(self):
        self.state.reset_errors()

    def reset_globals(self):
        if "global decl" in self.root.named_content:
            original_pointer = self.state.current_pointer

            # self.choose_path(Path("global decl", incrementing_turn_index=False))
            # continue_internal

            self.state.current_pointer = original_pointer

        self.state.globals.snapshot_default_globals()

    def reset_state(self):
        self.state = State(self)
        # TODO: handle?
        # self.state.globals.variable_changed_event += VariableStateDidChangeEvent

        self.reset_globals()

    def reset_warnings(self):
        self.state.reset_warnings()

    def switch_flow(self, name: str):
        self.state._switch_flow(name)

    def switch_to_default_flow(self):
        self.state._switch_to_default_flow()

    def to_dict(self) -> dict:
        return

    def to_json(self) -> str:
        return

    @property
    def variables(self) -> dict[str, t.Any]:
        return self.state.globals
