import decimal
import itertools
import math
from builtins import dict

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
    pprint(netlist.ohm())

    print('\nnetlist.kcl')
    pprint(netlist.kcl())

    print('\nnetlist.kvl')
    pprint(netlist.kvl())

    print('\nnetlist.node_potential_substituted_ohms_law')
    pprint(netlist.node_potential_substituted_ohm())

    print('\nnetlist.substituted_kcl')
    pprint(netlist.substituted_kcl())

    print('\nnetlist.expressions_for_potential')
    pprint(netlist.expressions_for_potential())

    print('\nnetlist.expressions_for_current')
    pprint(netlist.expressions_for_current())

    print('\nnetlist.total_equations')
    pprint(netlist.total_equations())

    eqs, x_names = netlist.python_equations_and_variable_names()
    for eq in eqs:
        print(eq, '=', 0)
    print(x_names)

    f, x_names = netlist.python_func_to_solve()
    from scipy.optimize import root
    x0 = np.zeros_like(x_names, dtype=np.float64)
    optimize_result = root(f, x0)
    assert optimize_result.success, optimize_result
    x = optimize_result.x
    print(x)

    def float_to_string(v):
        dct = dict([
            ('zero', 1e-18),
            ('f', 1e-15),
            ('p', 1e-12),
            ('n', 1e-9),
            ('u', 1e-6),
            ('m', 1e-3),
            ('_', 1e+0),
            ('K', 1e+3),
            ('M', 1e+6),
            ('G', 1e+9),
            ('T', 1e+12),
        ])

        u = ' '
        for unit, scale in dct.items():
            if v < scale * 1e+3:
                if unit == 'zero':
                    v = 0
                elif unit == '_':
                    break
                else:
                    v /= scale
                    u = unit
                    break

        return f'{v:9.3f} {u}'

    for n, v in zip(x_names, x):
        print(f'{n:<10s} {float_to_string(v)}')


if __name__ == '__main__':
    main()
