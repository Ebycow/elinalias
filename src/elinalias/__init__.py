"""elinalias — Elin の異名(エイリアス)生成を Python で再現するライブラリ。"""

from .data import AliasData, Mix, extract
from .generator import AliasGenerator, random_alias, title_case
from .netrandom import NetRandom

__all__ = [
    "AliasData",
    "AliasGenerator",
    "Mix",
    "NetRandom",
    "extract",
    "random_alias",
    "title_case",
]
__version__ = "0.1.0"
