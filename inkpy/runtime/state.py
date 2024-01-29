import json
import random
import time
import typing as t
import warnings

from ..compiler.json import JSONCompiler
from .call_stack import CallStack
from .choice import Choice
from .container import Container
from .control_command import ControlCommand
from .glue import Glue
from .flow import Flow
from .path import Path
from .pointer import Pointer
from .push_pop import PushPopType
from .value import ListValue, StringValue
from .variables_state import VariablesState


if t.TYPE_CHECKING:
    from .object import InkObject
    from .story import Story


class State:
    DEFAULT_FLOW_NAME = "DEFAULT_FLOW"

    INK_SAVE_STATE_VERSION = 10
    MIN_COMPATIBLE_LOAD_VERSION = 8

    OnDidLoadState = t.Callable[[], None]

    def __init__(self, story: "Story"):
        self.story = story

        self.current_errors: list[str] = []
        self.current_turn_index: int = 0
        self.current_warnings: list[str] = []
        self.did_safe_exit = False
        self.diverted_pointer: t.Optional[Pointer] = None
        self.evaluation_stack: list[InkObject] = []
        self.output_stream: list["InkObject"] = []

        self._current_flow = Flow(self.DEFAULT_FLOW_NAME, story)
        self._named_flows: dict[str, Flow] = {}

        self._on_did_load_state: t.Optional[self.OnDidLoadState] = None

        self._turn_indices: dict[str, int] = {}
        self._visit_counts: dict[str, int] = {}

        # seed the random number generator
        time_seed = time.time_ns() // 1_000_000
        self.story_seed = random.Random(time_seed).randint(0, 2**31 - 1) % 100
        self.previous_random = 0

        self.variables_state = VariablesState(self.call_stack, story.list_definitions)

        self.goto_start()

    @property
    def alive_flow_names(self) -> list[str]:
        return [name for name in self._named_flows if name != self.DEFAULT_FLOW_NAME]

    @property
    def call_stack(self) -> CallStack:
        return self._current_flow.call_stack

    @property
    def can_continue(self) -> bool:
        return bool(self.current_pointer and not self.has_error)

    def clean_output_whitespace(self, text: str) -> str:
        output = ""

        current_whitespace_start = -1
        start_of_line = 0

        for i, c in enumerate(text):
            is_inline_whitespace = c in (" ", "\t")

            if is_inline_whitespace and current_whitespace_start == -1:
                current_whitespace_start = i

            if not is_inline_whitespace:
                if (
                    c != "\n"
                    and current_whitespace_start > 0
                    and current_whitespace_start != start_of_line
                ):
                    output += " "
                current_whitespace_start = -1

            if c == "\n":
                start_of_line = i + 1

            if not is_inline_whitespace:
                output += c

        return output

    @property
    def current_choices(self) -> list[Choice]:
        if self.can_continue:
            return []
        return self._current_flow.current_choices

    @property
    def current_flow_is_default_flow(self) -> bool:
        return self._current_flow.name == self.DEFAULT_FLOW_NAME

    current_flow_is_default = current_flow_is_default_flow

    @property
    def current_flow_name(self) -> str:
        return self._current_flow.name

    @property
    def current_pointer(self) -> Pointer:
        return self.call_stack.current_element.current_pointer

    @current_pointer.setter
    def current_pointer(self, value: Pointer | None):
        self.call_stack.current_element.current_pointer = value

    @property
    def current_text(self) -> str:
        if self._output_stream_text_dirty:
            text = ""

            in_tag = False
            for object in self.output_stream:
                if not in_tag and isinstance(object, StringValue):
                    text += object.value
                elif isinstance(object, ControlCommand):
                    if object.type == ControlCommand.CommandType.BeginTag:
                        in_tag = True
                    elif object.type == ControlCommand.CommandType.EndTag:
                        in_tag = False

            self._current_text = self.clean_output_whitespace(text)
            self._output_stream_text_dirty = False

        return self._current_text

    def force_end(self):
        self.call_stack.reset()

        self._current_flow.current_choices.clear()

        self.current_pointer = None
        self.previous_pointer = None

        self.did_safe_exit = True

    @property
    def generated_choices(self) -> list[Choice]:
        return self._current_flow.current_choices

    def goto_start(self):
        self.call_stack.current_element.current_pointer = Pointer.start_of(
            self.story.main_content_container
        )

    @property
    def has_error(self) -> bool:
        return len(self.current_errors) > 0

    has_errors = has_error

    @property
    def has_warning(self) -> bool:
        return len(self.current_warnings) > 0

    has_warnings = has_warning

    @property
    def in_expression_evaluation(self) -> bool:
        return self.call_stack.current_element.in_expression_eval

    @in_expression_evaluation.setter
    def in_expression_evaluation(self, value: bool):
        self.call_stack.current_element.in_expression_eval = value

    @property
    def in_string_evaluation(self) -> bool:
        for output in self.output_stream:
            if (
                isinstance(output, ControlCommand)
                and output.type == ControlCommand.CommandType.BeginString
            ):
                return True

        return False

    def increment_visit_count_for_container(self, container: "Container"):
        path_string = str(container.path)
        if path_string in self._visit_counts:
            self._visit_counts[path_string] += 1
        else:
            self._visit_counts[path_string] = 0

    def load_dict(self, data: dict[str, t.Any]):
        # check the save state version
        version = data.get("inkSaveVersion")

        if not version:
            raise ValueError("Version of ink save format could not be found")

        try:
            version = int(version)
        except ValueError:
            raise ValueError(
                f"Version of ink save format could not be parsed: {version}"
            )

        if version < self.MIN_COMPATIBLE_LOAD_VERSION:
            raise RuntimeError(
                "Ink save format isn't compatible with the current version (saw "
                f"'{version}', but minimum is '{self.MIN_COMPATIBLE_LOAD_VERSION}')"
            )
        elif version > self.INK_SAVE_STATE_VERSION:
            raise RuntimeError(
                "Ink save format is too new for the current version (saw "
                f"'{version}', but current is '{self.INK_SAVE_STATE_VERSION}')"
            )
        elif version != self.INK_SAVE_STATE_VERSION:
            warnings.warn(
                f"Ink save format doesn't match current version (saw '{version}', but "
                f"current is '{self.INK_SAVE_STATE_VERSION}')",
                RuntimeWarning,
            )

        self._named_flows.clear()

        # latest multi-flow format, flows always exists even if there is just a default
        if "flows" in data:
            flows = data["flows"]

            for name, flow_data in flows.items():
                flow = Flow(name, self, flow_data)

                if len(flows) > 1:
                    self._named_flows[name] = flow
                else:
                    self._current_flow = flow

            if self._named_flows:
                self._current_flow = self._named_flows["currentFlowName"]

        # old format, check callstack, output stream and choices
        else:
            self._current_flow = Flow(self.DEFAULT_FLOW_NAME, self.story)
            # _currentFlow.callStack.SetJsonToken ((Dictionary < string, object > )jObject ["callstackThreads"], story);
            # _currentFlow.outputStream = Json.JArrayToRuntimeObjList ((List<object>)jObject ["outputStream"]);
            # _currentFlow.currentChoices = Json.JArrayToRuntimeObjList<Choice>((List<object>)jObject ["currentChoices"]);

            # object jChoiceThreadsObj = null;
            # jObject.TryGetValue("choiceThreads", out jChoiceThreadsObj);
            # _currentFlow.LoadFlowChoiceThreads((Dictionary<string, object>)jChoiceThreadsObj, story);

        self.output_stream_dirty()

        # variablesState.SetJsonToken((Dictionary < string, object> )jObject["variablesState"]);
        # variablesState.callStack = _currentFlow.callStack;

        # evaluationStack = Json.JArrayToRuntimeObjList ((List<object>)jObject ["evalStack"]);

        if current_divert_target_path := data.get("currentDivertTarget"):
            divert_path = Path(current_divert_target_path)
            self.diverted_pointer = self.story.pointer_at_path(divert_path)

        self._visit_counts = {k: int(v) for k, v in data["visitCounts"]}
        self._turn_indices = {k: int(v) for k, v in data["turnIndices"]}

        self.current_turn_index = int(data["turnIdx"])
        self.story_seed = int(data["storySeed"])

        # not optional, but bug in inkjs means it's actually missing in inkjs saves
        self.previous_random = int(data.get("previousRandom", 0))

        if self._on_did_load_state:
            self._on_did_load_state()

    def load_json(self, input: str | t.TextIO):
        if isinstance(input, str):
            data = json.loads(input)
        else:
            data = json.load(input)

        self.load_dict(data)

    def on_did_load_state(self, f: t.Optional[OnDidLoadState] = None):
        def decorator(f):
            self._on_did_load_state = f
            return f

        return f and decorator(f) or decorator

    @property
    def output_stream_contains_content(self) -> bool:
        return any(isinstance(c, StringValue) for c in self.output_stream)

    def output_stream_dirty(self):
        self._output_stream_text_dirty = True
        self._output_stream_tags_dirty = True

    @property
    def output_stream_ends_in_newline(self) -> bool:
        for output in self.output_stream:
            if not isinstance(output, ControlCommand):
                break
            elif isinstance(output, StringValue):
                if output.is_newline:
                    return True
                elif output.is_non_whitespace:
                    break

        return False

    def peek_evaluation_stack(self) -> "InkObject":
        return self.evaluation_stack[-1]

    def pop_callstack(self, pop_type: t.Optional[PushPopType] = None):
        if self.call_stack.current_element.type == PushPopType.Function:
            self.trim_whitespace_from_function_end()

        self.call_stack.pop(pop_type)

    def pop_evaluation_stack(
        self, count: int = 1
    ) -> t.Union["InkObject", list["InkObject"]]:
        if count > len(self.evaluation_stack):
            raise RuntimeError("Trying to pop too many objects from evaluation stack")

        objs = self.evaluation_stack[-count:]
        self.evaluation_stack[:] = self.evaluation_stack[:-count]

        if count == 1:
            return objs[0]
        return objs

    def pop_from_output_stream(self, count: int):
        self.output_stream[:] = self.output_stream[: len(self.output_stream) - count]
        self.output_stream_dirty()

    @property
    def previous_pointer(self) -> Pointer:
        return self.call_stack.current_thread.previous_pointer

    @previous_pointer.setter
    def previous_pointer(self, value: Pointer | None):
        self.call_stack.current_thread.previous_pointer = value

    def push_evaluation_stack(self, object: "InkObject"):
        if isinstance(object, ListValue):
            raw_list = object.value

            if raw_list.origin_names:
                if not raw_list.origins:
                    raw_list.origins = ListDefinition()
                raw_list.origins.clear()

                for name in raw_list.origin_names:
                    pass

        self.evaluation_stack.append(object)

    def push_to_output_stream(self, object: "InkObject"):
        if isinstance(object, StringValue):
            texts = self.try_splitting_head_tail_whitespace(object)
            if texts:
                for text in texts:
                    self.push_to_output_stream_individual(text)
                self.output_stream_dirty()
                return

        self.push_to_output_stream_individual(object)
        self.output_stream_dirty()

    def push_to_output_stream_individual(self, object: "InkObject"):
        include_in_output = True

        if isinstance(object, Glue):
            self.trim_newlines_from_output_stream()
            include_in_output = True
        elif isinstance(object, StringValue):
            function_trim_index = -1
            current_element = self.call_stack.current_element
            if current_element.type == PushPopType.Function:
                function_trim_index = current_element.function_start_in_output_stream

            glue_trim_index = -1
            for i, output in enumerate(self.output_stream):
                if isinstance(output, Glue):
                    glue_trim_index = i
                    break
                elif (
                    isinstance(output, ControlCommand)
                    and output.type == ControlCommand.CommandType.BeginString
                ):
                    if i >= function_trim_index:
                        function_trim_index = -1
                    break

            trim_index = -1
            if glue_trim_index != -1 and function_trim_index != -1:
                trim_index = min(glue_trim_index, function_trim_index)
            elif glue_trim_index != -1:
                trim_index = glue_trim_index
            else:
                trim_index = function_trim_index

            if trim_index != -1:
                if object.is_newline:
                    include_in_output = True
                elif object.is_non_whitespace:
                    if glue_trim_index > -1:
                        self.remove_existing_glue()

                    if function_trim_index > -1:
                        callstack_elements = self.call_stack.elements
                        for element in callstack_elements:
                            if element.type == PushPopType.Function:
                                element.function_start_in_output_stream = -1
                            else:
                                break

            elif object.is_newline:
                if (
                    self.output_stream_ends_in_newline
                    or not self.output_stream_contains_content
                ):
                    include_in_output = False

        if include_in_output:
            self.output_stream.append(object)
            self.output_stream_dirty()

    def record_turn_index_visit_to_container(self, container: "Container"):
        path_string = str(container.path)
        self.turn_indices[path_string] = self.current_turn_index

    def remove_existing_glue(self):
        for i in range(len(self.output_stream) - 1, -1, -1):
            c = self.output_stream[i]
            if isinstance(c, Glue):
                self.output_stream.pop(i)
            else:
                break

        self.output_stream_dirty()

    def reset_errors(self):
        self.current_errors.clear()
        self.current_warnings.clear()

    def reset_output(self, objs: t.Optional[list["InkObject"]] = None):
        self.output_stream.clear()
        if objs:
            self.output_stream.extend(objs)

    def set_chosen_path(self, path: "Path", incrementing_turn_index: bool):
        self._current_flow.current_choices.clear()

        new_pointer = self.story.pointer_at_path(path)
        if new_pointer and new_pointer.index == -1:
            new_pointer.index = 0

        self.current_pointer = new_pointer

        if incrementing_turn_index:
            self.current_turn_index += 1

    def to_dict(self) -> dict[str, t.Any]:
        flows = {n: f.to_dict() for n, f in self._named_flows.items()}

        if not flows:
            flows = {self._current_flow.name: self._current_flow.to_dict()}

        data = {
            "currentFlowName": self._current_flow.name,
            "evalStack": [
                JSONCompiler.dump_runtime_object(e) for e in self.evaluation_stack
            ],
            "flows": flows,
            "inkFormatVersion": self.story.INK_VERSION_CURRENT,
            "inkSaveVersion": self.INK_SAVE_STATE_VERSION,
            "previousRandom": self.previous_random,
            "storySeed": self.story_seed,
            "turnIndices": self._turn_indices,
            "variablesState": self.variables_state.to_dict(),
            "visitCounts": self._visit_counts,
        }

        if self.diverted_pointer:
            data["currentDivertTarget"] = str(self.diverted_pointer.path)

        return data

    def to_json(self, output: t.Optional[t.TextIO] = None) -> t.Optional[str]:
        data = self.to_dict()

        if output:
            json.dump(data, output)
        else:
            return json.dumps(data)

    def trim_newlines_from_output_stream(self):
        remove_whitespace_from = -1

        index = len(self.output_stream) - 1
        while index >= 0:
            content = self.output_stream[index]

            if (
                isinstance(content, ControlCommand)
                or isinstance(content, StringValue)
                and content.is_non_whitespace
            ):
                break
            elif isinstance(content, StringValue) and content.is_newline:
                remove_whitespace_from = index

            index -= 1

        if remove_whitespace_from >= 0:
            i = remove_whitespace_from
            while i < len(self.output_stream):
                content = self.output_stream[i]
                if isinstance(content, StringValue):
                    self.output_stream.pop(i)
                else:
                    i += 1

        self.output_stream_dirty()

    def trim_whitespace_from_function_end(self):
        assert self.call_stack.current_element.type == PushPopType.Function

        function_start_point = (
            self.call_stack.current_element.function_start_in_output_stream
        )

        if function_start_point == -1:
            function_start_point = 0

        for i in range(len(self.output_stream) - 1, function_start_point - 1, -1):
            output = self.output_stream[i]
            if i >= function_start_point:
                break

            if isinstance(output, ControlCommand):
                break
            elif not isinstance(output, StringValue):
                continue

            if output.is_newline or output.is_inline_whitespace:
                self.output_stream.pop(i)
                self.output_stream_dirty()
            else:
                break

    def try_exit_function_eval_from_game(self) -> bool:
        if (
            self.call_stack.current_element.type
            == PushPopType.FunctionEvaluationFromGame
        ):
            self.current_pointer = None
            self.did_safe_exit = True
            return True

        return False

    def try_splitting_head_tail_whitespace(
        self, text: StringValue
    ) -> list[StringValue]:
        head_first_newline_idx = -1
        head_last_newline_idx = -1

        for i, c in enumerate(text.value):
            if c == "\n":
                if head_first_newline_idx == -1:
                    head_first_newline_idx = i
                head_last_newline_idx = i
            elif c == " " or c == "\t":
                continue
            else:
                break

        tail_last_newline_idx = -1
        tail_first_newline_idx = -1

        for i, c in reversed(list(enumerate(text.value))):
            if c == "\n":
                if tail_last_newline_idx == -1:
                    tail_last_newline_idx = i
                tail_first_newline_idx = i
            elif c == " " or c == "\t":
                continue
            else:
                break

        if head_first_newline_idx == -1 and tail_last_newline_idx == -1:
            return

        texts = []
        inner_start = 0
        inner_end = len(text.value)

        if head_first_newline_idx != -1:
            if head_first_newline_idx > 0:
                leading_spaces = StringValue(text.value[:head_first_newline_idx])
                texts.append(leading_spaces)
            texts.append(StringValue("\n"))
            inner_start = head_last_newline_idx + 1

        if tail_last_newline_idx != -1:
            inner_end = tail_last_newline_idx

        if inner_end > inner_start:
            inner_text = text.value[inner_start : inner_start + inner_end]
            texts.append(inner_text)

        if (
            tail_last_newline_idx != -1
            and tail_first_newline_idx > head_last_newline_idx
        ):
            texts.append(StringValue("\n"))
            if tail_last_newline_idx < len(text.value) - 1:
                trailing_spaces = StringValue(text.value[tail_last_newline_idx + 1 :])
                texts.append(trailing_spaces)

        return texts

    def visit_count_for_container(self, container: "Container") -> int:
        if not container.visits_should_be_counted:
            self.add_error(
                f"Read count for target ({container.name} - on {container.debug}) unknown."
            )

        container_path_string = str(container.path)
        count = self._visit_counts.get(container_path_string, 0)
        return count
