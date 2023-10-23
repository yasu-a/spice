import numpy as np
from typing import NamedTuple, TYPE_CHECKING
from dataclasses import dataclass
import re
from ntpprint import pprint, nt_asdict

if TYPE_CHECKING:
    from comcls import ComponentClass
    from model import ComponentModel


@dataclass(frozen=True)
class NodePortPair:
    component: 'ComponentInstance'
    node_name: str
    port_name: str

    def __lt__(self, other):
        if not isinstance(other, NodePortPair):
            return NotImplemented
        if not self.component.name < other.component.name:
            return False
        if not self.node_name < other.node_name:
            return False
        if not self.port_name < other.port_name:
            return False
        return True

    def __repr__(self):
        return f'NodePortPair({self.component.name}, {self.node_name}, {self.port_name})'


class ComponentInstance(NamedTuple):
    clazz: 'ComponentClass'
    name: str
    port_mapping: tuple[str, ...]
    model: 'ComponentModel'

    @property
    def conductance(self):
        return self.clazz.calculate_conductance(self)

    def list_node_and_port(self) -> list[NodePortPair]:
        return [
            NodePortPair(
                component=self,
                node_name=node_name,
                port_name=port_name
            )
            for port_name, node_name in zip(self.clazz.ports, self.port_mapping)
        ]
