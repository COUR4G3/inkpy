import typing as t

from collections import UserDict

from .call_stack import CallStack
from .list_definition import ListDefinition
from .object import InkObject
from .value import ListValue, VariablePointerValue
from .variable_assignment import VariableAssignment


class VariablesState:
    _batch_observing_variable_changes: bool = False
    _changed_variables_for_batch_ops: set[str] = set()

    default_global_variables: dict[str, InkObject] = {}
    variable_changed_event_callbacks: list[t.Callable] = []

    def __init__(
        self, call_stack: CallStack, list_definitions: t.Optional[ListDefinition] = None
    ):
        self.call_stack = call_stack
        self.global_variables: dict[str, InkObject] = {}
        self.list_definitions = list_definitions

    def assign(self, assignment: VariableAssignment, value: InkObject):
        name = assignment.variable_name
        index = -1

        if assignment.is_new_declaration:
            set_global = assignment.is_global
        else:
            set_global = self.global_variable_exists_with_name(name)

        if assignment.is_new_declaration:
            if isinstance(value, VariablePointerValue):
                value = self.resolve_variable_pointer(value)
        else:
            existing_pointer = True
            while existing_pointer:
                existing_pointer = self.get_raw_variable_with_name(name, index)
                if existing_pointer:
                    name = existing_pointer.variable_name
                    index = existing_pointer.index
                    set_global = index == 0

        if set_global:
            self.set_global(name, value)
        else:
            self.call_stack.set_temporary_variable(
                name, value, assignment.is_new_declaration, index
            )

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

    def get_raw_variable_with_name(self, name: str, index: int = -1) -> InkObject:
        if index == 0 or index == -1:
            value = self.global_variables.get(name, None)
            if value is not None:
                return value

            value = self.default_global_variables.get(name, None)
            if value is not None:
                return value

            # TODO: var listItemValue = _listDefsOrigin.FindSingleItemListWithName (name);
            #    if (listItemValue)
            #         return listItemValue;

        value = self.call_stack.get_temporary_variable_with_name(name, index)
        return value

    def get_variable_with_name(self, name: str, index: int = -1) -> InkObject:
        value = self.get_raw_variable_with_name(name, index)

        if isinstance(value, VariablePointerValue):
            value = self.value_at_variable_pointer(value)

        return value

    def global_variable_exists_with_name(self, name: str) -> bool:
        return name in self.global_variables or name in self.default_global_variables

    def observe_variable_change(self, callback: t.Callable):
        self.variable_changed_event_callbacks.append(callback)

    def set_global(self, name: str, value: InkObject):
        old_value = self.global_variables.get(name, None)

        ListValue.retain_list_origins_for_assignment(old_value, value)

        self.global_variables[name] = value

        if self.batch_observing_variable_changes:
            self._changed_variables_for_batch_ops.add(name)
        else:
            self.variable_changed_event(name, value)

    def snapshot_default_variables(self):
        return

    def variable_changed_event(self, name: str, value: InkObject):
        for callback in self.variable_changed_event_callbacks:
            callback(name, value)
