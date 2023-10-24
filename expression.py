from frozendict import frozendict
import ast
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ExprNode:
    def evaluate(self):
        raise NotImplementedError()

    def children(self):
        raise NotImplementedError()


@dataclass(frozen=True)
class Constant(ExprNode):
    value: float

    def evaluate(self):
        return self.value

    def children(self):
        yield from []

    def as_name(self):
        return str(int(self.value))


@dataclass(frozen=True)
class BinaryOperator(ExprNode):
    a: ExprNode
    b: ExprNode

    @classmethod
    def _calc_impl(cls, a, b):
        raise NotImplementedError()

    def evaluate(self):
        return self._calc_impl(self.a, self.b)

    def children(self):
        yield self.b
        yield self.a


@dataclass(frozen=True)
class OpAdd(BinaryOperator):
    @classmethod
    def _calc_impl(cls, a, b):
        raise a.evaluate() + b.evaluate()


@dataclass(frozen=True)
class OpMul(BinaryOperator):
    @classmethod
    def _calc_impl(cls, a, b):
        raise a.evaluate() * b.evaluate()


@dataclass(frozen=True)
class UnaryOperator(ExprNode):
    a: ExprNode

    @classmethod
    def _calc_impl(cls, a):
        raise NotImplementedError()

    def evaluate(self):
        return self._calc_impl(self.a)

    def children(self):
        yield self.a


@dataclass(frozen=True)
class OpUSub(UnaryOperator):
    @classmethod
    def _calc_impl(cls, a):
        return -a.evaluate()


@dataclass(frozen=True)
class Function(ExprNode):
    name: str
    args: tuple[ExprNode]

    def evaluate(self):
        raise NotImplementedError()

    def children(self):
        yield from self.args


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
    p_number = r'([+-]?(\d*\.\d+|\d+\.?\d*)([eE][+-]\d+)?)' \
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
            return Function(name=item.func.id, args=args)
        elif isinstance(item, ast.Assign):
            name, val = item.targets[0].id, item.value
            val = rec(val)
            return NamedValue(name, val)
        elif isinstance(item, ast.UnaryOp):
            assert isinstance(item.op, ast.USub), item.op
            return OpUSub(rec(item.operand))
        else:
            assert False, (item, vars(item))

    return rec(root)
