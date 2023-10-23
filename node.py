from dataclasses import dataclass


@dataclass(frozen=True)
class Node:
    name: str

    def __lt__(self, other):
        if not isinstance(other, Node):
            return NotImplemented
        if self.name < other.name:
            return True
        return False

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        if not isinstance(other, Node):
            return NotImplemented
        return self.name == other.name

    @property
    def is_ground(self):
        return self.name == '0'