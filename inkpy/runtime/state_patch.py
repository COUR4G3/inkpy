import typing as t

from .container import Container
from .object import InkObject


class StatePatch:
    def __init__(self, patch_to_copy: t.Optional["StatePatch"] = None):
        if patch_to_copy:
            self.globals = patch_to_copy.globals.copy()
            self.changed_variables = patch_to_copy.changed_variables.copy()
            self.visit_counts = patch_to_copy.visit_counts.copy()
            self.turn_indices = patch_to_copy.turn_indices.copy()
        else:
            self.globals: dict[str, t.Any] = {}
            self.changed_variables: set[str] = set()
            self.visit_counts: dict[Container, int] = {}
            self.turn_indices: dict[Container, int] = {}

    def add_changed_variable(self, name: str):
        self.changed_variables.add(name)

    def set_global(self, name: str, value: InkObject):
        self.globals[name] = value

    def set_turn_index(self, container: Container, index: int):
        self.turn_indices[container] = index

    def set_visit_count(self, container: Container, count: int):
        self.visit_counts[container] = count

    def try_get_global(self, name: str) -> InkObject | None:
        return self.globals.get(name)

    def try_get_turn_index(self, container: Container) -> int:
        return self.turn_indices.get(container)

    def try_get_visit_count(self, container: Container) -> int:
        return self.visit_counts.get(container, 0)
