import collections
import operator
from dataclasses import dataclass
from frozendict import frozendict
import numpy as np
from typing import NamedTuple, TYPE_CHECKING
import re
from ntpprint import pprint, nt_asdict

if TYPE_CHECKING:
    from comcls import ComponentClassSet
    from comins import ComponentInstance, NodePortPair


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
    node_name: str

    def __repr__(self):
        return f'{type(self).__name__}(edge_name={self.node_name!r})'

    def __lt__(self, other):
        if not isinstance(other, NodePropertyBase):
            return NotImplemented
        if self.node_name < other.node_name:
            return True
        return False


class NodePotential(NodePropertyBase):
    pass


class NetList(NamedTuple):
    title: str
    components: tuple['ComponentInstance', ...]
    commands: tuple[str, ...]

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

    def list_node_names(self) -> dict['str', list['NodePortPair']]:
        result = collections.defaultdict(list)
        for npp in self.list_node_port_pair():
            result[npp.node_name].append(npp)
        return collections.OrderedDict(sorted(result.items(), key=operator.itemgetter(0)))

    def lookup_node_index(self, node_name):
        # TODO: optimize!
        for i, nn in enumerate(self.list_node_names()):
            if node_name == nn:
                return i
        assert False, node_name

    def edge_count(self):
        return len(self.components)

    def node_count(self):
        return len(self.list_node_names())

    def edge_current_vector(self):  # i
        return [EdgeCurrent(com) for com in self.list_components()]

    def edge_voltage_vector(self):  # v
        return [EdgeVoltage(com) for com in self.list_components()]

    def node_potential_vector(self):  # e
        return [NodePotential(node_name) for node_name in self.list_node_names()]

    def conductance_matrix(self):
        g = np.diagflat([com.conductance for com in self.list_components()])
        assert g.shape == (self.edge_count(), self.edge_count())
        return g

    def voltage_matrix(self):
        ev = np.zeros(shape=(self.edge_count(), self.node_count()))
        for i, com in enumerate(self.list_components()):
            for node_name, current_flow in zip(com.port_mapping, com.clazz.current_flow):
                j = self.lookup_node_index(node_name)
                ev[i, j] = current_flow.value
        return ev

    def kcl(self):
        eqs = {}
        for node_name, npp_lst in self.list_node_names().items():
            for nnp in npp_lst:
                i = EdgeCurrent(nnp.component)
                v = EdgeVoltage(nnp.component)
