import typing as t

from collections import UserDict

from .call_stack import CallStack
from .list_definition import ListDefinition
from .object import InkObject


class VariablesState:
    _batch_observing_variable_changes: bool = False
    _changed_variables_for_batch_ops: set[str] = set()

    default_global_variables: dict[str, InkObject] = {}
    variable_changed_event_callbacks: dict[str, t.Callable] = []

    def __init__(
        self, call_stack: CallStack, list_definitions: t.Optional[ListDefinition] = None
    ):
        self.call_stack = call_stack
        self.global_variables: dict[str, InkObject] = {}
        self.list_definitions = list_definitions

    @property
    def batch_observing_variable_changes(self) -> bool:
        return self._batch_observing_variable_changes

    @batch_observing_variable_changes.setter
    def batch_observing_variable_changes(self, value: bool):
        self._batch_observing_variable_changes = value

        if value:
            self._changed_variables_for_batch_ops = set()
        else:
            if self._changed_variables_for_batch_ops:
                for name in self._changed_variables_for_batch_ops:
                    current_value = self.global_variables.get(name)
                    self.variable_changed_event(name, current_value)

            self._changed_variables_for_batch_ops.clear()

    def variable_changed_event(self, name: str, value: InkObject):
        for callback in self.variable_changed_event_callbacks:
            callback(name, value)
