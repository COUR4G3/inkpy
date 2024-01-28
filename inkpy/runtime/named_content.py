import typing as t

from .object import InkObject


class NamedContent(InkObject):
    def __init__(self, *args, name: t.Optional[str] = None, **kwargs):
        self.name = name

        super().__init__(*args, **kwargs)

    @property
    def has_valid_name(self):
        return bool(self.name)
