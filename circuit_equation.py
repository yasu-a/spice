from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from node import Node
    from edge import Edge

from equation import *


@dataclass(frozen=True)
class CircuitVariable(Variable, ABC):
    @classmethod
    def _suffix(cls):
        raise NotImplementedError()

    def to_expr(self):
        return ex.Variable(name=f'_{self._suffix()}_{self.name.lower()}')

    def term(self, k=None):
        if k is None:
            k = ex.POS_ONE
        return LinearTerm(k=k, element=self)


@dataclass(frozen=True)
class EdgeVariable(Variable, ABC):
    edge: 'Edge'

    @property
    def name(self):
        return self.edge.component.name

    @classmethod
    def _name_source(cls) -> str:
        return 'edge'


@dataclass(frozen=True)
class EdgeCurrent(EdgeVariable):
    if TYPE_CHECKING:
        def __init__(self, edge: Edge):
            ...

    @classmethod
    def _suffix(cls):
        return 'i'


@dataclass(frozen=True)
class EdgeVoltage(EdgeVariable):
    if TYPE_CHECKING:
        def __init__(self, edge: Edge):
            ...

    @classmethod
    def _suffix(cls):
        return 'v'


@dataclass(frozen=True)
class NodeVariable(Variable, ABC):
    node: 'Node'

    @property
    def name(self):
        return self.node.name

    @classmethod
    def _name_source(cls) -> str:
        return 'node'


@dataclass(frozen=True)
class NodePotential(NodeVariable):
    if TYPE_CHECKING:
        def __init__(self, node: Node):
            ...

    @classmethod
    def _suffix(cls):
        return 'e'
