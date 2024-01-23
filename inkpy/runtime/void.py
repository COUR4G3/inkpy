from .object import InkObject


class Void(InkObject):
    def __bool__(self):
        return False
