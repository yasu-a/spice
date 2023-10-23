import collections
import operator
from dataclasses import dataclass
from typing import NamedTuple, TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from comcls import ComponentClassSet
    from comins import ComponentInstance, NodePortPair
from node import Node


@dataclass(frozen=True)
class EdgePropertyBase:
    component: 'ComponentInstance'

    def __repr__(self):
        return f'{type(self).__name__}(edge_name={self.component.name!r})'

    def __lt__(self, other):
        if not isinstance(other, EdgePropertyBase):
            return NotImplemented
        if self.component.name < other.component.name:
            return True
        return False


class EdgeCurrent(EdgePropertyBase):
    pass


class EdgeVoltage(EdgePropertyBase):
    pass


@dataclass(frozen=True)
class NodePropertyBase:
    node: 'Node'

    def __repr__(self):
        return f'{type(self).__name__}(edge_name={self.node.name!r})'

    def __lt__(self, other):
        if not isinstance(other, NodePropertyBase):
            return NotImplemented
        if self.node < other.node:
            return True
        return False


class NodePotential(NodePropertyBase):
    pass


class NetList(NamedTuple):
    title: str
    components: tuple['ComponentInstance', ...]
    commands: tuple[str, ...]

    @property
    def nodes(self) -> tuple['Node']:
        return tuple(Node(name) for name in self.list_nodes())

    @classmethod
    def from_string(cls, source: str, class_set: 'ComponentClassSet'):
        title = None
        components = []
        commands = []

        for line_no, line in enumerate(source.split('\n')):
            line_no, line = line_no + 1, line.strip()

            if not line:
                pass
            elif line_no == 1:
                title = line
            elif line.startswith('*'):
                pass
            elif line.startswith('.'):
                # commands.append(tuple(re.split(r'\s+', line[1:])))
                pass
            else:
                ins = class_set.parse_netlist_line(line)
                components.append(ins)

        return cls(
            title=title,
            components=tuple(components),
            commands=tuple(commands)
        )

    def list_components(self) -> list['ComponentInstance']:
        return sorted(self.components)

    def list_node_port_pair(self) -> list['NodePortPair']:
        return sorted(x for com in self.list_components() for x in com.list_node_and_port())

    def list_nodes(self) -> dict['Node', list['NodePortPair']]:
        result = collections.defaultdict(list)
        for npp in self.list_node_port_pair():
            result[npp.node].append(npp)
        return collections.OrderedDict(sorted(result.items(), key=operator.itemgetter(0)))

    def lookup_node_index(self, node: 'Node'):
        # TODO: optimize!
        for i, nn in enumerate(self.list_nodes()):
            if node == nn:
                return i
        assert False, node

    def lookup_component_index(self, com):
        for i, c in enumerate(self.list_components()):
            if com == c:
                return i
        assert False, com

    def edge_count(self):
        return len(self.components)

    def node_count(self):
        return len(self.nodes)

    def edge_current_vector(self):  # i
        return [EdgeCurrent(com) for com in self.list_components()]

    def edge_voltage_vector(self):  # v
        return [EdgeVoltage(com) for com in self.list_components()]

    def node_potential_vector(self):  # e
        return [NodePotential(node) for node in self.nodes]

    def conductance_matrix(self):
        g = np.diagflat([com.conductance for com in self.list_components()])
        assert g.shape == (self.edge_count(), self.edge_count())
        return g

    def voltage_matrix(self):
        ev = np.zeros(shape=(self.edge_count(), self.node_count()))
        for i, com in enumerate(self.list_components()):
            for node, current_flow in zip(com.port_mapping, com.clazz.current_flow):
                j = self.lookup_node_index(node)
                ev[i, j] = current_flow.value
        return ev

    def kcl(self):
        p = np.zeros(shape=(self.node_count(), self.edge_count()))
        for node, npp_lst in self.list_nodes().items():
            node_index = self.lookup_node_index(node)
            for nnp in npp_lst:
                com_index = self.lookup_component_index(nnp.component)
                p[node_index, com_index] = nnp.component.node_assign[node]['current_flow'].value
        return p

    def kvl(self):
        e = np.zeros(shape=(self.edge_count(), self.node_count()))
        for com in self.components:
            com_index = self.lookup_component_index(com)
            node_high = com.port_assign[com.clazz.high_side]['node']
            node_low = com.port_assign[com.clazz.low_side]['node']
            node_index_high = self.lookup_node_index(node_high)
            node_index_low = self.lookup_node_index(node_low)
            e[com_index, [node_index_high, node_index_low]] = [1, -1]
        return e

    def constant_voltage(self):
        c = np.zeros(self.edge_count())
        for i, edge_voltage in enumerate(self.edge_voltage_vector()):
            c[i] = edge_voltage.component.constant_voltage
        return c

    def constant_current(self):
        c = np.zeros(self.edge_count())
        for i, edge_current in enumerate(self.edge_current_vector()):
            c[i] = edge_current.component.constant_current
        return c
