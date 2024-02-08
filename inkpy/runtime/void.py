class Void:
    def __bool__(self):
        return False

    def __eq__(self, other):
        return isinstance(other, Void)

    def __repr__(self):
        return "void"
