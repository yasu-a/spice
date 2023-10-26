import functools
import math
from abc import ABC

from frozendict import frozendict
from pprint import pprint
import collections
import operator
from dataclasses import dataclass
from typing import NamedTuple, TYPE_CHECKING, Any, TypeVar
from model import ComponentModel
import numpy as np

import expression as ex

if TYPE_CHECKING:
    from comcls import ComponentClassSet
    from comins import ComponentInstance, NodePortPair
from node import Node


@dataclass(frozen=True)
class NameGettable:
    @classmethod
    def _name_source(cls) -> str:
        raise NotImplementedError()

    def _order_sources(self) -> tuple:
        return getattr(self, self._name_source()),

    def __lt__(self, other):
        if not isinstance(other, type(self)):
            return NotImplemented
        for this_src, other_src \
                in zip(self._order_sources(), other._order_sources()):
            if this_src < other_src:
                return True
        return False

    @property
    def name(self):
        raise NotImplementedError()

    def __repr__(self):
        return f'{type(self).__name__}({self._name_source()}={self.name!r})'


@dataclass(frozen=True)
class CircuitVariable(NameGettable, ABC):
    @classmethod
    def _suffix(cls):
        raise NotImplementedError()

    def to_expr_variable(self):
        return ex.Variable(name=f'_{self._suffix()}_{self.name.lower()}')

    def term(self, k=None):
        if k is None:
            k = ex.POS_ONE
        return LinearTerm(k=k, element=self)


@dataclass(frozen=True)
class EdgeProperty(CircuitVariable, ABC):
    edge: 'Edge'

    @property
    def name(self):
        return self.edge.component.name

    @classmethod
    def _name_source(cls) -> str:
        return 'edge'


class EdgeCurrent(EdgeProperty):
    @classmethod
    def _suffix(cls):
        return 'i'


class EdgeVoltage(EdgeProperty):

    @classmethod
    def _suffix(cls):
        return 'v'


@dataclass(frozen=True)
class NodeProperty(CircuitVariable, ABC):
    node: 'Node'

    @property
    def name(self):
        return self.node.name

    @classmethod
    def _name_source(cls) -> str:
        return 'node'


class NodePotential(NodeProperty):
    @classmethod
    def _suffix(cls):
        return 'e'


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


def split_behavioral_name_and_expr(expr: ex.ExprNode):
    if not isinstance(expr, ex.NamedValue):
        return None
    return expr.var_name, expr.node


class LinearTerm:
    def __init__(self, k: ex.ExprNode, element: CircuitVariable):
        self.__k = k
        self.__element = element

    @property
    def k(self):
        return self.__k

    @property
    def element(self):
        return self.__element

    def __neg__(self):
        return LinearTerm(
            k=-self.k,
            element=self.element
        )

    def __mul__(self, other):
        if isinstance(other, float):
            other = ex.Constant(other)
        if not isinstance(other, ex.ExprNode):
            return NotImplemented
        return LinearTerm(
            k=ex.OpMul(other, self.k).simplify(),
            element=self.element
        )

    def __repr__(self):
        var_name = self.element.to_expr_variable().name
        k = self.k.simplify().evaluate_if_possible()
        if k == 1:
            k = ''
        if isinstance(k, float):
            k = f'{k:.6f}'
        return f'{k!s:>8s} {var_name:>7s}'


class LinearTerms:
    @classmethod
    def _coerce_to_list_of_terms(cls, obj) -> list[LinearTerm]:
        if obj == 0:
            return []

        try:
            it = iter(obj)
        except TypeError:
            if isinstance(obj, LinearTerms):
                obj = list(obj.__terms)
            elif isinstance(obj, LinearTerm):
                obj = [obj]
            else:
                raise TypeError(obj)
        else:
            obj = list(it)

        if isinstance(obj, list):
            for elm in obj:
                if not isinstance(elm, LinearTerm):
                    raise TypeError(obj)
        else:
            raise TypeError(obj)

        return obj

    def __init__(self, terms):
        self.__terms: list[LinearTerm] = self._coerce_to_list_of_terms(terms)

    def __neg__(self):
        return LinearTerms(map(operator.neg, self.__terms))

    def __add__(self, other):
        other = LinearTerms(other)
        return LinearTerms(self.__terms + other.__terms)

    @classmethod
    def sum(cls, terms):
        return LinearTerms([
            term
            for item in terms
            for term in cls._coerce_to_list_of_terms(item)
        ])

    def __sub__(self, other):
        other = LinearTerms(other)
        return LinearTerms(self.__terms + (-other).__terms)

    def __mul__(self, other):
        return LinearTerms(term * other for term in self.__terms)

    def __repr__(self):
        if not self.__terms:
            return '0'
        return ' + '.join(map(str, self.__terms))

    def __lshift__(self, other: list['LinearEquation']):
        src_eqs, dst_terms = other, self

        for src_eq in src_eqs:
            if len(src_eq.left.__terms) != 1:
                raise ValueError(other)

        terms_lut: dict[CircuitVariable, LinearTerms] = {
            src_eq.left.__terms[0].element: src_eq.right
            for src_eq in src_eqs
        }
        assigned_terms = []
        for dst_term in dst_terms.__terms:
            assignment = terms_lut.get(dst_term.element)
            if assignment:
                new_terms = assignment * dst_term.k
            else:
                new_terms = LinearTerms(dst_term)
            assigned_terms.append(new_terms)
        return LinearTerms.sum(assigned_terms)


@dataclass()
class LinearEquation:
    left: LinearTerms
    right: LinearTerms

    def __repr__(self):
        return f'{self.left} = {self.right}'

    def to_equation(self) -> 'LinearEquation':
        return self

    def __neg__(self):
        return LinearEquation(
            left=-self.left,
            right=-self.right
        )

    def __add__(self, other):
        if not isinstance(other, LinearEquation):
            return NotImplemented
        return LinearEquation(
            left=self.left + other.left,
            right=self.right + other.right
        )

    def __sub__(self, other):
        if not isinstance(other, LinearEquation):
            return NotImplemented
        return LinearEquation(
            left=self.left - other.left,
            right=self.right - other.right
        )

    @classmethod
    def from_left_and_right(cls, left, right):
        return LinearEquation(
            left=LinearTerms(left),
            right=LinearTerms(right)
        )

    @classmethod
    def from_left(cls, left):
        return LinearEquation(
            left=LinearTerms(left),
            right=LinearTerms(0)
        )

    def __ilshift__(self, other):
        if not isinstance(other, list):
            return NotImplemented
        for item in other:
            if not isinstance(item, LinearEquation):
                return NotImplemented
        self.right = self.right << other


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

    def ohms_law(self) -> list[LinearEquation]:
        # -> dict[EdgeCurrent, tuple[EdgeVoltage, ex.ExprNode]]:
        # i = Gv
        eqs = [
            LinearEquation.from_left_and_right(
                left=EdgeCurrent(edge).term(),
                right=EdgeVoltage(edge).term(edge.component.conductance)
            )
            for edge in self.edges
            if edge.component.conductance is not None
        ]
        return eqs

    def kcl(self) -> list[LinearEquation]:
        #  -> dict[Node, list[tuple[EdgeCurrent, ex.ExprNode]]]:
        # i_1 + i_2 + ... + i_n = 0
        eqs = []
        for node in self.nodes:
            nnp_with_node = self.ports_with_node(node)
            cfs = [
                nnp.component.current_flow(nnp.port_name)
                for nnp in nnp_with_node
            ]  # current flows
            eq = LinearEquation.from_left([
                EdgeCurrent(Edge(nnp.component)).term(ex.Constant(cf.value))
                for nnp, cf in zip(nnp_with_node, cfs)
            ])
            eqs.append(eq)

        return eqs

    def kvl(self) -> list[LinearEquation]:
        # -> dict[EdgeVoltage, dict[NodePotential, ex.ExprNode]]:
        # v = e_high - e_low
        eqs = []
        for edge in self.edges:
            node_high = edge.component.port_to_node[edge.component.clazz.port_high]
            node_low = edge.component.port_to_node[edge.component.clazz.port_low]
            eq = LinearEquation.from_left_and_right(
                left=EdgeVoltage(edge).term(),
                right=[
                    NodePotential(node).term(sign)
                    for node, sign in zip([node_high, node_low], [ex.POS_ONE, ex.NEG_ONE])
                ]
            )
            eqs.append(eq)
        return eqs

    def node_potential_substituted_ohms_law(self) -> list[LinearEquation]:
        # -> dict[EdgeCurrent, list[tuple[NodePotential, ex.ExprNode]]]:
        ohm = self.ohms_law()
        kvl = self.kvl()

        for ohm_eq in ohm:
            ohm_eq <<= kvl

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
