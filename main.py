import numpy as np

np.set_printoptions(
    formatter={'float_kind': '{:10.6f}'.format}
)

from typing import NamedTuple
import re
from ntpprint import pprint, nt_asdict

from netlist import NetList
from comcls import ComponentClass, ComponentClassSet, CurrentFlow
from comins import ComponentInstance
from model import ComponentModel


def main():
    class_set = ComponentClassSet(
        classes=(
            ComponentClass(
                name='vs',
                prefix='v',
                ports=('pos', 'neg'),
                high_side='pos',
                low_side='neg',
                current_flow=(CurrentFlow.IN, CurrentFlow.OUT),
                e_proc=lambda ins: ins.model.params['value']
            ),
            # ComponentClass(
            #     name='vcvs',
            #     prefix='e',
            #     ports=('pos', 'neg', 'c_pos', 'c_neg'),
            #     current_flow=(CurrentFlow.IN, CurrentFlow.OUT)
            # ),
            ComponentClass(
                name='r',
                prefix='r',
                ports=('begin', 'end'),
                high_side='begin',
                low_side='end',
                current_flow=(CurrentFlow.IN, CurrentFlow.OUT),
                g_proc=lambda ins: 1 / ins.model.params['value']
            )
        )
    )

    with open('netlist.cir', 'r') as f:
        netlist = NetList.from_string(
            source=f.read(),
            class_set=class_set
        )

    # KCL
    node_names = netlist.list_node_port_pair()

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
