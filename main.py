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

    with open('sample1.cir', 'r') as f:
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

    return

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
    total_dict: dict[object, str] = {}
    for a, (b, c) in dct.items():
        total_dict[a] = b.to_python(ctx) + '-' + c.to_python(ctx)
    for a, (b, c) in ctx['used_edge_currents'].items():
        if a in dct:
            continue
        total_dict[a] = b.to_python(ctx) + '-' + c.to_python(ctx)
    print('total_dict')
    pprint(total_dict)
    xs_name: list[str] = sorted(
        {x for v in total_dict.values() for x in re.findall(r'x__\w_[\w\d]+', v)})
    print('xs_name')
    pprint(xs_name)
    assert len(total_dict) == len(xs_name), (len(total_dict), len(xs_name))

    def expr_to_funcs(var_names: list[str], exprs: list[str]):
        exprs_name_converted: list[str] = []

        for expr in exprs:
            for i, var_name in enumerate(var_names):
                expr = expr.replace(var_name, f'_x[{i}]')
            exprs_name_converted.append(expr)

        f_lst_expr = '[' + ', '.join(expr for expr in exprs_name_converted) + ']'
        f_expr = f'_f_placeholder[0] = lambda _x: {f_lst_expr}'
        f_expr_compiled = compile(f_expr, f'__eqs__', mode='exec')
        _f_placeholder = {}
        exec(f_expr_compiled, dict(_f_placeholder=_f_placeholder))
        f = _f_placeholder[0]
        return f

    func = expr_to_funcs(xs_name, list(total_dict.values()))
    print(func)

    x0 = np.zeros(len(xs_name))
    print(func(x0))

    from scipy.optimize import root

    y = root(func, x0)
    print(y)
    pprint(dict(zip(map('{:10s}'.format, xs_name), map('{:12.8f}'.format, y['x']))))

    x0_min = np.array([7 if name.startswith('x__i_') else 0.01 for name in xs_name])
    x0_max = -x0_min

    # print(np.mgrid[tuple(for v_min, v_max in zip(x0_min, x0_max))])
    #
    # from sklearn.decomposition import PCA
    # from sklearn.preprocessing import StandardScaler
    # from sklearn.pipeline import Pipeline
    #
    # pl = Pipeline([
    #     ('std', StandardScaler())
    #     ('pca', PCA(n_components=2))
    # ])
    #
    # pl.fit()


if __name__ == '__main__':
    main()
