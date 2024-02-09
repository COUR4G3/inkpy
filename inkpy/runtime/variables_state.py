import typing as t

from .call_stack import CallStack
from .exceptions import StoryException
from .value import Value


if t.TYPE_CHECKING:
    from .story import Story


class VariablesState:
    dont_save_default_values = True

    def __init__(self, call_stack: CallStack, story: "Story"):
        self.call_stack = call_stack
        self.story = story

        self._batch_observing_variable_changes = False
        self._changed_variables_for_batch = set()
        self._global_variables: dict[str, Value] = {}
        self._default_global_variables: dict[str, Value] = {}

    def __contains__(self, name: str):
        return name in self._global_variables or name in self._default_global_variables

    def __getitem__(self, name: str):
        # TODO: get from patch

        value = self._global_variables.get(name)
        if value is None:
            value = self._default_global_variables.get(name)

        if value is None:
            # TODO: return warning
            return

        return value.value

    def __iter__(self):
        return iter(self._global_variables.keys())

    def __setitem__(self, name: str, value: t.Any):
        if name not in self._default_global_variables:
            raise StoryException(
                f"Cannot assign to a variable ({name}) that hasn't been declared "
                "in the story"
            )

        ink_value = Value.create(value)
        if ink_value is None:
            if value is None:
                raise RuntimeError("Cannot pass None to VariableState")
            else:
                raise RuntimeError(f"Invalid value passed to VariableState: {value!r}")

        self.set_global_variable(name, ink_value)

    @property
    def batch_observing_variable_changes(self) -> bool:
        return self._batch_observing_variable_changes

    @batch_observing_variable_changes.setter
    def batch_observing_variable_changes(self, value: bool):
        self._batch_observing_variable_changes = value

        if not value:
            for name in self._changed_variables_for_batch:
                value = self._global_variables[name]
                self._on_variable_changed(name, value)

            self._changed_variables_for_batch.clear()

    def get(self, name: str, index: int = -1) -> Value:
        value = self._get_raw_variable(name, index)

        # TODO: resolve variable pointer value

        return value

    def get_context_index(self, name: str):
        if name in self._global_variables or name in self._default_global_variables:
            return 0
        return self.call_stack.current_element_index

    def _get_raw_variable(self, name: set, index: int = -1) -> Value | None:
        if index <= 0:
            # TODO: patch

            if name in self._global_variables:
                return self._global_variables[name]

            if name in self._default_global_variables:
                return self._default_global_variables[name]

            # TODO: single list item

        return self.call_stack.get_temporary_variable(name, index)

    def _on_variable_changed(self, name: str, value: Value):
        if self._batch_observing_variable_changes:
            self._changed_variables_for_batch.add(name)
        else:
            for observer in self.story._observers[name]:
                observer(name, value)

    def resolve_variable_pointer(self, pointer) -> Value:
        return self.get(pointer.variable_name, pointer.index)

    def set_global_variable(self, name: str, value: Value):
        # TODO: patch

        old_value = self._global_variables.get(name)

        # TODO: retain for list stuff

        # TODO: patch

        self._global_variables[name] = value

        if value != old_value:
            self._on_variable_changed(name, value)

    def snapshot_defaults(self):
        self._default_global_variables = self._global_variables.copy()
