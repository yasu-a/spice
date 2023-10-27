from typing import TYPE_CHECKING
from dataclasses import dataclass

if TYPE_CHECKING:
    from comins import ComponentInstance


@dataclass(frozen=True)
class Edge:
    component: 'ComponentInstance'

    def __repr__(self):
        return f'Edge(name={self.component.name!r})'

    def __lt__(self, other):
        if not isinstance(other, Edge):
            return NotImplemented
        if self.component.name < other.component.name:
            return True
        return False
