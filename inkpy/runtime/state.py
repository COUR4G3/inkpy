import typing as t

from .call_stack import CallStack
from .flow import Flow
from .pointer import Pointer
from .variables_state import VariablesState


if t.TYPE_CHECKING:
    from .story import Story


class State:
    DEFAULT_FLOW_NAME: str = "DEFAULT_FLOW"

    def __init__(self, story: "Story"):
        self.story = story

        self.current_flow = Flow(self.DEFAULT_FLOW_NAME, story)
        self.current_turn_index: int = -1
        self.errors: list[str] = []
        self.eval_stack: list = []
        self.named_flows: dict[str, Flow] = {}
        self.output_stream: list = []
        self.seed: int = 42
        self.turn_indices: dict[str, int] = {}
        self.variables_state = VariablesState(self.call_stack, story.list_definitions)
        self.visit_counts: dict[str, int] = {}
        self.warnings: list[str] = []

        self.goto_start()

    @property
    def alive_flow_names(self) -> list[str]:
        return [f for f in self.named_flows if f != self.DEFAULT_FLOW_NAME]

    @property
    def call_stack(self) -> CallStack:
        return self.current_flow.call_stack

    @property
    def can_continue(self) -> bool:
        return self.current_pointer and not self.has_error

    @property
    def current_flow_name(self) -> str:
        return self.current_flow.name

    @property
    def current_flow_is_default_flow(self) -> bool:
        return self.current_flow.name == self.DEFAULT_FLOW_NAME

    @property
    def current_pointer(self) -> Pointer:
        return self.call_stack.current_element.current_pointer

    @current_pointer.setter
    def current_pointer(self, value: Pointer):
        self.call_stack.current_element.current_pointer = value

    @property
    def current_text(self) -> str:
        return ""  # TODO: get output

    def force_end(self):
        self.call_stack.reset()
        self.current_flow.current_choices.clear()
        self.current_pointer = None
        self.previous_pointer = None
        self.did_safe_exit = True

    def goto_start(self):
        self.call_stack.current_element.current_pointer = Pointer.start_of(
            self.story.main_content_container
        )

    @property
    def has_error(self) -> bool:
        return len(self.errors) > 0

    @property
    def has_warning(self) -> bool:
        return len(self.warnings) > 0

    @property
    def previous_pointer(self) -> Pointer:
        return self.call_stack.current_thread.previous_pointer

    @previous_pointer.setter
    def previous_pointer(self, value: Pointer):
        self.call_stack.current_thread.previous_pointer = value

    def _remove_flow(self, name: str):
        if name == self.DEFAULT_FLOW_NAME:
            raise Exception("Cannot destory the default flow")

        if self.current_flow.name == name:
            self._switch_to_default_flow()

        del self.named_flows[name]

    def reset_errors(self):
        self.errors.clear()
        self.warnings.clear()

    def reset_output(self, objs: t.Optional[list] = None):
        self.output_stream.clear()
        if objs:
            self.output_stream.extend(objs)

    def _switch_flow(self, name: str):
        if not self.named_flows:
            self.named_flows[self.DEFAULT_FLOW_NAME] = self.current_flow

        if name == self.current_flow.name:
            return

        flow = self.named_flows.get(name)
        if not flow:
            flow = Flow(name)
            self.named_flows[name] = flow

        self.current_flow = flow
        self.variables_state.call_stack = self.current_flow.call_stack

    def _switch_to_default_flow(self):
        self._switch_flow(self.DEFAULT_FLOW_NAME)
