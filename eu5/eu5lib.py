from enum import StrEnum
from functools import cached_property

from common.paradox_lib import GameConcept, NameableEntity, AdvancedEntity, PdxColor, ModifierType


class Eu5ModifierType(ModifierType):
    # unique to eu5:
    ai: bool = False
    bias_type: list[str]|str
    category: str = 'all'
    format: str = ''
    min: int
    scale_with_pop: bool
    should_show_in_modifiers_tab: bool

    # shared attributes with different defaults
    num_decimals: int = 2  # vic3 has a default of 0

    # the following are named differently in the parent class and are handled in the constructor
    # is_bool: bool
    # is_good: str
    # is_percent: bool

    def __init__(self, name: str, display_name: str, **kwargs):
        super().__init__(name, display_name, **kwargs)
        if 'is_percent' in kwargs:
            self.percent = kwargs['is_percent']
        if 'is_bool' in kwargs:
            self.boolean = kwargs['is_bool']
        if 'is_good' in kwargs:
            if kwargs['is_good'] == 'good':
                self.good = True
            elif kwargs['is_good'] == 'bad':
                self.good = False
            elif kwargs['is_good'] == 'neutral':
                self.neutral = True
        if 'is_percent' in kwargs:
            self.percent = kwargs['is_percent']

    def _get_fully_localized_display_name_and_desc(self) -> (str, str):
        display_name = self.parser.localize('MODIFIER_TYPE_NAME_' + self.name)
        display_name = self.parser.formatter.format_localization_text(display_name, [])
        description = self.parser.localize('MODIFIER_TYPE_DESC_' + self.name)
        description = self.parser.formatter.format_localization_text(description, [])
        return display_name, description

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
