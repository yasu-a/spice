import numpy as np

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
                e_proc=lambda ins: ins.model.params['value']
            ),
            ComponentClass(
                name='cs',
                prefix='I',
                port_high='pos',
                port_low='neg',
                current_flow=(CurrentFlow.IN, CurrentFlow.OUT),
                j_proc=lambda ins: ins.model.params['value']
            ),
            ComponentClass(
                name='bv',
                prefix='E',
                port_high='pos',
                port_low='neg',
                current_flow=(CurrentFlow.IN, CurrentFlow.OUT)
            ),
            ComponentClass(
                name='bi',
                prefix='G',
                port_high='pos',
                port_low='neg',
                current_flow=(CurrentFlow.IN, CurrentFlow.OUT)
            ),
            ComponentClass(
                name='r',
                prefix='r',
                port_high='begin',
                port_low='end',
                current_flow=(CurrentFlow.IN, CurrentFlow.OUT),
                g_proc=lambda ins: 1 / ins.model.params['value']
            )
        )
    )

    with open('sample1.cir', 'r') as f:
        netlist = NetList.from_string(
            source=f.read(),
            class_set=class_set
        )

    pprint(netlist.components)

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
