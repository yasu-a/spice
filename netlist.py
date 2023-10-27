from typing import NamedTuple, TYPE_CHECKING

import circuit_equation as ceq
import expression as ex
from edge import Edge
from node import Node

if TYPE_CHECKING:
    from comcls import ComponentClassSet
    from comins import ComponentInstance, NodePortPair


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
        # -> dict[EdgeCurrent, tuple[EdgeVoltage, ex.ExprNode]]:
        # i = Gv
        eqs = ceq.LinearEquationSet(
            ceq.LinearEquation.from_left_and_right(
                left=ceq.EdgeCurrent(edge).term(),
                right=ceq.EdgeVoltage(edge).term(edge.component.conductance)
            )
            for edge in self.edges
            if edge.component.conductance is not None
        )

        assert eqs.check_type(), eqs

        return eqs

    def kcl(self) -> ceq.LinearEquationSet:
        #  -> dict[Node, list[tuple[EdgeCurrent, ex.ExprNode]]]:
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
        # -> dict[EdgeVoltage, dict[NodePotential, ex.ExprNode]]:
        # v = e_high - e_low
        eqs = ceq.LinearEquationSet()
        for edge in self.edges:
            node_high = edge.component.port_to_node[edge.component.clazz.port_high]
            node_low = edge.component.port_to_node[edge.component.clazz.port_low]
            eq = ceq.LinearEquation.from_left_and_right(
                left=ceq.EdgeVoltage(edge).term(),
                right=[
                    ceq.NodePotential(node).term(sign)
                    for node, sign in zip([node_high, node_low], [ex.POS_ONE, ex.NEG_ONE])
                ]
            )
            eqs.append(eq)

        assert eqs.check_type(), eqs

        return eqs

    def node_potential_substituted_ohm(self) -> ceq.LinearEquationSet:
        # -> dict[EdgeCurrent, list[tuple[NodePotential, ex.ExprNode]]]:
        # i = G e_high - G e_low
        ohm = self.ohm()
        kvl = self.kvl()

        ohm <<= kvl

        assert ohm.check_type(), ohm

        return ohm

    def substituted_kcl(self) -> ceq.LinearEquationSet:
        # -> dict[Node, tuple[ceq.Variable, ex.ExprNode]]:
        # Ge = 0
        ohm = self.node_potential_substituted_ohm()
        kcl = self.kcl()

        kcl <<= ohm

        assert kcl.check_type(), kcl

        return kcl

    def expressions_for_voltage(self) -> dict[ceq.EdgeVoltage, ex.ExprNode]:
        dct = {}
        for edge in self.edges:
            if edge.component.constant_voltage is None:
                continue
            dct[ceq.EdgeVoltage(edge)] = edge.component.constant_voltage
        return dct

    def expressions_for_potential(self) \
            -> dict[
                ceq.EdgeVoltage, tuple[list[tuple[ceq.NodePotential, ex.ExprNode]], ex.ExprNode]]:
        expr_vol = self.expressions_for_voltage()
        kvl = self.kvl()

        for edge_voltage, expr in list(expr_vol.items()):
            expr_vol[edge_voltage] = []
            for node_potential, sign in kvl[edge_voltage].items():
                expr_vol[edge_voltage].append((node_potential, sign))
            expr_vol[edge_voltage] = expr_vol[edge_voltage], expr

        expr_vol[None] = [(NodePotential(Node('0')), ex.POS_ONE)], ex.ZERO

        return expr_vol

    def expressions_for_current(self) -> dict[ceq.EdgeCurrent, ex.ExprNode]:
        dct = {}
        for edge in self.edges:
            if edge.component.constant_current is None:
                continue
            dct[ceq.EdgeCurrent(edge)] = edge.component.constant_current
        return dct

    def _parse_variable_to_expr(self, variable, record):
        if isinstance(variable, ceq.EdgeCurrent):
            result = ex.Variable(name=f'x__i_{variable.edge.component.name.lower()}')
        elif isinstance(variable, ceq.NodePotential):
            result = ex.Variable(name=f'x__e_{variable.node.name.lower()}')
        else:
            assert False, variable
        record[variable] = result
        return result

    def total_equations(self, var_record=None) \
            -> dict[Node | ceq.EdgeVoltage | ceq.EdgeCurrent, tuple[ex.ExprNode, ex.ExprNode]]:
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
            -> dict[ceq.EdgeCurrent, tuple[ex.ExprNode, ex.ExprNode]]:
        ohm = self.node_potential_substituted_ohm()
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
