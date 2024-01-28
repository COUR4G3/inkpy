import itertools
import time
import typing as t

from dataclasses import dataclass

from .object import InkObject


class Profiler:
    class ProfileNode:
        def __init__(self, key: t.Optional[str] = None):
            self.key = key

            self._nodes: dict[str, Profiler.ProfileNode] = {}

            self._self_elapsed: float = 0.0
            self._total_elapsed: float = 0.0
            self._self_sample_count: int = 0
            self._total_sample_count: int = 0

        def __str__(self):
            return self.print_hierachy()

        def add_sample(self, stack: list[str], duration: float, index: int = -1):
            self._total_elapsed += duration
            self._total_sample_count += 1

            if index == len(stack) - 1:
                self._self_sample_count += 1
                self._self_elapsed += duration

            if index + 1 < len(stack):
                self.add_sample_to_node(stack, duration, index + 1)

        def add_sample_to_node(
            self, stack: list[str], duration: float, index: int = -1
        ):
            key = stack[index]

            if not (node := self._nodes.get(key)):
                node = Profiler.ProfileNode()
                self._nodes[key] = node

            node.add_sample(stack, duration, index)

        @property
        def descending_ordered_nodes(self) -> list[tuple[str, "Profiler.ProfileNode"]]:
            return sorted(self._nodes, key=lambda n: n[1]._total_elapsed)

        @property
        def has_children(self) -> bool:
            return len(self._nodes) > 0

        def print_hierachy(self, indent: int = 0):
            text = f"{indent * ' '}{self.key}: {self.report}\n"

            for _, node in self.descending_ordered_nodes:
                node.print_hierachy(indent + 1)

            return text

        @property
        def report(self):
            text = f"total {self._total_elapsed:.6f}, "
            text += f"self {self._self_elapsed:.6f}, "
            text += f" ({self._self_sample_count} self samples, "
            text += f"{self._total_sample_count} total)"
            return text

    @dataclass
    class StepDetail:
        type: str
        obj: t.Optional[InkObject] = None
        elapsed: float = 0.0

    def __init__(self):
        self._root_node = Profiler.ProfileNode()

        self._current_step_details: t.Optional[Profiler.StepDetail] = None
        self._current_step_stack = None
        self._step_details: list[Profiler.StepDetail] = []

        self._num_continues: int = 0

        self._step_paused: float = 0.0

        self._continue_started: float = 0.0
        self._snap_started: float = 0.0
        self._step_started: float = 0.0

        self._continue_total: float = 0.0
        self._snap_total: float = 0.0
        self._step_total: float = 0.0

    def megalog(self) -> str:
        """Log of all the internal instructions that were evaluated while profiling."""
        text = "Step type\tDescription\tPath\tTime"

        for step in self._step_details:
            text += f"{step.type}\t{step.obj!r}\t{step.obj.path}\t{step.elapsed:.6f}"

        return text

    def post_continue(self):
        elapsed = time.perf_counter() - self._continue_started
        self._continue_total += elapsed
        self._num_continues += 1

    def post_snapshot(self):
        elapsed = time.perf_counter() - self._snap_started
        self._snap_total += elapsed

    def post_step(self):
        elapsed = time.perf_counter() - self._step_started - self._step_paused
        self._step_total += elapsed

        self._root_node.add_sample(self._current_step_details, elapsed)

        self._current_step_details.elapsed = elapsed
        self._step_details.append(self._current_step_details)

    def pre_continue(self):
        self._continue_started = time.perf_counter()

    def pre_snapshot(self):
        self._snap_started = time.perf_counter()

    def pre_step(self):
        self._current_step_stack = None
        self._step_started = time.perf_counter()
        self._step_paused = 0.0

    def report(self) -> str:
        """Generate a printable report based on the data recording during profiling."""
        other_total = self._continue_total - (self._step_total + self._snap_total)

        text = f"{self._num_continues} CONTINUES / LINES:\n"
        text += f"TOTAL TIME: {self._continue_total:.6f}\n"
        text += f"SNAPSHOTTING: {self._snap_total:.6f}\n"
        text += f"OTHER: {other_total:.6f}\n"
        text += self._root_node.print_hierachy()

        return text

    @property
    def root_node(self) -> "Profiler.ProfileNode":
        return self._root_node

    def step(self, callstack):
        paused = time.perf_counter()

        stack = []
        for element in callstack.elements:
            stack_element_name = None
            if element.current_pointer.path:
                for component in element.current_pointer.path.components:
                    if component.is_index:
                        stack_element_name = component.name
                        break
            stack.append(stack_element_name)

        self._current_step_stack = stack

        current_object = callstack.current_element.current_pointer.resolve()

        self._step_paused += time.perf_counter() - paused

        step_type = repr(current_object)

        self._current_step_details = Profiler.StepDetail(step_type, current_object)

    def step_length_report(self) -> str:
        """Generate a printable report specifying the averages and maximums."""
        text = f"TOTAL: {self._root_node._total_elapsed:.6f}\n"

        text += f"AVERAGE STEP TIMES: {', '.join(average_step_times)}\n"

        text += f"ACCUMULATED STEP TIMES: {', '.join(cum_step_times)}\n"

        return text
