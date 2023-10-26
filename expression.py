from frozendict import frozendict
import ast
import re
from typing import TypeVar
from dataclasses import dataclass

EVAL_DEFAULT_SELF = object()

T = TypeVar('T')


@dataclass(frozen=True)
class ExprNode:
    def evaluate(self) -> float:
        raise NotImplementedError()

    def evaluate_if_possible(self, default=EVAL_DEFAULT_SELF):
        try:
            return self.evaluate()
        except NotImplementedError:
            if default == EVAL_DEFAULT_SELF:
                return self
            else:
                return default

    def children(self):
        raise NotImplementedError()

    def _py_unary_operation(self, clazz: type['UnaryOperator']):
        return clazz(a=self)

    def _py_binary_operation(self, other, clazz: type['BinaryOperator']):
        if isinstance(other, (float, int)):
            other = Constant(other)
        if not isinstance(other, ExprNode):
            return NotImplemented
        return clazz(a=self, b=other)

    def __neg__(self):
        return self._py_unary_operation(OpUSub)

    def __add__(self, other):
        return self._py_binary_operation(other, OpAdd)

    def __mul__(self, other):
        return self._py_binary_operation(other, OpMul)

    def simplify(self) -> 'ExprNode':
        return self

    def to_python(self, ctx) -> str:
        raise NotImplementedError()


@dataclass(frozen=True)
class Constant(ExprNode):
    value: float

    def evaluate(self) -> float:
        return self.value

    def children(self):
        yield from []

    def as_name(self):
        return str(int(self.value))

    def to_python(self, ctx) -> str:
        return repr(self.value)


POS_ONE = Constant(+1)
ZERO = Constant(0)
NEG_ONE = Constant(-1)


@dataclass(frozen=True)
class BinaryOperator(ExprNode):
    a: ExprNode
    b: ExprNode

    @classmethod
    def _calc_impl(cls, a, b) -> float:
        raise NotImplementedError()

    def evaluate(self) -> float:
        return self._calc_impl(self.a, self.b)

    def children(self):
        yield self.b
        yield self.a

    def simplify(self) -> 'ExprNode':
        ins = type(self)(self.a.simplify(), self.b.simplify())
        try:
            return Constant(ins.evaluate())
        except NotImplementedError:
            return ins


@dataclass(frozen=True)
class OpAdd(BinaryOperator):
    @classmethod
    def _calc_impl(cls, a, b) -> float:
        return a.evaluate() + b.evaluate()

    def to_python(self, ctx) -> str:
        return '(' + self.a.to_python(ctx) + ' + ' + self.b.to_python(ctx) + ')'


@dataclass(frozen=True)
class OpMul(BinaryOperator):
    @classmethod
    def _calc_impl(cls, a, b) -> float:
        return a.evaluate() * b.evaluate()

    def to_python(self, ctx) -> str:
        return '(' + self.a.to_python(ctx) + ' * ' + self.b.to_python(ctx) + ')'


@dataclass(frozen=True)
class UnaryOperator(ExprNode):
    a: ExprNode

    @classmethod
    def _calc_impl(cls, a) -> float:
        raise NotImplementedError()

    def evaluate(self) -> float:
        return self._calc_impl(self.a)

    def children(self):
        yield self.a

    def simplify(self) -> 'ExprNode':
        ins = type(self)(self.a.simplify())
        try:
            return Constant(ins.evaluate())
        except NotImplementedError:
            return ins


@dataclass(frozen=True)
class OpUSub(UnaryOperator):
    @classmethod
    def _calc_impl(cls, a) -> float:
        return -a.evaluate()

    def to_python(self, ctx) -> str:
        return '-(' + self.a.to_python(ctx) + ')'


@dataclass(frozen=True)
class OpInvert(UnaryOperator):
    @classmethod
    def _calc_impl(cls, a) -> float:
        return 1 / a.evaluate()

    def to_python(self, ctx) -> str:
        return '(1 / ' + self.a.to_python(ctx) + ')'


@dataclass(frozen=True)
class Function(ExprNode):
    name: str
    args: tuple[ExprNode]

    def children(self):
        yield from self.args

    def to_python(self, ctx) -> str:
        return self.name + '(' + ', '.join(arg.to_python(ctx) for arg in self.args) + ')'


@dataclass(frozen=True)
class Variable(ExprNode):
    name: str

    def children(self):
        yield from []

    def to_python(self, ctx) -> str:
        return self.name

    def as_name(self) -> str:
        return self.name


@dataclass(frozen=True)
class Probe(Variable):
    pass


@dataclass(frozen=True)
class VoltageProbe(Probe):
    def to_python(self, ctx) -> str:
        var_record = ctx['var_record']
        for k, v in var_record.items():
            # FIXME!: check type with `isinstance`
            if type(k).__name__.startswith('NodePotential') and k.name == self.name:
                return v.name
        assert False, ctx


@dataclass(frozen=True)
class CurrentProbe(Probe):
    def to_python(self, ctx) -> str:
        for k, (var, expr) in ctx['edge_currents'].items():
            # FIXME!: check type with `isinstance`
            if type(k).__name__.startswith('EdgeCurrent') and k.name == self.name:
                ctx['used_edge_currents'][k] = expr, var
                return var.name
        assert False, ctx


@dataclass(frozen=True)
class NamedValue(ExprNode):
    var_name: str
    node: ExprNode

    def evaluate(self):
        return self.node.evaluate()

    def children(self):
        yield from []


# def _walk(self, current=None):
#     current = current or self.__root
#     for child in current.children():
#         yield from self._walk(child)
#     yield current

# def partial_eval(self, current=None):
#     current = current or self.__root
#     for child in current.children():
#         child.partial_eval()
#     try:
#         current = Constant(current.evaluate())
#     except NotImplementedError:
#         # TODO: optimize by memorize with returning eval result as boolean
#         pass
#     yield current
#
#     for node in self._walk():
#         try:
#             node.evaluate()
#         except NotImplementedError:
#             pass

_MEASUREMENT_UNITS = {
    'p': 1.0e-12,
    'n': 1.0e-9,
    'u': 1.0e-6,
    'm': 1.0e-3,
    'k': 1.0e+3,
    'K': 1.0e+3,
    'M': 1.0e+6,
    'Meg': 1.0e+6,
    'Mega': 1.0e+6,
    'G': 1.0e+9,
    'Gig': 1.0e+9,
    'Giga': 1.0e+9
}
_MEASUREMENT_UNITS_FLATTEN = '|'.join(sorted(_MEASUREMENT_UNITS, reverse=True))

_OPERATOR_MAPPING: dict[ast.BinOp, BinaryOperator] = {ast.Add: OpAdd, ast.Mult: OpMul}


def _normalize(src):
    p_space = r'\s+'
    p_number = r'(?<![a-zA-Z_])([+-]?(\d*\.\d+|\d+\.?\d*)([eE][+-]\d+)?)' \
               rf'({_MEASUREMENT_UNITS_FLATTEN})?'

    src = re.sub(
        p_space,
        ' ',
        src
    )
    src = re.sub(
        p_number,
        lambda m: str(float(m[1]) * _MEASUREMENT_UNITS.get(m[4], 1)),
        src
    )

    return src


def parse(src):
    src = _normalize(src)
    root = ast.parse(src).body[0]

    def rec(item):
        if isinstance(item, ast.Expr):
            return rec(item.value)
        elif isinstance(item, ast.BinOp):
            a, op, b = item.left, item.op, item.right
            a, b = rec(a), rec(b)
            for k, v in _OPERATOR_MAPPING.items():
                if isinstance(op, k):
                    return v(a, b)
            assert False, (item, vars(item))
        elif isinstance(item, ast.Constant):
            return Constant(item.value)
        elif isinstance(item, ast.Call):
            args = tuple(rec(arg) for arg in item.args)
            if len(args) == 1:
                if item.func.id in 'VvIi':
                    probe_type = dict(v=VoltageProbe, i=CurrentProbe).get(item.func.id.lower())
                    return probe_type(args[0].as_name())
            return Function(name=item.func.id, args=args)
        elif isinstance(item, ast.Assign):
            name, val = item.targets[0].id, item.value
            val = rec(val)
            return NamedValue(name, val)
        elif isinstance(item, ast.UnaryOp):
            assert isinstance(item.op, ast.USub), item.op
            return OpUSub(rec(item.operand))
        elif isinstance(item, ast.Name):
            return Variable(item.id)
        else:
            assert False, (item, vars(item))

    return rec(root)
