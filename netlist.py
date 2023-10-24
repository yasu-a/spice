import math

from frozendict import frozendict
from pprint import pprint
import collections
import operator
from dataclasses import dataclass
from typing import NamedTuple, TYPE_CHECKING, Any
from model import ComponentModel
import numpy as np

import expression as ex

if TYPE_CHECKING:
    from comcls import ComponentClassSet
    from comins import ComponentInstance, NodePortPair
from node import Node


@dataclass(frozen=True)
class NameGettable:
    @property
    def name(self):
        raise NotImplementedError()


@dataclass(frozen=True)
class EdgePropertyBase(NameGettable):
    edge: 'Edge'

    @property
    def name(self):
        return self.edge.component.name

    def __repr__(self):
        return f'{type(self).__name__}(edge_name={self.edge.component.name!r})'

    def __lt__(self, other):
        if not isinstance(other, EdgePropertyBase):
            return NotImplemented
        if self.edge < other.edge:
            return True
        return False


class EdgeCurrent(EdgePropertyBase):
    pass


class EdgeVoltage(EdgePropertyBase):
    pass


@dataclass(frozen=True)
class NodePropertyBase(NameGettable):
    node: 'Node'

    @property
    def name(self):
        return self.node.name

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


def parse_linear(node: ex.ExprNode):
    print(node)
    if not isinstance(node, ex.OpMul):
        return None
    if isinstance(node.b, ex.Constant):
        node = ex.OpMul(a=node.b, b=node.a)
    if not isinstance(node.a, ex.Constant):
        return None
    if isinstance(node.b, ex.OpUSub):
        node = ex.OpMul(a=ex.OpUSub(node.a), b=node.b.a)
    if not isinstance(node.b, ex.Function):
        return None
    if len(node.b.args) != 1:
        return None
    if not isinstance(node.b.args[0], ex.Constant):
        return None
    return ComponentModel(
        name='linear',
        params=frozendict(
            factor=node.a.evaluate(),
            edge_name=node.b.args[0].as_name(),
            probe_type=node.b.name
        )
    )


def split_behavioral_name_and_expr(expr: ex.ExprNode):
    if not isinstance(expr, ex.NamedValue):
        return None
    return expr.var_name, expr.node


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

        # re-parse models
        for i, com in enumerate(components):
            if com.clazz is None:
                var_name, model_expr = split_behavioral_name_and_expr(com.model.expr)
                ins = class_set.parse_netlist_line(
                    line=com.source_line,
                    force_prefix=var_name,
                    force_expr=model_expr
                )
                assert ins is not None
                components[i] = ins

        return cls(
            title=title,
            components=tuple(components),
            commands=tuple(commands)
        )

    @property
    def edges(self) -> list[Edge]:
        return sorted(Edge(com) for com in self.components)

    @property
    def nodes(self) -> list[Node]:
        return sorted({node for com in self.components for node in com.nodes})

    def ports_with_node(self, node: Node) -> list['NodePortPair']:
        lst = []
        for com in self.components:
            nnp_lst = com.list_node_and_port()
            for nnp in nnp_lst:
                if nnp.node == node:
                    lst.append(nnp)
        return lst

    def ohms_law(self) -> dict[EdgeCurrent, tuple[EdgeVoltage, ex.ExprNode]]:
        dct = {}
        for edge in self.edges:
            if edge.component.conductance is None:
                continue
            dct[EdgeCurrent(edge)] = EdgeVoltage(edge), edge.component.conductance
        return dct

    def kcl(self) -> dict[Node, list[tuple[EdgeCurrent, ex.ExprNode]]]:
        dct = {}
        for node in self.nodes:
            nnp_with_node = self.ports_with_node(node)
            cfs = [nnp.component.current_flow(nnp.port_name) for nnp in nnp_with_node]
            dct[node] = []
            for nnp, cf in zip(nnp_with_node, cfs):
                dct[node].append((EdgeCurrent(Edge(nnp.component)), ex.Constant(cf.value)))
        return dct

    def kvl(self) -> dict[EdgeVoltage, dict[NodePotential, ex.ExprNode]]:
        dct = {}
        for edge in self.edges:
            node_high = edge.component.port_to_node[edge.component.clazz.port_high]
            node_low = edge.component.port_to_node[edge.component.clazz.port_low]
            dct[EdgeVoltage(edge)] = {}
            for node, sign in zip([node_high, node_low], [ex.POS_ONE, ex.NEG_ONE]):
                dct[EdgeVoltage(edge)][NodePotential(node)] = sign
        return dct

    def node_potential_substituted_ohms_law(self) \
            -> dict[EdgeCurrent, list[tuple[NodePotential, ex.ExprNode]]]:
        ohm = self.ohms_law()
        kvl = self.kvl()

        for edge_current, (edge_voltage, g) in list(ohm.items()):
            ohm[edge_current] = []
            for node_potential, sign in kvl[edge_voltage].items():
                ohm[edge_current].append((node_potential, sign * g))
            ohm[edge_current] = tuple(ohm[edge_current])

        return ohm

    def substituted_kcl(self) \
            -> dict[Node, tuple[EdgeCurrent | EdgeVoltage | NodePotential, ex.ExprNode]]:
        ohm = self.node_potential_substituted_ohms_law()
        kcl = self.kcl()

        for node, kcl_node in list(kcl.items()):
            kcl[node] = []
            for edge_current, sign in kcl_node:
                if edge_current in ohm:
                    for node_potential, g in ohm[edge_current]:
                        kcl[node].append((node_potential, sign * g))
                else:
                    kcl[node].append((edge_current, sign))

        return kcl

    def expressions_for_voltage(self) -> dict[EdgeVoltage, ex.ExprNode]:
        dct = {}
        for edge in self.edges:
            if edge.component.constant_voltage is None:
                continue
            dct[EdgeVoltage(edge)] = edge.component.constant_voltage
        return dct

    def expressions_for_potential(self) \
            -> dict[EdgeVoltage, tuple[list[tuple[NodePotential, ex.ExprNode]], ex.ExprNode]]:
        expr_vol = self.expressions_for_voltage()
        kvl = self.kvl()

        for edge_voltage, expr in list(expr_vol.items()):
            expr_vol[edge_voltage] = []
            for node_potential, sign in kvl[edge_voltage].items():
                expr_vol[edge_voltage].append((node_potential, sign))
            expr_vol[edge_voltage] = expr_vol[edge_voltage], expr

        expr_vol[None] = [(NodePotential(Node('0')), ex.POS_ONE)], ex.ZERO

        return expr_vol

    def expressions_for_current(self) -> dict[EdgeCurrent, ex.ExprNode]:
        dct = {}
        for edge in self.edges:
            if edge.component.constant_current is None:
                continue
            dct[EdgeCurrent(edge)] = edge.component.constant_current
        return dct

    def _parse_variable_to_expr(self, variable, record):
        if isinstance(variable, EdgeCurrent):
            result = ex.Variable(name=f'x__i_{variable.edge.component.name.lower()}')
        elif isinstance(variable, NodePotential):
            result = ex.Variable(name=f'x__e_{variable.node.name.lower()}')
        else:
            assert False, variable
        record[variable] = result
        return result

    def total_equations(self, var_record=None) \
            -> dict[Node | EdgeVoltage | EdgeCurrent, tuple[ex.ExprNode, ex.ExprNode]]:
        var_record = var_record or {}
        dct = {}

        for node, terms in self.substituted_kcl().items():
            total_expr = None
            for var, expr in terms:
                var = self._parse_variable_to_expr(var, record=var_record)
                expr = expr * var
                if total_expr is None:
                    total_expr = expr
                else:
                    total_expr = ex.OpAdd(total_expr, expr)
            dct[node] = total_expr.simplify(), ex.ZERO.simplify()
        dct.popitem()  # eliminate one of kcl

        for edge_voltage, (terms, edge_voltage_given) in self.expressions_for_potential().items():
            total_expr = None
            for var, expr in terms:
                var = self._parse_variable_to_expr(var, record=var_record)
                expr = expr * var
                if total_expr is None:
                    total_expr = expr
                else:
                    total_expr = ex.OpAdd(total_expr, expr)
            dct[edge_voltage] = total_expr.simplify(), edge_voltage_given.simplify()

        # dict[EdgeCurrent, ex.ExprNode]
        for edge_current, edge_current_given in self.expressions_for_current().items():
            var = self._parse_variable_to_expr(edge_current, record=var_record)
            dct[edge_current] = var.simplify(), edge_current_given.simplify()

        return dct, var_record

    def node_potential_substituted_ohms_law_equations(self, var_record=None) \
            -> dict[EdgeCurrent, tuple[ex.ExprNode, ex.ExprNode]]:
        ohm = self.node_potential_substituted_ohms_law()
        var_record = var_record or {}
        dct = {}
        for edge_current, terms in ohm.items():
            total_expr = None
            for var, expr in terms:
                var = self._parse_variable_to_expr(var, record=var_record)
                expr = expr * var
                if total_expr is None:
                    total_expr = expr
                else:
                    total_expr = ex.OpAdd(total_expr, expr)
            edge_current_var = self._parse_variable_to_expr(edge_current, record=var_record)
            dct[edge_current] = edge_current_var.simplify(), total_expr.simplify()

        return dct, var_record
