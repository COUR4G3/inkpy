class StoryException(RuntimeError):
    def __init__(self, message: str):
        self.message = message
