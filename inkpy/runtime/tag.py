from .object import InkObject


class Tag(InkObject):
    def __init__(self, text: str):
        self.text = text

    def __str__(self):
        return f"#{self.text}"
