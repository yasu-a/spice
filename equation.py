import operator
from abc import ABC
from dataclasses import dataclass
from typing import TYPE_CHECKING

import expression as ex


@dataclass(frozen=True)
class NameGettable:
    @classmethod
    def _name_source(cls) -> str:
        raise NotImplementedError()

    def _order_sources(self) -> tuple:
        return getattr(self, self._name_source()),

    def __lt__(self, other):
        if not isinstance(other, type(self)):
            return NotImplemented
        for this_src, other_src \
                in zip(self._order_sources(), other._order_sources()):
            if this_src < other_src:
                return True
        return False

    @property
    def name(self):
        raise NotImplementedError()

    def __repr__(self):
        return f'{type(self).__name__}({self._name_source()}={self.name!r})'


@dataclass(frozen=True)
class Variable(NameGettable, ABC):
    @classmethod
    def _suffix(cls):
        raise NotImplementedError()

    @property
    def var_name(self):
        return f'_{self._suffix()}_{self.name.lower()}'

    def to_expr(self):
        return ex.Variable(name=self.var_name)

    def term(self, k=None):
        if k is None:
            k = ex.POS_ONE
        return LinearTerm(k=k, element=self)


@dataclass(frozen=True)
class ConstVariable(Variable):
    @classmethod
    def _name_source(cls) -> str:
        raise ValueError('constant variable has no name source')

    @property
    def name(self):
        raise ValueError('constant variable has no name')

    @property
    def var_name(self):
        return f'cst.'

    @classmethod
    def _suffix(cls):
        raise ValueError('constant variable has no suffix')

    def to_expr(self):
        return ex.POS_ONE

    def __repr__(self):
        return f'cst.'


VAR_CONST = ConstVariable()


class LinearTerm:
    def __init__(self, k: ex.ExprNode, element: Variable):
        self.__k = k
        self.__element = element

    @classmethod
    def const(cls, k: ex.ExprNode):
        return cls(k=k, element=VAR_CONST)

    @property
    def k(self):
        return self.__k

    @property
    def element(self):
        return self.__element

    def __neg__(self):
        return LinearTerm(
            k=-self.k,
            element=self.element
        )

    def __mul__(self, other):
        if isinstance(other, float):
            other = ex.Constant(other)
        if not isinstance(other, ex.ExprNode):
            return NotImplemented
        return LinearTerm(
            k=ex.OpMul(other, self.k).simplify(),
            element=self.element
        )

    def __repr__(self):
        k = self.k.simplify().evaluate_if_possible()
        if k == 1:
            k = ''
        if isinstance(k, float):
            k = f'{k:.6f}'
        return f'{k!s:>9s} {self.element.var_name!s:>7s}'

    def is_const(self):
        return self.element == VAR_CONST


class LinearTerms:
    @classmethod
    def _coerce_to_list_of_terms(cls, obj) -> list[LinearTerm]:
        if obj == 0:
            return []

        try:
            it = iter(obj)
        except TypeError:
            if isinstance(obj, LinearTerms):
                obj = list(obj.__terms)
            elif isinstance(obj, Variable):
                obj = [obj.term()]
            elif isinstance(obj, ex.ExprNode):
                obj = [LinearTerm.const(obj)]
            elif isinstance(obj, LinearTerm):
                obj = [obj]
            else:
                raise TypeError(obj)
        else:
            obj = list(it)

        if isinstance(obj, list):
            for elm in obj:
                if not isinstance(elm, LinearTerm):
                    raise TypeError(obj)
        else:
            raise TypeError(obj)

        return obj

    def __init__(self, terms):
        self.__terms: list[LinearTerm] = self._coerce_to_list_of_terms(terms)

    @property
    def single(self):
        return len(self.__terms) == 1

    @property
    def first(self):
        return self.__terms[0]

    def __neg__(self):
        return LinearTerms(map(operator.neg, self.__terms))

    def __add__(self, other):
        other = LinearTerms(other)
        return LinearTerms(self.__terms + other.__terms)

    @classmethod
    def sum(cls, terms):
        return LinearTerms([
            term
            for item in terms
            for term in cls._coerce_to_list_of_terms(item)
        ])

    def __sub__(self, other):
        other = LinearTerms(other)
        return LinearTerms(self.__terms + (-other).__terms)

    def __mul__(self, other):
        return LinearTerms(term * other for term in self.__terms)

    def __repr__(self):
        if not self.__terms:
            return '0'
        return ' + '.join(map(str, self.__terms))

    def __lshift__(self, other: 'LinearEquationSet'):
        if isinstance(other, list):
            for item in other:
                if not isinstance(item, LinearEquation):
                    return NotImplemented
        else:
            return NotImplemented

        src_eqs, dst_terms = other, self

        for src_eq in src_eqs:
            if len(src_eq.left.__terms) != 1:
                raise ValueError(other)

        var_to_formula = src_eqs.var_to_formula()
        result = []
        for dst_term in dst_terms.__terms:
            var_assignment: LinearTerms = var_to_formula.get(dst_term.element)
            if var_assignment:
                new_terms = var_assignment * dst_term.k
            else:
                new_terms = LinearTerms(dst_term)
            result.append(new_terms)
        return LinearTerms.sum(result)

    def split_vars_and_const(self):
        var_side = []
        const_side = []
        for term in self.__terms:
            if term.is_const():
                const_side.append(term)
            else:
                var_side.append(term)
        return LinearTerms(var_side), LinearTerms(const_side)


@dataclass()
class LinearEquation:
    left: LinearTerms
    right: LinearTerms

    def __repr__(self):
        return f'{self.left} = {self.right}'

    def split_vars_and_const(self) -> 'LinearEquation':
        left_vars, left_consts = self.left.split_vars_and_const()
        right_vars, right_consts = self.right.split_vars_and_const()
        return LinearEquation.from_left_and_right(
            left=left_vars - right_vars,
            right=-left_consts + right_consts
        )

    def var_to_formula(self) -> tuple[Variable, LinearTerms]:
        if not self.left.single:
            raise ValueError('left hand formula has multiple terms', self)

        left_term, right_formula = self.left.first, self.right
        left_k, left_var = left_term.k, left_term.element
        right_formula = right_formula * ex.OpInvert(left_k)
        return left_var, right_formula

    def __neg__(self):
        return LinearEquation(
            left=-self.left,
            right=-self.right
        )

    def __add__(self, other):
        if not isinstance(other, LinearEquation):
            return NotImplemented
        return LinearEquation(
            left=self.left + other.left,
            right=self.right + other.right
        )

    def __sub__(self, other):
        if not isinstance(other, LinearEquation):
            return NotImplemented
        return LinearEquation(
            left=self.left - other.left,
            right=self.right - other.right
        )

    @classmethod
    def from_left_and_right(cls, left, right):
        return LinearEquation(
            left=LinearTerms(left),
            right=LinearTerms(right)
        )

    @classmethod
    def from_left(cls, left):
        return LinearEquation(
            left=LinearTerms(left),
            right=LinearTerms(0)
        )

    def __ilshift__(self, other):
        self.right = self.right << other
        self.left = self.left << other
        return self


class LinearEquationSet(list[LinearEquation]):
    def var_to_formula(self) -> dict[Variable, LinearTerms]:
        return dict(map(LinearEquation.var_to_formula, self))

    def split_vars_and_const(self):
        for i, item in enumerate(self):
            self[i] = item.split_vars_and_const()

    def check_type(self):
        for item in self:
            if not isinstance(item, LinearEquation):
                return False
        return True

    def __ilshift__(self, other: 'LinearEquationSet'):
        item: LinearEquation
        for item in self:
            item <<= other
        return self
