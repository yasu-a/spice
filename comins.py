from dataclasses import dataclass
from typing import NamedTuple, TYPE_CHECKING
from frozendict import frozendict
import expression as ex

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
        if self.component.name < other.component.name:
            return True
        if self.node < other.node:
            return True
        if self.port_name < other.port_name:
            return True
        return False

    def __repr__(self):
        return f'NodePortPair({self.component.name}, {self.node.name}, {self.port_name})'


@dataclass(frozen=True)
class ComponentInstance:
    source_line: str
    clazz: 'ComponentClass'
    name: str
    port_mapping: tuple['Node', ...]
    model: 'ComponentModel'

    def current_flow(self, port_name):
        i = self.clazz.ports.index(port_name)
        return self.clazz.current_flow[i]

    @property
    def nodes(self):
        return sorted(self.port_mapping)

    @property
    def port_to_node(self) -> frozendict[str, 'Node']:
        return frozendict({k: v for k, v in zip(self.clazz.ports, self.port_mapping)})

    @property
    def node_to_port(self) -> frozendict[str, 'Node']:
        return frozendict({k: v for k, v in zip(self.port_mapping, self.clazz.ports)})

    _REPR_VISIBLE = frozendict(
        name=None,
        clazz=lambda v: v.name,
        port_to_node=None,
        model=None
    )

    def __repr__(self):
        entries = {}
        for name, mapper in self._REPR_VISIBLE.items():
            obj = getattr(self, name)
            if mapper:
                obj = mapper(obj)
            entries[name] = obj

        return ', '.join(f'{k}={v!r}' for k, v in entries.items())

    def __lt__(self, other):
        if not isinstance(other, ComponentInstance):
            return NotImplemented
        if self.clazz < other.clazz:
            return True
        if self.name < other.name:
            return True
        return False

    @property
    def conductance(self) -> ex.ExprNode | None:
        return self.clazz.calculate_conductance(self)

    @property
    def constant_voltage(self) -> ex.ExprNode | None:
        return self.clazz.calculate_constant_voltage(self)

    @property
    def constant_current(self) -> ex.ExprNode | None:
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

    def list_node_and_port(self) -> list[NodePortPair]:
        return [
            NodePortPair(
                component=self,
                node=node,
                port_name=port_name
            )
            for port_name, node in zip(self.clazz.ports, self.port_mapping)
        ]
