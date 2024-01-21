import typing as t

from .flow import Flow


if t.TYPE_CHECKING:
    from .story import Story


class State:
    DEFAULT_FLOW_NAME: str = "DEFAULT_FLOW"

    def __init__(self, story: "Story"):
        self.story = story

        self.current_flow = Flow(self.DEFAULT_FLOW_NAME)
        self.named_flows: dict[str, Flow] = {}

        self.errors: list[str] = []
        self.output_stream: list = []
        self.warnings: list[str] = []

        self.goto_start()

    @property
    def alive_flow_names(self) -> list[str]:
        return [f for f in self.named_flows if f != self.DEFAULT_FLOW_NAME]

    @property
    def can_continue(self) -> bool:
        return

    @property
    def current_flow_name(self) -> str:
        return self.current_flow.name

    @property
    def current_flow_is_default_flow(self) -> bool:
        return self.current_flow.name == self.DEFAULT_FLOW_NAME

    def force_end(self):
        return

    @property
    def has_error(self) -> bool:
        return len(self.errors) > 0

    @property
    def has_warning(self) -> bool:
        return len(self.warnings) > 0

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
