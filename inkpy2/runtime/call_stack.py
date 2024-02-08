class CallStack:
    class Element:
        current_pointer = None

    class Thread:
        previous_pointer = None

    def __init__(self):
        self.elements: list[CallStack.Element] = []
        self.threads: list[CallStack.Thread] = []

    def __len__(self):
        return len(self.elements)

    @property
    def current_element(self) -> "Element":
        return self.elements[-1]

    @property
    def current_thread(self) -> "Thread":
        return self.threads[-1]

    @property
    def depth(self) -> int:
        return len(self.elements)
