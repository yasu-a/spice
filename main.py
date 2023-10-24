import numpy as np
import expression as ex

np.set_printoptions(
    formatter={'float_kind': '{:10.6f}'.format}
)

from typing import NamedTuple
import re
from ntpprint import pprint, nt_asdict

from netlist import NetList
from comcls import ComponentClass, ComponentClassSet, CurrentFlow


def main():
    class_set = ComponentClassSet(
        classes=(
            ComponentClass(
                name='vs',
                prefix='v',
                port_high='pos',
                port_low='neg',
                current_flow=(CurrentFlow.IN, CurrentFlow.OUT),
                e_proc=lambda ins: ins.model.expr
            ),
            ComponentClass(
                name='cs',
                prefix='I',
                port_high='pos',
                port_low='neg',
                current_flow=(CurrentFlow.IN, CurrentFlow.OUT),
                j_proc=lambda ins: ins.model.expr
            ),
            ComponentClass(
                name='r',
                prefix='r',
                port_high='begin',
                port_low='end',
                current_flow=(CurrentFlow.IN, CurrentFlow.OUT),
                g_proc=lambda ins: ex.OpInvert(ins.model.expr)
            )
        )
    )

    with open('sample2.cir', 'r') as f:
        netlist = NetList.from_string(
            source=f.read(),
            class_set=class_set
        )

    print('\nnetlist.components')
    pprint(netlist.components)

    print('\nnetlist.ohms_law')
    pprint(netlist.ohms_law())

    print('\nnetlist.kcl')
    pprint(netlist.kcl())

    print('\nnetlist.kvl')
    pprint(netlist.kvl())

    print('\nnetlist.substituted_kcl')
    pprint(netlist.substituted_kcl())

    print('\nnetlist.expressions_for_potential')
    pprint(netlist.expressions_for_potential())

    print('\nnetlist.expressions_for_current')
    pprint(netlist.expressions_for_current())

    print('\nnetlist.total_equations')
    pprint(netlist.total_equations())

    print()
    dct, rec = netlist.total_equations()
    pprint(rec)
    ctx = dict(var_record=rec)
    for a, (b, c) in dct.items():
        print(a)
        print(b.to_python(ctx), '=', c.to_python(ctx))

    return

    # print(netlist.edge_voltage_vector())
    print(netlist.conductance_matrix())
    # print(netlist.edge_current_vector())

    # print(netlist.node_potential_vector())
    print(netlist.kcl())
    # print(netlist.edge_current_vector())

    # print(netlist.edge_voltage_vector())
    print(netlist.kvl())
    # print(netlist.node_potential_vector())

    # print(netlist.edge_voltage_vector())
    print(netlist.constant_voltage())

    # print(netlist.edge_current_vector())
    print(netlist.constant_current())

    P = np.nan_to_num(netlist.kcl(), nan=0)
    G = np.nan_to_num(netlist.conductance_matrix(), nan=0)
    Esd = np.nan_to_num(netlist.kvl(), nan=0)
    M = np.matmul(np.matmul(P, G), Esd)

    print(M)
    print(netlist.node_potential_vector())

    # pprint(nt_asdict(netlist.conductance_matrix()))


if __name__ == '__main__':
    main()
