from enum import StrEnum
from functools import cached_property

from common.paradox_lib import GameConcept, NameableEntity, AdvancedEntity, PdxColor


class Eu5GameConcept(GameConcept):
    family: str = ''
    alias: list['Eu5GameConcept']
    is_alias: bool = False

    def __init__(self, name: str, display_name: str, **kwargs):
        self.alias = []
        super().__init__(name, display_name, **kwargs)

class GoodCategory(StrEnum):
    raw_material = 'raw_material'
    produced = 'produced'

    @cached_property
    def display_name(self) -> str:
        from eu5.game import eu5game
        return eu5game.parser.localize(self)

class Good(AdvancedEntity):
    ai_rgo_size_importance: float = None
    base_production: float = 0
    category: GoodCategory
    color: PdxColor
    default_market_price: float = 1
    food: float = 0
    inflation: bool = False
    is_slaves: bool = False
    method: str = ''
    transport_cost: float = 1
