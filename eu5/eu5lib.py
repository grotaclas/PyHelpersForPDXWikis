from enum import StrEnum
from functools import cached_property

from common.paradox_lib import GameConcept, NameableEntity, AdvancedEntity, PdxColor, ModifierType, Modifier
from common.paradox_parser import Tree


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
    is_bool: bool = False
    is_good: str = 'good'
    is_percent: bool = False

    def __init__(self, name: str, display_name: str, **kwargs):
        super().__init__(name, display_name, **kwargs)
        if self.is_percent:
            self.percent = self.is_percent
        if self.is_bool:
            self.boolean = self.is_bool
        if self.is_good == 'good':
            self.good = True
        elif self.is_good == 'bad':
            self.good = False
        elif self.is_good == 'neutral':
            self.neutral = True

    def _get_fully_localized_display_name_and_desc(self) -> (str, str):
        display_name = self.parser.localize('MODIFIER_TYPE_NAME_' + self.name)
        display_name = self.parser.formatter.format_localization_text(display_name, [])
        description = self.parser.localize('MODIFIER_TYPE_DESC_' + self.name)
        description = self.parser.formatter.format_localization_text(description, [])
        return display_name, description

class Eu5Modifier(Modifier):
    modifier_type: Eu5ModifierType

class Building(AdvancedEntity):
    AI_ignore_available_worker_flag: bool
    AI_optimization_flag_coastal: bool
    allow: Tree
    allow_wrong_startup: bool
    always_add_demands: bool
    build_time: int = 0 # scripted value
    can_close: bool
    can_destroy: Tree
    capital_country_modifier: list[Eu5Modifier]
    capital_modifier: list[Eu5Modifier]
    category: str
    city: bool = False
    construction_demand: str
    conversion_religion: str
    country_potential: Tree
    destroy_price: str
    employment_size: float # scripted value
    estate: str
    forbidden_for_estates: bool
    foreign_country_modifier: Tree
    graphical_tags: list
    in_empty: str
    increase_per_level_cost: float
    is_foreign: bool = False
    lifts_fog_of_war: bool
    location_potential: Tree
    market_center_modifier: list[Eu5Modifier]
    max_levels: int|str  # TODO: scripted integer
    modifier: list[Eu5Modifier]  # possible types: {<class 'list'>, <class 'common.paradox_parser.Tree'>}
    need_good_relation: bool
    obsolete: 'Building'
    on_built: Tree
    on_destroyed: Tree
    pop_size_created: str
    pop_type: str
    possible_production_methods: list
    price: str
    raw_modifier: list[Eu5Modifier]
    remove_if: Tree
    rural_settlement: bool
    stronger_power_projection: bool
    town: bool = False
    unique_production_methods: Tree  # possible types: {<class 'list'>, <class 'common.paradox_parser.Tree'>}


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
