import json
import random
import sys
import time
import typing as t

from collections import UserDict, defaultdict
from dataclasses import asdict, dataclass, field

from .call_stack import CallStack
from .choice import Choice
from .container import Container
from .flow import Flow
from .pointer import Pointer


if t.TYPE_CHECKING:
    from .story import Story


class Globals(UserDict):
    def __init__(self):
        self.call_stack: t.Optional[CallStack] = None
        self.observers: dict[str, list[t.Callable[[str, t.Any], None]]] = defaultdict(
            list
        )

        super().__init__()

    def __setitem__(self, key, item):
        super().__setitem__(key, item)

        if key not in self.observers:
            return

        for f in self.observers[key]:
            f(key, item)

    def __delitem__(self, key):
        super().__delitem__(key)

        if key not in self.observers:
            return

        for f in self.observers[key]:
            f(key, None)


@dataclass
class State:
    DEFAULT_FLOW_NAME: t.ClassVar[str] = "DEFAULT_FLOW"

    ink_save_state_version: t.ClassVar[int] = 10
    ink_min_compatible_load_version: t.ClassVar[int] = 8

    story: "Story"
    current_flow: Flow = field(init=False)
    current_turn_index: int = -1
    errors: list = field(default_factory=list)
    globals: Globals = field(default_factory=Globals)
    named_flows: dict[str, Flow] = field(default_factory=dict)
    seed: int = field(init=False)
    temp: dict[str, t.Any] = field(default_factory=dict)
    turn_indices: dict[str, int] = field(default_factory=dict)
    visit_counts: dict[str, int] = field(default_factory=dict)
    warnings: list = field(default_factory=list)

    def __post_init__(self):
        self.seed = (
            random.Random(time.time_ns() // 1_000_000).randint(0, sys.maxsize) % 100
        )

        self.current_flow = Flow(self.DEFAULT_FLOW_NAME, self.story)
        self.goto_start()

    def add_error(self, message):
        self.errors.append(message)

    def add_warning(self, message):
        self.warnings.append(message)

    def alive_flow_names(self):
        return [n for n, f in self.named_flows if n != self.DEFAULT_FLOW_NAME]

    @property
    def call_stack(self) -> CallStack:
        return self.current_flow.call_stack

    @property
    def call_stack_depth(self) -> int:
        return self.call_stack.depth

    @property
    def can_continue(self) -> bool:
        return not self.current_pointer and not self.has_error

    @property
    def choices(self) -> list[Choice]:
        if self.can_continue:
            return []
        return self.current_flow.choices

    @property
    def current_choices(self) -> list[Choice]:
        return self.choices

    @property
    def current_flow_is_default_flow(self) -> bool:
        return self.current_flow.name == self.DEFAULT_FLOW_NAME

    @property
    def current_flow_name(self) -> str:
        return self.current_flow.name

    @property
    def current_path_string(self) -> str:
        return self.current_pointer and str(self.current_pointer.path)

    @property
    def current_pointer(self):
        return self.call_stack.current_element.current_pointer

    @current_pointer.setter
    def current_pointer(self, value):
        self.call_stack.current_element.current_pointer = value

    def force_end(self):
        self.call_stack.reset()

        self.current_flow.choices.clear()

        self.current_pointer = None
        self.previous_pointer = None

    @property
    def generated_choices(self) -> list[Choice]:
        return self.current_flow.choices

    def goto(self, pointer: Pointer):
        self.current_pointer = pointer

    def goto_start(self):
        start = Pointer.start_of(self.story.root)
        return self.goto(start)

    @property
    def has_error(self) -> bool:
        return len(self.errors) > 0

    @property
    def has_warning(self) -> bool:
        return len(self.warnings) > 0

    @property
    def in_expression_evaluation(self) -> bool:
        return self.call_stack.current_element.in_expression_evaluation

    @in_expression_evaluation.setter
    def in_expression_evaluation(self, value: bool):
        self.call_stack.current_element.in_expression_evaluation = value

    def increment_visit_count_for_container(self, container: Container):
        return

    @property
    def tmp(self) -> dict[str, t.Any]:
        return self.temp

    def load_dict(self, data: dict):
        return

    def load_json(self, data: str):
        return

    @property
    def previous_pointer(self):
        return self.call_stack.current_thread.previous_pointer

    @previous_pointer.setter
    def previous_pointer(self, value):
        self.call_stack.current_thread.previous_pointer = value

    def record_turn_index_visit_to_container(self, container: Container):
        return

    def _remove_flow(self, name: str):
        if name == self.DEFAULT_FLOW_NAME:
            raise RuntimeError("Cannot destroy default flow")

        if self.current_flow_name == name:
            self._switch_to_default_flow()

        del self.named_flows[name]

    def reset_errors(self):
        self.errors.clear()

    def reset_warnings(self):
        self.warnings.clear()

    def _switch_flow(self, name: str):
        if not self.named_flows:
            self.named_flows[self.DEFAULT_FLOW_NAME] = self.current_flow

        if name == self.current_flow_name:
            return

        if name not in self.named_flows:
            flow = Flow(name, self.story)
            self.named_flows[name] = flow

        self.current_flow = flow
        self.globals.call_stack = self.current_flow.call_stack

    def _switch_to_default_flow(self):
        if not self.named_flows:
            return
        return self._switch_flow(self.DEFAULT_FLOW_NAME)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    def turns_since_for_container(self, container: Container):
        return

    def visit_count_at_path_string(self, path: str):
        return

    def visit_count_for_container(self, container: Container):
        return
