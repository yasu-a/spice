from dataclasses import dataclass
from typing import NamedTuple, TYPE_CHECKING
from frozendict import frozendict

if TYPE_CHECKING:
    from comcls import ComponentClass
    from model import ComponentModel
    from node import Node


@dataclass(frozen=True)
class NodePortPair:
    component: 'ComponentInstance'
    node: 'Node'
    port_name: str

    def __lt__(self, other):
        if not isinstance(other, NodePortPair):
            return NotImplemented
        if not self.component.name < other.component.name:
            return False
        if not self.node < other.node:
            return False
        if not self.port_name < other.port_name:
            return False
        return True

    def __repr__(self):
        return f'NodePortPair({self.component.name}, {self.node.name}, {self.port_name})'


class ComponentInstance(NamedTuple):
    clazz: 'ComponentClass'
    name: str
    port_mapping: tuple['Node', ...]
    model: 'ComponentModel'

    # TODO: impl calculate_conductance

    @property
    def constant_voltage(self) -> float:
        return self.clazz.calculate_constant_voltage(self)

    @property
    def constant_current(self) -> float:
        return self.clazz.calculate_constant_current(self)

    @property
    def node_assign(self):
        return {
            node: frozendict(
                port=port,
                node=node,
                current_flow=current_flow
            )
            for port, node, current_flow in \
            zip(self.clazz.ports, self.port_mapping, self.clazz.current_flow)
        }

    @property
    def port_assign(self):
        return {
            port: frozendict(
                port=port,
                node=node,
                current_flow=current_flow
            )
            for port, node, current_flow in \
            zip(self.clazz.ports, self.port_mapping, self.clazz.current_flow)
        }

    @property
    def conductance(self):
        return self.clazz.calculate_conductance(self)

    def list_node_and_port(self) -> list[NodePortPair]:
        return [
            NodePortPair(
                component=self,
                node=node,
                port_name=port_name
            )
            for port_name, node in zip(self.clazz.ports, self.port_mapping)
        ]
