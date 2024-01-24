import typing as t

from .call_stack import CallStack
from .object import InkObject
from .path import Path


class Choice(InkObject):
    def __init__(self):
        super().__init__()

        self.index: int = -1
        self.is_invisible_default: bool = False
        self.original_thread_index: int = -1
        self.source_path: t.Optional[str] = None
        self.target_path: t.Optional[Path] = None
        self.tags: list[str] = []
        self.text = ""
        self.thread_at_generation: t.Optional[CallStack.Thread] = None

    @property
    def path_string_on_choice(self) -> str:
        return str(self.target_path)

    @path_string_on_choice.setter
    def path_string_on_choice(self, value: str):
        self.target_path = Path(value)
