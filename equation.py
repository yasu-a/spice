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

    def to_expr(self):
        return ex.Variable(name=f'_{self._suffix()}_{self.name.lower()}')

    def term(self, k=None):
        if k is None:
            k = ex.POS_ONE
        return LinearTerm(k=k, element=self)


class LinearTerm:
    def __init__(self, k: ex.ExprNode, element: Variable):
        self.__k = k
        self.__element = element

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
        var_name = self.element.to_expr().name
        k = self.k.simplify().evaluate_if_possible()
        if k == 1:
            k = ''
        if isinstance(k, float):
            k = f'{k:.6f}'
        return f'{k!s:>9s} {var_name:>7s}'


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


@dataclass()
class LinearEquation:
    left: LinearTerms
    right: LinearTerms

    def __repr__(self):
        return f'{self.left} = {self.right}'

    def to_equation(self) -> 'LinearEquation':
        return self

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
