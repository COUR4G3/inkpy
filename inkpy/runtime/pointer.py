from dataclasses import dataclass

from .container import Container


@dataclass
class Pointer:
    path: str

    @classmethod
    def start_of(self, container: Container) -> "Pointer":
        return
