from dataclasses import dataclass
from frozendict import frozendict
import re
from typing import NamedTuple, Callable
from enum import Enum

import expression
from comins import ComponentInstance
from model import ComponentModel

from node import Node


class CurrentFlow(Enum):
    OUT = -1
    IN = +1


@dataclass(frozen=True)
class ComponentClassBase:
    pass


@dataclass(frozen=True)
class ComponentClass(ComponentClassBase):
    name: str
    prefix: str
    port_high: str
    port_low: str
    current_flow: tuple[CurrentFlow, ...]
    g_proc: Callable[[ComponentInstance], float] | float = None
    e_proc: Callable[[ComponentInstance], float] = None
    j_proc: Callable[[ComponentInstance], float] = None

    def __repr__(self):
        return f'ComponentClass(name={self.name!r})'

    def __lt__(self, other):
        if not isinstance(other, ComponentClass):
            return NotImplemented
        return self.name < other.name

    @property
    def ports(self) -> tuple[str, str]:
        return self.port_high, self.port_low

    def calculate_conductance(self, ins: ComponentInstance):
        if self.g_proc is None:
            return float('nan')
        elif isinstance(self.g_proc, float):
            return self.g_proc
        elif callable(self.g_proc):
            return self.g_proc(ins)
        else:
            assert False, self.g_proc

    def calculate_constant_voltage(self, ins: ComponentInstance):
        if self.e_proc is None:
            return float('nan')
        elif callable(self.e_proc):
            return self.e_proc(ins)
        else:
            assert False, self.e_proc

    def calculate_constant_current(self, ins: ComponentInstance):
        if self.j_proc is None:
            return float('nan')
        elif callable(self.j_proc):
            return self.j_proc(ins)
        else:
            assert False, self.j_proc


class ComponentClassSet:
    def __init__(self, classes: tuple[ComponentClass, ...]):
        self.__classes = classes

    def _find_by_prefix(self, name, force_prefix=None):
        if force_prefix:
            name = force_prefix
        for clazz in self.__classes:
            if name.lower().startswith(clazz.prefix.lower()):
                return clazz
        return None

    @classmethod
    def _parse_model(cls, model_str):
        node = expression.parse(model_str)
        try:
            node = node.evaluate()
        except NotImplementedError:
            pass
        return node

    def parse_netlist_line(
            self, line,
            force_prefix=None,
            force_model=None
    ) -> 'ComponentInstance | None':
        name, *ports, model_str = re.split(r'\s+', line)
        clazz = self._find_by_prefix(name, force_prefix=force_prefix)
        assert clazz is None or len(ports) == len(clazz.ports)
        ports = [Node(node_name) for node_name in ports]
        model = force_model or ComponentModel(
            name='const',
            params=frozendict(value=self._parse_model(model_str))
        )
        return ComponentInstance(
            source_line=line,
            clazz=clazz,
            name=name,
            port_mapping=tuple(ports),
            model=model
        )
