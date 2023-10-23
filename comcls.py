from frozendict import frozendict
import re
from typing import NamedTuple, Callable
from enum import Enum

from comins import ComponentInstance
from model import ComponentModel


class CurrentFlow(Enum):
    OUT = -1
    IN = +1


class ComponentClass(NamedTuple):
    name: str
    prefix: str
    ports: tuple[str, ...]
    current_flow: tuple[CurrentFlow, ...]
    g_proc: Callable[[ComponentInstance], float] | float = None

    def calculate_conductance(self, ins: ComponentInstance):
        if self.g_proc is None:
            return float('nan')
        elif isinstance(self.g_proc, float):
            return self.g_proc
        elif callable(self.g_proc):
            return self.g_proc(ins)
        else:
            assert False, self.g_proc


class ComponentClassSet:
    def __init__(self, classes: tuple[ComponentClass, ...]):
        self.__classes = classes

    def _find_by_prefix(self, name):
        for clazz in self.__classes:
            if name.lower().startswith(clazz.prefix.lower()):
                return clazz
        return None

    def parse_netlist_line(self, line) -> 'ComponentInstance | None':
        name, *ports, model_str = re.split(r'\s+', line)
        clazz = self._find_by_prefix(name)
        if clazz is None:
            return None
        assert len(ports) == len(clazz.ports)
        return ComponentInstance(
            clazz=clazz,
            name=name,
            port_mapping=tuple(ports),
            model=ComponentModel(
                name='const',
                params=frozendict(value=float(model_str))
            )
        )
