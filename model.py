import numpy as np
from typing import NamedTuple
import re
from ntpprint import pprint, nt_asdict
from frozendict import frozendict


class ComponentModel(NamedTuple):
    name: str
    params: frozendict[str, float]
