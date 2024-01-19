from dataclasses import dataclass


@dataclass
class Choice:
    index: int
    text: str

    @property
    def index1(self):
        return self.index + 1
