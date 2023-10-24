import itertools
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

    with open('sample3.cir', 'r') as f:
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
    ohm_dct, rec = netlist.node_potential_substituted_ohms_law_equations(rec)
    pprint(rec)
    ctx = dict(var_record=rec, edge_currents=ohm_dct, used_edge_currents={})
    pprint(ctx)
    total_dict = {}
    for a, (b, c) in dct.items():
        total_dict[a] = b.to_python(ctx) + '-' + c.to_python(ctx)
    for a, (b, c) in ctx['used_edge_currents'].items():
        if a in dct:
            continue
        total_dict[a] = b.to_python(ctx) + '-' + c.to_python(ctx)
    pprint(total_dict)
    xs = {x for v in total_dict.values() for x in re.findall(r'x__\w_[\w\d]+', v)}
    pprint(xs)
    assert len(total_dict) == len(xs), (len(total_dict), len(xs))

    k_sorted = sorted(total_dict, key=repr)

    funcs = [f'f_dct[{i}] = lambda {", ".join(xs)}: {total_dict[k]}'
             for i, k in enumerate(k_sorted)]
    pprint(funcs)
    funcs = [compile(f, f'__eq_{i}__', mode='exec') for i, f in enumerate(funcs)]
    # pprint(funcs)
    f_dct = {}
    for f in funcs:
        exec(f, dict(f_dct=f_dct))
    fs = [f_dct[i] for i, k in enumerate(k_sorted)]

    DELTA = 1e-12

    def df_of_f(f, xi):
        def df(x0):
            xl = np.array(x0)
            xl[xi] -= DELTA / 2
            xh = np.array(x0)
            xh[xi] += DELTA / 2
            return (f(*xh) - f(*xl)) / DELTA

        return df

    dfs = [[df_of_f(fs[i], j) for j in range(len(fs))] for i in range(len(fs))]
    pprint(fs)
    pprint(dfs)

    x0 = np.zeros(len(xs))
    for _ in range(100):
        f_x0 = np.array([fs[i](*x0) for i, k in enumerate(k_sorted)])
        print(f_x0)
        jacob = np.array([[dfs[i][j](x0) for j in range(len(fs))] for i in range(len(fs))])
        print(jacob)

        import gauss

        r = gauss.solve(jacob, f_x0[:, None])
        print(r)
        x0 = x0 - r
        print(x0)


if __name__ == '__main__':
    main()
