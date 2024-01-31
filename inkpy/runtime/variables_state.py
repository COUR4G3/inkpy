import typing as t

from ..compiler.json import JSONCompiler
from .call_stack import CallStack
from .exceptions import StoryException
from .object import InkObject
from .state_patch import StatePatch
from .value import Value, VariablePointerValue
from .variable_assignment import VariableAssignment


class VariablesState:
    dont_save_default_values = False

    def __init__(self, call_stack: CallStack, list_definitions=None):
        self._batch_observing_variable_changes = False
        self._call_stack = call_stack
        self._changed_variables_for_batch_obs: set[str] = set()

        self._default_global_variables: dict[str, InkObject] = {}
        self._global_variables: dict[str, InkObject] = {}

        self.patch: t.Optional[StatePatch] = None

    def __getitem__(self, name: str) -> t.Any:
        if self.patch and (value := self.patch.try_get_global(name)):
            return value.value

        value = self._global_variables.get(name)

        if value is None:
            value = self._default_global_variables.get(name)

        return value and value.value or None

    def __setitem__(self, name: str, value: t.Any):
        if name not in self._default_global_variables:
            raise StoryException(
                f"Cannot assign to a variable ('{name}') that hasn't been declared in "
                "the story"
            )

        value_obj = Value.create(value)
        if value_obj is None:
            if value_obj is None:
                raise RuntimeError("Cannot pass None to VariableState")
            else:
                raise RuntimeError(f"Invalid value passed to VariableState: {value!r}")

        self.set_global(name, value_obj)

    def apply_patch(self):
        for name, value in self.patch.globals.items():
            self._global_variables[name] = value

        if self._batch_observing_variable_changes:
            for name in self.patch.changed_variables:
                self._changed_variables_for_batch_obs.add(name)

        self.patch = None

    def assign(self, assign: VariableAssignment, value: InkObject):
        name = assign.variable_name
        index = -1

        if assign.is_new_decl:
            set_global = True
        else:
            set_global = self.global_variable_exists_with_name(name)

        if assign.is_new_decl:
            if isinstance(value, VariablePointerValue):
                value = self.resolve_variable_pointer(value)
        else:
            existing_pointer = False
            while existing_pointer is not None:
                existing_pointer = self.get_raw_variable_with_name(name, index)
                if isinstance(existing_pointer, VariablePointerValue):
                    name = existing_pointer.variable_name
                    index = existing_pointer.index
                    set_global = index == 0
                else:
                    break

        if set_global:
            self.set_global(name, value)
        else:
            self._call_stack.set_temporary_variable(
                name, value, assign.is_new_decl, index
            )

    @property
    def batch_observing_variable_changes(self) -> bool:
        return self._batch_observing_variable_changes

    @batch_observing_variable_changes.setter
    def batch_observing_variable_changes(self, value: bool):
        self._batch_observing_variable_changes = value

        if not value:
            if self._changed_variables_for_batch_obs:
                for name in self._changed_variables_for_batch_obs:
                    current_value = self._global_variables[name]
                    self.variable_changed_event(name, current_value)

        self._changed_variables_for_batch_obs.clear()

    @property
    def call_stack(self) -> CallStack:
        return self._call_stack

    @call_stack.setter
    def call_stack(self, value: CallStack):
        self._call_stack = value

    def get_context_index_of_variable_named(self, name: str) -> int:
        if self.global_variable_exists_with_name(name):
            return 0

        return self._call_stack.current_element_index

    def get_raw_variable_with_name(
        self, name: str, index: int = -1
    ) -> InkObject | None:
        if index <= 0:
            if self.patch and (value := self.patch.try_get_global(name)):
                return value

            value = self._global_variables.get(name)
            if value is not None:
                return value

            value = self._default_global_variables.get(name)
            if value is not None:
                return value

            # TODO: handle list values

        return self._call_stack.get_temporary_variable_with_name(name, index)

    def get_variable_with_name(self, name: str, index: int = -1) -> InkObject | None:
        value = self.get_raw_variable_with_name(name, index)

        if isinstance(value, VariablePointerValue):
            value = self.value_at_variable_pointer(value)

        return value

    def global_variable_exists_with_name(self, name: str) -> bool:
        return name in self._global_variables or name in self._default_global_variables

    def resolve_variable_pointer(
        self, value: VariablePointerValue
    ) -> VariablePointerValue:
        index = value.index

        if index == -1:
            index = self.get_content_index_of_variable_named(value.variable_name)

        value_of_variable_pointed_to = self.get_raw_variable_with_name(
            value.variable_name, index
        )

        # extra layer of indirection
        if isinstance(value_of_variable_pointed_to, VariablePointerValue):
            return value_of_variable_pointed_to
        else:
            return VariablePointerValue(value.variable_name, index)

    def set_global(self, name: str, value: InkObject):
        if not self.patch or (old_value := self.patch.try_get_global(name)):
            old_value = self._global_variables.get(name)

        if self.patch:
            self.patch.set_global(name, value)
        else:
            self._global_variables[name] = value

        if self.variable_changed_event is not None and value != old_value:
            if self.batch_observing_variable_changes:
                if self.patch:
                    self.patch.add_changed_variable(name)
                else:
                    self._changed_variables_for_batch_obs.add(name)
        else:
            self.variable_changed_event(name, value)

    def snapshot_default_globals(self):
        self._default_global_variables = self._global_variables.copy()

    def to_dict(self) -> dict[str, t.Any]:
        data = {}

        for name, value in self._global_variables.items():
            if self.dont_save_default_values:
                default_value = self._default_global_variables.get(name)
                if default_value == value:
                    continue

            data[name] = JSONCompiler.dump_runtime_object(value)

        return data

    def try_get_default_variable_value(self, name: str) -> InkObject | None:
        return self._default_global_variables.get(name)

    def value_at_variable_pointer(self, value: VariablePointerValue) -> InkObject:
        return self.get_variable_with_name(value.variable_name, value.index)

    def variable_changed_event(self, name: str, value: t.Any):
        return
