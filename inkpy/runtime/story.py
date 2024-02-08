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
        self.allow_external_function_fallbacks = True

        self._evaluation_content_container: Container | None = None
        self._externals: dict[str, ExternalFunction] = {}
        self._observers: dict[str, list[typing.Observer]] = defaultdict(list)
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

    def choose_path(self, path: Path):
        return

    def choose_path_string(self, path: str):
        return

    def continue_(self):
        return

    def continue_maximally(self) -> t.Generator[None, None, str]:
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
        """Reset all errors and warnings from execution."""
        self.state.reset_errors()

    def reset_globals(self):
        """Reset global variables back to their initial defaults."""

        if "global decl" in self.root_content_container.named_content:
            original_pointer = self.state.current_pointer

            self.choose_path(Path("global decl"))
            self.continue_()

            self.state.current_pointer = original_pointer

        self.state.variables_state.snapshot_default_globals()

    def reset_state(self):
        """Reset story back to its initial state."""

        self.state = State(self)
        self.reset_globals()

    def unbind_external_function(self, name: str):
        """Unbind a previously bound external function."""
        del self._externals[name]

    def validate_external_bindings(
        self, obj: Container | InkObject | None = None, missing: set | None = None
    ):
        """Validate all external functions are bound (or there are fallbacks)."""
        if missing_externals is None:
            missing_externals = set()

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

        else:
            raise ExternalBindingsValidationError(
                missing, self.allow_external_function_fallbacks
            )


class ExternalFunction:
    """An external function called by the story."""

    def __init__(self, name: str, f: t.Callable, lookahead_unsafe: bool = False):
        self.name = name
        self.f = f
        self.lookahead_unsafe = lookahead_unsafe

    def __call__(self, *args, **kwargs):
        return self.f(*args, **kwargs)
