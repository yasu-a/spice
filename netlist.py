import itertools
import re

from pprint import pprint

from typing import NamedTuple, TYPE_CHECKING, Callable

import circuit_equation as ceq
import expression as ex
from edge import Edge
from node import Node

if TYPE_CHECKING:
    from comcls import ComponentClassSet
    from comins import ComponentInstance, NodePortPair
    import numpy as np


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

    def ohm(self) -> ceq.LinearEquationSet:
        # i = Gv
        eqs = ceq.LinearEquationSet(
            ceq.LinearEquation.from_left_and_right(
                left=ceq.EdgeCurrent(edge),
                right=ceq.EdgeVoltage(edge).term(edge.component.conductance)
            )
            for edge in self.edges
            if edge.component.conductance is not None
        )

        assert eqs.check_type(), eqs

        return eqs

    def kcl(self) -> ceq.LinearEquationSet:
        # i_1 + i_2 + ... + i_n = 0
        eqs = ceq.LinearEquationSet()
        for node in self.nodes:
            nnp_with_node = self.ports_with_node(node)
            cfs = [
                nnp.component.current_flow(nnp.port_name)
                for nnp in nnp_with_node
            ]  # current flows
            eq = ceq.LinearEquation.from_left([
                ceq.EdgeCurrent(Edge(nnp.component)).term(ex.Constant(cf.value))
                for nnp, cf in zip(nnp_with_node, cfs)
            ])
            eqs.append(eq)

        assert eqs.check_type(), eqs

        return eqs

    def kvl(self) -> ceq.LinearEquationSet:
        # v = e_high - e_low
        eqs = ceq.LinearEquationSet()
        for edge in self.edges:
            node_high = edge.component.port_to_node[edge.component.clazz.port_high]
            node_low = edge.component.port_to_node[edge.component.clazz.port_low]
            eq = ceq.LinearEquation.from_left_and_right(
                left=ceq.EdgeVoltage(edge),
                right=[
                    ceq.NodePotential(node).term(sign)
                    for node, sign in zip([node_high, node_low], [ex.POS_ONE, ex.NEG_ONE])
                ]
            )
            eqs.append(eq)

        assert eqs.check_type(), eqs

        return eqs

    def node_potential_substituted_ohm(self) -> ceq.LinearEquationSet:
        # i = G e_high - G e_low
        ohm = self.ohm()
        kvl = self.kvl()

        ohm <<= kvl

        assert ohm.check_type(), ohm

        return ohm

    def substituted_kcl(self) -> ceq.LinearEquationSet:
        # Ge = 0
        ohm = self.node_potential_substituted_ohm()
        kcl = self.kcl()

        kcl <<= ohm

        assert kcl.check_type(), kcl

        return kcl

    def expressions_for_current(self) -> ceq.LinearEquationSet:
        # i = const.
        return ceq.LinearEquationSet(
            ceq.LinearEquation.from_left_and_right(
                left=ceq.EdgeCurrent(edge),
                right=edge.component.constant_current
            )
            for edge in self.edges
            if edge.component.constant_current is not None
        )

    def expressions_for_voltage(self) -> ceq.LinearEquationSet:
        # v = const.
        return ceq.LinearEquationSet(
            ceq.LinearEquation.from_left_and_right(
                left=ceq.EdgeVoltage(edge),
                right=edge.component.constant_voltage
            )
            for edge in self.edges
            if edge.component.constant_voltage is not None
        )

    def expressions_for_potential(self) -> ceq.LinearEquationSet:
        # e_high -  e_low = const.
        expr_vol = self.expressions_for_voltage()
        kvl = self.kvl()

        expr_vol <<= kvl

        for node in self.nodes:
            if node.is_grounded:
                expr_vol.append(
                    ceq.LinearEquation.from_left_and_right(
                        left=ceq.NodePotential(node),
                        right=0
                    )
                )

        assert expr_vol.check_type(), expr_vol

        return expr_vol

    def _parse_variable_to_expr(self, variable, record):
        if isinstance(variable, ceq.EdgeCurrent):
            result = ex.Variable(name=f'x__i_{variable.edge.component.name.lower()}')
        elif isinstance(variable, ceq.NodePotential):
            result = ex.Variable(name=f'x__e_{variable.node.name.lower()}')
        else:
            assert False, variable
        record[variable] = result
        return result

    def total_equations(self) -> ceq.LinearEquationSet:
        # -> dict[Node | ceq.EdgeVoltage | ceq.EdgeCurrent, tuple[ex.ExprNode, ex.ExprNode]]:
        eqs = ceq.LinearEquationSet()

        kcl = self.substituted_kcl()
        kcl.pop(0)  # eliminate one of kcl
        eqs += kcl

        const_e = self.expressions_for_potential()
        eqs += const_e

        const_i = self.expressions_for_current()
        eqs += const_i

        return eqs

    def node_potential_substituted_ohms_law_equations(self, var_record=None):
        ohm = self.node_potential_substituted_ohm()
        ohm <<= self.expressions_for_voltage()
        return ohm

    def name_to_circuit_var_mapping(self) -> dict[str, ceq.CircuitVariable]:
        def iter_objects():
            yield from map(ceq.EdgeVoltage, self.edges)
            yield from map(ceq.EdgeCurrent, self.edges)
            yield from map(ceq.NodePotential, self.nodes)

        return dict(
            obj.name_to_circuit_var_mapping_entry()
            for obj in iter_objects()
        )

    def _replace_equation_probes(self, eqs: list[str]) -> list[str]:
        mapping = self.name_to_circuit_var_mapping()
        pprint(mapping)

        def replace(formula: str):
            def repl(m):
                if m[1].startswith('_v_'):
                    if m[2] in (node.name for node in self.nodes):
                        return '_e_' + m[2].lower()
                return m[1].lower()

            return re.sub(r'__probe(_[iv]_([\w\d_]+))', repl, formula)

        return [replace(formula) for formula in eqs]

    def python_equations_and_variable_names(self) -> tuple[list[str], list[str]]:
        eqs = self._replace_equation_probes(
            self.total_equations().to_python()
        )
        print(len(eqs))

        variable_names = sorted({
            x for eq in eqs for x in re.findall(r'_[ive]_[\w\d]+', eq)
        })

        additional_ohms = self.node_potential_substituted_ohms_law_equations()
        pprint([eq.left.first.element.var_name for eq in additional_ohms])
        additional_eqs = ceq.LinearEquationSet(
            eq
            for eq in additional_ohms
            if eq.left.first.element.var_name in variable_names
        )
        pprint(additional_eqs)
        eqs += additional_eqs.to_python()

        assert len(eqs) == len(variable_names), (len(eqs), len(variable_names), variable_names)

        return eqs, variable_names

    def python_func_to_solve(self) -> tuple[Callable[['np.ndarray'], 'np.ndarray'], list]:
        formulas, x_names = self.python_equations_and_variable_names()

        array_assigned_x_names = {x_name: f'_x[{i}]' for i, x_name in enumerate(x_names)}

        for i in range(len(formulas)):
            for k, v in array_assigned_x_names.items():
                formulas[i] = formulas[i].replace(k, v)

        f_lst_expr = '[' + ', '.join(f for f in formulas) + ']'
        f_expr = f'_f_placeholder[0] = lambda _x: {f_lst_expr}'
        f_expr_compiled = compile(f_expr, f'__eqs__', mode='exec')
        _f_placeholder = {}
        exec(f_expr_compiled, dict(_f_placeholder=_f_placeholder))
        f = _f_placeholder[0]
        assert callable(f), f

        return f, x_names
