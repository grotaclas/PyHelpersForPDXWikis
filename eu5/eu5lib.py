import copy
import numbers
import re
from enum import StrEnum
from functools import cached_property
from pathlib import Path
from typing import Any

from common.paradox_lib import GameConcept, NameableEntity, AdvancedEntity, PdxColor, ModifierType, Modifier, IconMixin
from common.paradox_parser import Tree
from eu5.event_target import EventTarget
from eu5.game import eu5game
from eu5.trigger import Trigger
from eu5.effect import Effect

class Eu5ModifierType(ModifierType):
    # unique to eu5(stored in the game_data and handled by the constructor):
    ai: bool = False
    bias_type: list[str]|str
    category: str = 'all'
    format: str = ''
    is_societal_value_change: bool = False
    min: int = None
    max: int = None
    scale_with_pop: bool = False
    should_show_in_modifiers_tab: bool = True

    # stores the data which is unique to eu5
    game_data: Tree

    # shared attributes with different defaults
    num_decimals: int = 2  # vic3 has a default of 0

    icon_file: str = None
    "relative path to the icon file"
    negative_icon_file: str = None
    "relative path to the file for the negative icon(if any)"

    def __init__(self, name: str, display_name: str, **kwargs):
        if 'color' not in kwargs:
            kwargs['color'] = 'good'
        super().__init__(name, display_name, **kwargs)
        for k, v in self.game_data:
            setattr(self, k, v)

    def _get_fully_localized_display_name_and_desc(self) -> (str, str):
        display_name = self.parser.localize('MODIFIER_TYPE_NAME_' + self.name)
        if display_name != '(unused)':
            display_name = self.parser.formatter.strip_formatting(display_name, strip_newlines=True)
        description = self.parser.localize('MODIFIER_TYPE_DESC_' + self.name)
        description = self.parser.formatter.format_localization_text(description, [])
        return display_name, description

    def format_value(self, value):
        if isinstance(value, ScriptValue) and value.direct_value:
            value = value.direct_value
        return super().format_value(value)

    def format_value_without_color(self, value):
        if isinstance(value, ScriptValue) and value.direct_value:
            value = value.direct_value
        return super().format_value_without_color(value)

    def get_icon_path(self) -> Path|None:
        base_icon_folder = eu5game.game_path / 'game/main_menu'
        if self.icon_file:
            return base_icon_folder / self.icon_file
        else:
            return None

    def get_wiki_filename(self) -> str:
        if not self.icon_file:
            return ''
        filename = self.get_icon_path().stem + '.png'
        filename = filename.replace(':', '')
        filename = filename.replace('_', ' ')
        return filename.strip().capitalize()

class Eu5Modifier(Modifier):
    modifier_type: Eu5ModifierType

    def format_for_wiki(self):
        if self.name == 'potential_trigger':
            return 'generating of triggers not supported yet'  # @TODO
        elif self.name == 'scale':
            return 'generating of triggers not supported yet'  # @TODO
        value_and_name = super().format_for_wiki()
        return f'[[File:{self.modifier_type.get_wiki_filename()}|32px]] {value_and_name}'


class Eu5NamedModifier(NameableEntity):
    """Modifier describes several related concepts.
    This class is for entities from the common/modifiers folder which groups together multiple modifiers and
    gives them a name, category and description
    For the individual modifiers see the class Eu5Modifier
    For the possible types of these modifiers see Eu5ModifierType"""

    category: str
    description: str = ''
    decaying: bool = False
    modifier: list[Eu5Modifier]

    def format_for_wiki(self, time_limit_weeks: int = None) -> str:
        """@TODO: use wiki template"""
        return "Modifier ''“{}”''{} giving:\n* {}".format(
                                                       self.display_name,
                                                       ' for {} weeks'.format(time_limit_weeks) if time_limit_weeks is not None else '',
                                                       '\n* '.join([modifier.format_for_wiki() for modifier in self.modifier]))


class Eu5AdvancedEntity(AdvancedEntity):

    icon_folder: str = None
    "either the name of the define in NGameIcons or the folder name relative to game/main_menu/gfx/interface/icons"

    base_icon_folder = eu5game.game_path / 'game/main_menu/gfx/interface/icons'

    def get_icon_filename(self) -> str:
        if self.icon:
            name = self.icon
        else:
            name = self.name
        return f'{name}.dds'

    @classmethod
    def get_icon_folder(cls):
        if cls.icon_folder is None:
            icon_folder = re.sub(r'(?<!^)(?=[A-Z])', '_', cls.__name__).lower()
            path = cls.base_icon_folder / icon_folder
            if not path.exists():
                # try plural
                icon_folder += 's'
                path = cls.base_icon_folder / icon_folder
                if not path.exists():
                    raise Exception(f'No icon folder for class "{cls.__name__}"')
        else:
            if cls.icon_folder in eu5game.parser.defines['NGameIcons']:
                cls.base_icon_folder = eu5game.game_path / 'game/main_menu'
                icon_folder = eu5game.parser.defines['NGameIcons'][cls.icon_folder]
            elif cls.icon_folder in eu5game.parser.defines['NGameIllustrations']:
                cls.base_icon_folder = eu5game.game_path / 'game/main_menu'
                icon_folder = eu5game.parser.defines['NGameIllustrations'][cls.icon_folder]
            else:
                icon_folder = cls.icon_folder

        return cls.base_icon_folder / icon_folder

    def get_icon_path(self) -> Path:
        return self.get_icon_folder() / self.get_icon_filename()

    def get_wiki_filename(self) -> str:
        filename = self.get_icon_filename().replace('.dds', '.png')
        prefix = self.get_wiki_filename_prefix()
        filename = filename.removeprefix('icon_')
        if not filename.lower().startswith(prefix.lower()):
            filename = f'{prefix} {filename}'
        filename = filename.replace(':', '')
        filename = filename.replace('_', ' ')
        return filename.capitalize()

    def get_wiki_icon(self, size: str = '32px') -> str:
        return self.get_wiki_file_tag(size, link='self')


class ScriptValue(NameableEntity):  # can't have a name, but we want to use logic of the parent class
    direct_value: float|str = None  # if it is defined as name_of_scripted_value = value
    desc: str = ''
    value: float|str = None
    calculations:Tree = None  # everything else has to be processed in order

    def format(self):
        if self.direct_value:
            return self.direct_value
        else:
            if self.desc:
                tooltip_text = self.desc
            elif self.value:
                tooltip_text = self.value
            else:
                tooltip_text = self.name
            # @TODO: implement showing calculations or some kind of tenmplate with a better explanation
            return f'{{{{Tooltip|{tooltip_text}|Showing the full calculation is not implemented yet}}}}'

    def __mul__(self, other):
        if isinstance(other, numbers.Number):
            other_number = other
        elif isinstance(other, ScriptValue):
            if other.direct_value:
                other_number = other.direct_value
            elif self.direct_value:
                return other.__mul__(self)
            else:
                return NotImplemented
        else:
            return NotImplemented

        if self.direct_value:
            return self.direct_value * other_number
        else:
            result_name = f'{self.name}*{other_number}'
            result = ScriptValue(result_name, result_name)
            if self.desc:
                result.desc = f'{self.desc} * {other_number}'
            result_calculations = copy.deepcopy(self.calculations)
            result_calculations['multiply'] = other_number
            result.calculations = result_calculations
            return result
    def __str__(self):
        return str(self.format())

    @classmethod
    def could_be_script_value(cls, script: Tree):
        for key, value in script:
            if key in ['save_temporary_scope_as', 'save_temporary_value_as', 'limit', 'desc', ]:
                # ignored
                continue
            elif key in ['add', 'divide', 'max', 'min', 'multiply', 'subtract', 'value', ]:
                # actual script value calculations
                continue
            elif  EventTarget.could_be_event_target(key) or key in ['if', 'else_if', 'else'] or Effect.is_iterator(key):
                if isinstance(value, Tree):
                    if not cls.could_be_script_value(value):
                        return False
                elif isinstance(value, list):
                    for v2 in value:
                        if isinstance(v2, Tree):
                            if not cls.could_be_script_value(v2):
                                return False
                        else:
                            # print(f'Error: unknown sub-value type "{type(value)}" in list in {key}-block in script value')
                            return False
                else:
                    # print(f'Error: unknown value type "{type(value)}" in {key}-block in script value')
                    return False

            else:
                return False

        return True

# Map classes
class Location(Eu5AdvancedEntity):
    climate: 'Climate'
    culture: 'Culture' = None
    modifier: Eu5NamedModifier = None
    movement_assistance: list[float] = []
    natural_harbor_suitability: float = None
    raw_material: 'Good' = None
    religion: 'Religion' = None
    topography: 'Topography'
    vegetation: 'Vegetation' = None

    @cached_property
    def province(self):
        # lazy loading to avoid infinite recursions, because province parsing requires locations
        return eu5game.parser.get_province(self)

    @cached_property
    def area(self):
        return self.province.area

    @cached_property
    def region(self):
        return self.area.region

    @cached_property
    def sub_continent(self):
        return self.region.sub_continent

    @cached_property
    def continent(self):
        return self.sub_continent.continent

    def get_position_description(self):
        return f'{self.province}(`{self.province.name}`), {self.area}(`{self.area.name}`), {self.region}(`{self.region.name}`), {self.sub_continent}(`{self.sub_continent.name}`), {self.continent}(`{self.continent.name}`)'


class Province(NameableEntity):
    locations: dict[str, Location]
    _area: str

    @cached_property
    def area(self) -> 'Area':
        return eu5game.parser.areas[self._area]

class Area(NameableEntity):
    provinces: dict[str, Province]
    _region: str

    @cached_property
    def region(self) -> 'Region':
        return eu5game.parser.regions[self._region]

class Region(NameableEntity):
    areas: dict[str, Area]
    _sub_continent: str

    @cached_property
    def sub_continent(self) -> 'SubContinent':
        return eu5game.parser.sub_continents[self._sub_continent]

class SubContinent(NameableEntity):
    regions: dict[str, Region]
    _continent: str

    @cached_property
    def continent(self) -> 'Continent':
        return eu5game.parser.continents[self._continent]


class Continent(NameableEntity):
    sub_continents: dict[str, SubContinent]


class Advance(Eu5AdvancedEntity):
    age: str
    ai_preference_tags: list = []
    ai_weight: Tree = None
    allow: Trigger = None
    allow_children: bool = True
    country_type: str = None
    depth: int = None
    age_specialization: str = None  # called "for" in the files, but that's a reserved word in python
    government: str = None
    in_tree_of: Any = None # possible types: {<class 'list'>, <class 'str'>}
    modifier_while_progressing: Tree
    potential: Trigger = None
    requires: list['Advance'] = []
    research_cost: float = None # percentage?
    starting_technology_level: int = 0
    unlock_ability: list[str] = []
    unlock_building: list[str] = []
    unlock_cabinet_action: list[str] = []
    unlock_casus_belli: list[str] = []
    unlock_country_interaction: list[str] = []
    unlock_diplomacy: list[str] = []
    unlock_estate_privilege: list[str] = []
    unlock_government_reform: list[str] = []
    unlock_heir_selection: list[str] = []
    unlock_law: list[str] = []
    unlock_levy: list[str] = []
    unlock_policy: list[str] = []
    unlock_production_method: list[str] = []
    unlock_road_type: list[str] = []
    unlock_subject_type: list[str] = []
    unlock_unit: list[str] = []

    icon_folder = 'ADVANCE_ICON_PATH'

    def get_wiki_icon(self, size: str = '32px') -> str:
        if self.get_wiki_filename().removesuffix(".png") == self.display_name:
            localized_name_param = ''
        else:
            localized_name_param = f'|{self.display_name}'

        return f'{{{{Advance|{self.get_wiki_filename().removesuffix(".png")}{localized_name_param}|w={size}}}}}'


class Resource(IconMixin):
    pass


class HardcodedResource(Resource, StrEnum):
    army_tradition = 'army_tradition'
    doom = 'doom'
    favors = 'favors'
    gold = 'gold'
    gold_per_pop = 'gold_per_pop'
    government_power = 'government_power'
    harmony = 'harmony'
    honor = 'honor'
    inflation = 'inflation'
    karma = 'karma'
    manpower = 'manpower'
    navy_tradition = 'navy_tradition'
    piety = 'piety'
    prestige = 'prestige'
    purity = 'purity'
    religious_influence = 'religious_influence'
    righteousness = 'righteousness'
    rite_power = 'rite_power'
    sailors = 'sailors'
    self_control = 'self_control'
    scaled_gold = 'scaled_gold'
    scaled_manpower = 'scaled_manpower'
    scaled_recipient_gold = 'scaled_recipient_gold'
    scaled_sailors = 'scaled_sailors'
    spy_network = 'spy_network'
    stability = 'stability'
    trust = 'trust'
    war_exhaustion = 'war_exhaustion'
    yanantin = 'yanantin'

    # specific gov powers
    legitimacy = 'legitimacy'
    republican_tradition = 'republican_tradition'
    devotion = 'devotion'
    horde_unity = 'horde_unity'
    tribal_cohesion = 'tribal_cohesion'

    @cached_property
    def display_name(self) -> str:
        return eu5game.parser.localize(self)

    @cached_property
    def positive_is_good(self):
        change_loc = eu5game.parser.localize(f'FORMAT_CURRENCY_{self.name}_change')
        if '|-=' in change_loc:
            return False
        elif '|+=' in change_loc:
            return True
        # default
        return True

    @cached_property
    def icon(self):
        return self.name.replace('_', ' ')


class GoodCategory(StrEnum):
    raw_material = 'raw_material'
    produced = 'produced'

    @cached_property
    def display_name(self) -> str:
        from eu5.game import eu5game
        return eu5game.parser.localize(self)


class Good(Eu5AdvancedEntity, Resource):
    ai_rgo_size_importance: float = None
    base_production: float = 0
    category: GoodCategory
    color: PdxColor
    custom_tags: list[str] = []
    default_market_price: float = 1
    demand_add: Tree = None
    demand_multiply: Tree = None
    food: float = 0
    inflation: bool = False
    is_slaves: bool = False
    method: str = ''
    transport_cost: float = 1

    icon_folder = 'TRADE_GOODS_ICON_PATH'

    @cached_property
    def positive_is_good(self) -> bool:
        return True

    def get_icon_filename(self) -> str:
        return f'icon_goods_{self.name}.dds'

    def get_wiki_filename_prefix(self) -> str:
        return 'Goods'

    def get_wiki_filename(self) -> str:
        wiki_filename = super().get_wiki_filename()
        if wiki_filename.startswith('Goods goods'):
            return 'Goods ' + wiki_filename.removeprefix('Goods goods ')
        else:
            return wiki_filename

    def get_wiki_page_name(self) -> str:
        return 'Goods'

    @cached_property
    def demands(self) -> dict['PopType', float]:
        demands = {}
        for pop in eu5game.parser.pop_types.values():
            demand = 0
            if self.demand_add:
                if pop.name in self.demand_add:
                    demand += self.demand_add[pop.name]
                if 'all' in self.demand_add:
                    demand += self.demand_add['all']
                if pop.upper and 'upper' in self.demand_add:
                    demand += self.demand_add['upper']
            if self.demand_multiply:
                if pop.name in self.demand_multiply:
                    demand *= self.demand_multiply[pop.name]
                if 'all' in self.demand_multiply:
                    demand *= self.demand_multiply['all']
                if pop.upper and 'upper' in self.demand_multiply:
                    demand *= self.demand_multiply['upper']
            demands[pop] = demand
        return demands


class ResourceValue:
    value: int|float
    resource: Resource

    def __init__(self, resource: Resource | None, value: int | float):
        self.resource = resource
        self.value = value

    @classmethod
    def create_with_hardcoded_resource(cls, resource_name: str, resource_value: int | float) -> 'ResourceValue':
        return cls(HardcodedResource(resource_name), resource_value)

    @classmethod
    def create_with_goods(cls, resource_name: str, resource_value: int | float) -> 'ResourceValue':
        return cls(eu5game.parser.goods[resource_name], resource_value)

    def format(self, icon_only=False):
        if self.resource is None:
            return ''
        return eu5game.parser.formatter.format_resource(self.resource, self.value, icon_only=icon_only)

    def __str__(self):
        return self.format()


class Cost(ResourceValue):
    def format(self, icon_only=False):
        return eu5game.parser.formatter.format_cost(self.resource, self.value, icon_only)


class Price(NameableEntity):
    min: float  # unused
    cap_scale: int # max
    costs: list[Cost]

    def format(self, icon_only=False):
        return eu5game.parser.formatter.create_wiki_list([cost.format(icon_only) for cost in self.costs])


class GoodsDemand(NameableEntity):
    category: str
    hidden: bool
    demands: list[Cost]

    def format(self, icon_only=False):
        return eu5game.parser.formatter.create_wiki_list([cost.format(icon_only) for cost in self.demands])


class NoPrice(Price):

    def __init__(self):
        super().__init__('', '')
        self.costs = []

    def __bool__(self):
        return False

    def format(self, icon_only=False):
        return ''


class ProductionMethod(NameableEntity):
    category: str
    input: list[Cost]
    output: float = 0
    potential: Tree
    produced: Good = None

    def format(self, icon_only=False):
        data = [
            'Input:',
            [cost.format(icon_only) for cost in self.input] if self.input else 'None',
        ]
        if self.output and self.produced:
            data.append('Output:')
            data.append(ResourceValue(self.produced, self.output).format(icon_only))
        # return eu5game.parser.formatter.create_wiki_list(data)
        return [self.display_name, data]

class Age(Eu5AdvancedEntity):
    efficiency: float
    hegemons_allowed: bool = False
    max_price: int
    mercenaries: float = 0
    modifier: list[Eu5Modifier]
    price_stability: float
    year: int

class BuildingCategory(Eu5AdvancedEntity):
    icon_folder = 'building_categories'

class Building(Eu5AdvancedEntity):
    AI_ignore_available_worker_flag: bool = False
    AI_optimization_flag_coastal: bool = False
    allow: Trigger = None
    allow_wrong_startup: bool = False
    always_add_demands: bool = False
    build_time: int = 0 # scripted value
    can_close: bool = True
    can_destroy: Trigger = None
    capital_country_modifier: list[Eu5Modifier]
    capital_modifier: list[Eu5Modifier]
    category: BuildingCategory
    city: bool = False
    construction_demand: GoodsDemand = NoPrice()
    conversion_religion: str = None
    country_potential: Trigger = None
    destroy_price: Price = NoPrice()
    employment_size: float = 0
    estate: str = ''
    forbidden_for_estates: bool = False
    foreign_country_modifier: list[Eu5Modifier]
    graphical_tags: list[str] = []
    in_empty: str = 'owned'
    increase_per_level_cost: float = 0
    is_foreign: bool = False
    lifts_fog_of_war: bool = False
    location_potential: Trigger = None
    market_center_modifier: list[Eu5Modifier]
    max_levels: int|str  # TODO: scripted integer
    modifier: list[Eu5Modifier]  # possible types: {<class 'list'>, <class 'common.paradox_parser.Tree'>}
    need_good_relation: bool = False
    obsolete: list['Building'] = []
    on_built: Effect = None
    on_destroyed: Effect = None
    pop_size_created: int = 0
    pop_type: str
    possible_production_methods: list[ProductionMethod] = []
    price: Price = NoPrice()
    raw_modifier: list[Eu5Modifier]
    remove_if: Trigger = None
    rural_settlement: bool = False
    stronger_power_projection: bool = False
    town: bool = False
    unique_production_methods: list[list[ProductionMethod]] = [] # possible types: {<class 'list'>, <class 'common.paradox_parser.Tree'>}

    icon_folder = 'BUILDINGS_ICON_PATH'


class Climate(Eu5AdvancedEntity):
    audio_tags: Tree
    color: PdxColor
    debug_color: PdxColor
    has_precipitation: bool = True
    location_modifier: list[Eu5Modifier]
    unit_modifier: list[Eu5Modifier] = []
    winter: str

    icon_folder = 'CLIMATE_ICON_PATH'


class CountryDescriptionCategory(NameableEntity):
    pass


class Country(Eu5AdvancedEntity):
    # From in_game/setup/countries
    color: PdxColor
    color2: PdxColor = None
    culture_definition: 'Culture' = None  # only unset for special tags DUMMY, PIR and MER
    description_category: CountryDescriptionCategory = None
    difficulty: int = 2  # If I understand the readme correctly, the default is 2
    female_regnal_names: list[str]
    formable_level: int = 0
    is_historic: bool = False
    male_regnal_names: list[str]
    religion_definition: 'Religion' = None  # only unset for special tags DUMMY, PIR and MER
    unit_color0: PdxColor = None
    unit_color1: PdxColor = None
    unit_color2: PdxColor = None

    # From main_menu/setup/start/10_countries_and_roads.txt
    accepted_cultures: 'Culture' = None
    add_pops_from_locations: list[Location] = None
    ai_advance_preference_tags: Tree = None
    capital: Location = None
    control: list[Location] = []
    country_name: str = ''
    country_rank: str = ''
    court_language: 'Language' = None
    currency_data: Tree = None
    discovered_areas: list[Area] = []
    discovered_provinces: list[Province] = []
    discovered_regions: list[Region] = []
    dynasty: str = ''
    flag: str = None
    government: Tree  # @TODO: government parsing
    include: str = ''
    is_valid_for_release: bool = True
    liturgical_language: 'Language' = None
    our_cores_conquered_by_others: list[Location] = []
    own_conquered: list[Location] = []
    own_control_colony: list[Location] = []
    own_control_conquered: list[Location] = []
    own_control_core: list[Location] = []
    own_control_integrated: list[Location] = []
    own_core: list[Location] = []
    religious_school: 'ReligiousSchool' = None
    revolt: bool = False
    scholars: 'ReligiousSchool' = None
    starting_technology_level: int = None
    timed_modifier: list[Eu5Modifier] = []
    tolerated_cultures: list['Culture'] = []
    type: 'GovernmentType'
    variables: Tree = None

    def __init__(self, name: str, display_name: str, **kwargs):
        if kwargs['setup_data']:
            for k, v in kwargs['setup_data']:
                if k in kwargs:
                    print(f'Error: duplicate key {k} in {name}. Orig_value: "{kwargs[k]}"; setup_value: "{v}"')
                else:
                    kwargs[k] = v

        super().__init__(name, display_name, **kwargs)
        if self.country_name:
            self.display_name = f'{eu5game.parser.localize(self.country_name)}({self.name})'

    def has_flag(self, flag: str):
        if self.variables and 'data' in self.variables:
            for variable in self.variables['data']:
                if (
                        variable['flag'] == flag
                        and variable['data']['type'] == 'boolean'
                        and variable['data']['identity'] == 1
                ):
                    return True
        return False


class CultureGroup(NameableEntity):
    character_modifier: list[Eu5Modifier] = []
    country_modifier: list[Eu5Modifier] = []
    location_modifier: list[Eu5Modifier] = []


class Culture(Eu5AdvancedEntity):
    adjective_keys: list[str] = []
    character_modifier: list[Eu5Modifier] = []
    color: PdxColor
    country_modifier: list[Eu5Modifier] = []
    culture_groups: list[CultureGroup] = []
    dynasty_name_type: str = ''
    language: 'Language'
    location_modifier: list[Eu5Modifier] = []
    noun_keys: list[str] = []
    opinions: Tree = None
    tags: list[str]  # gfx tags
    use_patronym: bool = False


class Estate(Eu5AdvancedEntity):
    alliance:float
    bank: bool = False  #can and will loan money
    can_have_characters: bool = True
    characters_have_dynasty: str
    color: str  # @TODO named color
    high_power: list[Eu5Modifier]
    low_power: list[Eu5Modifier]
    opinion: Tree # scripted value
    power: list[Eu5Modifier] = []
    power_per_pop: float
    priority_for_dynasty_head: bool = False
    revolt_court_language: str
    rival: float
    ruler: bool = False
    satisfaction: list[Eu5Modifier] = []
    tax_per_pop: float
    use_diminutive: bool = False

    def get_wiki_filename(self) -> str:
        return super().get_wiki_filename().replace(' estate.png', '.png')


class EstatePrivilege(Eu5AdvancedEntity):
    estate: Estate

    potential: Tree  # Trigger
    allow: Tree  # Trigger
    can_revoke: Tree  # Trigger

    on_activate: Tree  # Effect
    on_fully_activated: Tree  # Effect
    on_deactivate: Tree  # Effect

    country_modifier: list[Eu5Modifier]
    province_modifier: list[Eu5Modifier]
    location_modifier: list[Eu5Modifier]

    days: int
    weeks: int
    months: int
    years: int

    icon_folder = 'ESTATE_PRIVILEGE_ICON_PATH'

    def get_wiki_filename_prefix(self) -> str:
        return 'Privilege'


class HeirSelection(Eu5AdvancedEntity):
    all_in_country: bool = None
    all_in_dynasty: bool = None
    allow_children: bool = None
    allow_female: bool = None
    allow_foreign_ruler: bool = True
    allow_male: bool = None
    allowed: Trigger = None
    allowed_estates: list[Estate] = []
    cached: bool = False
    calc: ScriptValue = None
    candidate_country: Trigger = None
    heir_is_allowed: Trigger = None
    ignore_ruler: bool = False
    include_ruler_siblings: bool = None
    locked: Trigger = None
    max_possible_candidates: int = None
    potential: Trigger = None
    show_candidates: bool = True
    sibling_score: ScriptValue = None
    succession_effect: Effect = None
    term_duration: int = None
    through_female: bool = None
    traverse_family_tree: bool = False
    use_election: bool = None
    use_mothers_dynasty: bool = False

class Eu5GameConcept(GameConcept):
    family: str = ''
    alias: list['Eu5GameConcept']
    is_alias: bool = False

    def __init__(self, name: str, display_name: str, **kwargs):
        self.alias = []
        super().__init__(name, display_name, **kwargs)


class GovernmentType(Eu5AdvancedEntity):
    care_about_producing_heirs: bool = False
    color: PdxColor
    default_character_estate: Estate
    generate_consorts: bool = False
    government_power: HardcodedResource
    heir_selection: list[HeirSelection] = []
    modifier: list[Eu5Modifier]
    use_regnal_number: bool = False


class Institution(Eu5AdvancedEntity):
    age: Age
    can_spawn: Trigger
    promote_chance: ScriptValue
    spread_embraced_to_capital: ScriptValue
    spread_from_any_coast_border_location: ScriptValue
    spread_from_any_import: ScriptValue
    spread_from_friendly_coast_border_location: ScriptValue
    spread_from_was_possible_spawn: ScriptValue
    spread_scale_on_control_if_owner_embraced: int
    spread_to_market_member: ScriptValue


class LanguageFamily(NameableEntity):
    color: PdxColor = None


class Language(Eu5AdvancedEntity):
    character_name_order: str = ''
    character_name_short_regnal_number: str = ''
    color: PdxColor = None
    descendant_prefix: str = ''
    descendant_prefix_female: str = ''
    descendant_prefix_male: str = ''
    descendant_suffix: str = ''
    descendant_suffix_female: str = ''
    descendant_suffix_male: str = ''
    dialects: Tree = None
    dynasty_names: list[str] = []
    dynasty_template_keys: list[str] = []
    family: LanguageFamily = None
    female_names: list[str] = []
    first_name_conjoiner: str = ''
    location_prefix: str = ''
    location_prefix_vowel: str = ''
    location_suffix: str = ''
    lowborn: list[str] = []
    male_names: list[str] = []
    patronym_prefix_daughter: str = ''
    patronym_prefix_daughter_vowel: str = ''
    patronym_prefix_son: str = ''
    patronym_prefix_son_vowel: str = ''
    patronym_suffix: str = ''
    patronym_suffix_daughter: str = ''
    patronym_suffix_son: str = ''
    ship_names: list[str] = []


class LawPolicy(Eu5AdvancedEntity):
    allow: Trigger = None
    country_modifier: list[Eu5Modifier]
    estate_preferences: list[Estate] = [] # estate
    months: int = 0
    years: int = 0
    weeks: int = 0
    days: int = 0
    on_activate: Effect = None
    on_deactivate: Effect = None
    on_pay_price: Effect = None
    on_fully_activated: Effect = None
    potential: Trigger = None
    price: Price = NoPrice()
    wants_this_policy_bias: Any = None  # scripted number

    # for IO laws, but not an IO attribute
    diplomatic_capacity_cost: str = None
    gold: bool = None # for HRE laws?
    manpower: bool = None # for HRE laws?

    # IO attributes TODO: handle in IOs
    allow_member_annexation: bool = None
    annexation_speed: float = None
    can_build_buildings_in_members: bool = None
    can_build_rgos_in_members: bool = None
    can_build_roads_in_members: bool = None
    has_parliament: bool = None
    international_organization_modifier: list[Eu5Modifier]
    leader_change_method: str = None
    leader_change_trigger_type: str = None
    leader_type: str = None
    leadership_election_resolution: str = None
    months_between_leader_changes: int = None
    opinion_bonus: int = None
    payments_implemented: list[str] = []

    trust_bonus: int = None  # only used once in a PU law. Not sure if it is specific for policies or also for IOs

class Law(Eu5AdvancedEntity):
    allow: Trigger = None  # trigger
    custom_tags: list[str] = []
    law_category: str = ''
    law_country_group: str = None # tag
    law_gov_group: str = None # gov type
    law_religion_group: list[str] = [] # religions
    locked: Trigger = None  # trigger
    potential: Trigger = None  # trigger
    requires_vote: bool = None
    type: str = ''
    unique: bool = None# no Idea what this does

    policies: dict[str, LawPolicy]

    icon_folder = 'LAW_ICON_PATH'

    def get_wiki_filename_prefix(self) -> str:
        return ''

    def __init__(self, name: str, display_name: str, **kwargs):
        super().__init__(name, display_name, **kwargs)
        if isinstance(self.law_category, list):
            self.law_category = self.law_category[0]

    @cached_property
    def io_types(self) -> list[str]:
        if self.type != 'international_organization':
            return []
        return [typ.removeprefix('international_organization_type:') for typ in self.potential.find_all_recursively('international_organization_type')]

    @cached_property
    def io_type(self) -> str:
        if len(self.io_types) == 0:
            return ''
        elif len(self.io_types) == 1:
            return self.io_types[0]
        else:
            return 'multiple'

    @cached_property
    def law_category_loc(self):
        return eu5game.parser.formatter.resolve_nested_localizations(eu5game.parser.localize(self.law_category.upper() + '_LAW_CATEGORY'))


class LocationRank(Eu5AdvancedEntity):
    allow: Trigger = None
    build_time: int = 0
    color: PdxColor
    construction_demand: GoodsDemand = None
    country_modifier: list[Eu5Modifier]
    frame_tier: int
    is_established_city: bool = False
    max_rank: bool = False
    rank_modifier: list[Eu5Modifier]
    show_in_label: bool


class PopType(Eu5AdvancedEntity):
    assimilation_conversion_factor: float
    city_graphics: float
    color: PdxColor
    counts_towards_market_language: bool = False
    editor: float = 0
    grow: bool = False
    has_cap: bool = False
    literacy_impact: list[Eu5Modifier] = []
    migration_factor: float = 0
    pop_food_consumption: float
    pop_percentage_impact: list[Eu5Modifier] = []
    promote_to: list['PopType'] = []
    promotion_factor: float = 0
    tribal_rules: bool = False
    upper: bool = False

    possible_estates_with_triggers: dict[Estate, Trigger|None]

    def get_wiki_filename_prefix(self) -> str:
        return 'Pop'


class ReligiousAspect(Eu5AdvancedEntity):
    enabled: Trigger = None
    modifier: list[Eu5Modifier] = []
    opinions: Tree = None
    religion: list['Religion']
    visible: Trigger = None


class ReligiousFaction(Eu5AdvancedEntity):
    actions: list[str] = []
    enabled: Trigger = None
    visible: Trigger = None


class ReligiousFocus(Eu5AdvancedEntity):
    ai_will_do: Tree = None
    effect_on_completion: Tree = None
    modifier_on_completion: list[Eu5Modifier] = []
    modifier_while_progressing: list[Eu5Modifier] = []
    monthly_progress: Tree = None


class ReligionGroup(Eu5AdvancedEntity):
    allow_slaves_of_same_group: bool = True
    color: PdxColor = None
    convert_slaves_at_start: bool = None
    modifier: list[Eu5Modifier] = []


class ReligiousSchool(Eu5AdvancedEntity):
    enabled_for_character: Trigger = None
    enabled_for_country: Trigger = None
    modifier: list[Eu5Modifier] = []


class Religion(Eu5AdvancedEntity):
    ai_wants_convert: bool = False
    color: PdxColor = None
    culture_locked: bool = False
    definition_modifier: list[Eu5Modifier] = []
    enable: str = ''  # @TODO: Date
    factions: list[ReligiousFaction] = []
    group: ReligionGroup = None
    has_autocephalous_patriarchates: bool = False
    has_avatars: bool = False
    has_canonization: bool = False
    has_cardinals: bool = False
    has_doom: bool = False
    has_honor: bool = False
    has_karma: bool = False
    has_patriarchs: bool = False
    has_piety: bool = False
    has_purity: bool = False
    has_religious_head: bool = False
    has_religious_influence: bool = False
    has_rite_power: bool = False
    has_yanantin: bool = False

    # saved as str when parsing to delay loading the country list, because it depends on the religion list
    _important_country: str = None

    language: Language = None
    max_religious_figures_for_religion: Tree = None
    max_sects: int = 0
    needs_reform: bool = False
    num_religious_focuses_needed_for_reform: int = 0
    opinions: Tree = None
    reform_to_religion: 'Religion' = None
    religious_aspects: int = 0
    religious_focuses: list[ReligiousFocus] = []
    religious_school: list[ReligiousSchool] = []
    tags: list[str] = ''  # possible types: {list[eu5.eu5lib.ReligionGroup], list[str], list[eu5.eu5lib.Eu5GameConcept]}
    tithe: float = 0
    unique_names: list[str] = []
    use_icons: bool = False

    def __init__(self, name: str, display_name: str, **kwargs):
        if 'important_country' in kwargs:
            # saved as private attribute and removed to not override the cached_property
            self._important_country = kwargs['important_country']
            del kwargs['important_country']
        super().__init__(name, display_name, **kwargs)

    @cached_property
    def important_country(self) -> Country|None:
        """Lazy loaded country to avoid infinite recursion, because the country parsing uses the religions"""
        if self._important_country:
            return eu5game.parser.countries[self._important_country]
        else:
            return None


class Topography(Eu5AdvancedEntity):
    audio_tags: Tree
    blocked_in_winter: bool = False
    can_freeze_over: bool = None
    can_have_ice: bool = False
    color: PdxColor
    debug_color: PdxColor
    defender: int = 0
    has_sand: bool = False
    location_modifier: list[Eu5Modifier] = []
    movement_cost: float
    vegetation_density: float = 0
    weather_cyclone_strength_change_percent: int
    weather_front_strength_change_percent: int
    weather_tornado_strength_change_percent: int

    icon_folder = 'TOPOGRAPHY_TYPE_ICON_PATH'


class Vegetation(Eu5AdvancedEntity):
    audio_tags: Tree
    color: PdxColor
    debug_color: PdxColor
    defender: int = 0
    has_sand: bool = False
    location_modifier: list[Eu5Modifier]
    movement_cost: float

    icon_folder = 'VEGETATION_TYPE_ICON_PATH'


class InternationalOrganization(Eu5AdvancedEntity):
    ai_desire_to_allow_new_member: ScriptValue = None
    ai_desire_to_join: ScriptValue = None
    ai_issue_voting_bias: ScriptValue = None
    annexation_min_years_before: ScriptValue = None
    antagonism_modifier_for_taking_land_from_fellow_member: float = 0
    auto_disband_trigger: Trigger
    auto_leave_trigger: Trigger
    can_annex_members: Trigger = None
    can_be_created: bool = False
    can_be_enemy_trigger: Trigger = None
    can_declare_war: Trigger
    can_initiate_policy_votes: Trigger = None
    can_invite_countries: Any = None # possible types(out of 25): <class 'bool'>(24), list[bool](1)
    can_join_trigger: Trigger
    can_lead_trigger: Trigger = None
    can_leave_trigger: Trigger = None
    can_target_trigger: Trigger = None
    custom_name: 'CustomizableLocalization' = None
    declare_war_on_target_casus_belli: 'CasusBelli' = None
    diplomatic_capacity_cost: ScriptValue = None
    disband_if_no_leader: bool = None
    disband_message_trigger: Trigger = None
    enabled: Trigger = None
    expel_members_who_are_attackers_at_war_with_other_members: bool = False
    expel_members_who_are_defenders_at_war_with_other_members: bool = False
    expel_members_who_are_targets_of_other_members: bool = None
    fog_of_war_lifted: bool = False
    gives_food_access_to_members: bool = False
    gives_military_access_to_all_when_at_war: bool = False
    has_dynastic_power: bool = False
    has_enemies: bool = None
    has_leader_country: bool = None
    has_military_access: Trigger = None
    has_parliament: bool = False
    has_target: bool = None
    international_organization_modifier: list[Eu5Modifier] = []
    join_defensive_wars: str = ''
    join_defensive_wars_always: Trigger = None
    join_defensive_wars_auto_call: Trigger = None
    join_offensive_wars: str = ''
    join_offensive_wars_always: Trigger = None
    land_ownership_rule: 'InternationalOrganizationLandOwnershipRule' = None
    laws: Tree = None
    leader: Effect = None
    leader_change_method: str = '' # possible types(out of 10): <class 'str'>(10), <class 'eu5.eu5lib.Eu5GameConcept'>(5)
    leader_change_trigger_type: str = ''
    leader_color: Any = None
    leader_modifier: list[Eu5Modifier] = []
    leader_score: ScriptValue = None
    leader_title_key: str = ''
    leader_type: Any = None # possible types(out of 33): <class 'eu5.eu5lib.AttributeColumn'>(29), <class 'eu5.eu5lib.Eu5GameConcept'>(29), list[tuple](1)
    leadership_election_resolution: 'Resolution' = None
    max_active_resolutions: int = 0
    member_color: Any = None
    modifier: list[Eu5Modifier] = []
    monthly_effect: Effect = None
    months_between_leader_changes: int = 0
    no_cb_price_modifier_for_fellow_member: float = 0
    non_leader_modifier: list[Eu5Modifier] = []
    on_creation: Effect = None
    on_joined: Effect = None
    on_left: Effect = None
    only_leader_country_joins_defensive_wars: bool = False
    override_ruler_title: bool = False
    parliament_type: 'ParliamentType' = None
    payments_implemented: Any = None # possible types(out of 3): list[eu5.eu5lib.InternationalOrganizationPayment](2), list[tuple](1)
    potential_target_trigger: Trigger = None
    resolution_widget: Eu5GameConcept = None
    secondary_map_color_override: ScriptValue = None
    should_show_ruler_history: bool = True
    show_as_overlord_on_map_trigger: Trigger = None
    show_leave_message: bool = True
    show_on_diplomatic_map: bool = False
    show_strength_comparison_with_target: bool = False
    special_statuses_implemented: Any = None # possible types(out of 8): list[eu5.eu5lib.InternationalOrganizationSpecialStatus](5), <class 'list'>(2), list[tuple](1)
    subject_limited: bool = True
    target_color: PdxColor = None
    target_view_leader_color: PdxColor = None
    target_view_member_color: PdxColor = None
    title_is_suffix: bool = False
    tooltip: Effect = None
    unique: bool = None
    use_laws_as_join_reason: bool = True
    use_regnal_number: bool = False
    variables: Tree = None
    visible: Trigger
    icon_folder = 'INTERNATIONAL_ORGANIZATION_TYPE_ICON_PATH' # 30 / 35 icons found
    # icon_folder = 'INTERNATIONAL_ORGANIZATION_TYPE_ILLUSTRATION_PATH' # 27 / 35 icons found

    def get_wiki_filename(self) -> str:
        return 'IO ' + super().get_wiki_filename().removeprefix('Io ')

    def get_wiki_filename_prefix(self) -> str:
        return 'IO'
class ScriptedList(Eu5AdvancedEntity):
    @cached_property
    def triggers(self) -> list[str]:
        return [f'any_{self.name}']

    @cached_property
    def effects(self) -> list[str]:
        return [f'{prefix}_{self.name}' for prefix in ['every', 'ordered', 'random']]
############################################
#                                          #
#  Autogenerated classes with helper.py    #
#                                          #
############################################
class Achievement(Eu5AdvancedEntity):
    happened: Trigger
    possible: Trigger
    icon_folder = 'achievements' # 1 / 1 icons found
class AiDiplochance(Eu5AdvancedEntity):
    actor_at_war: int = 0
    actor_is_rival: int = 0
    actor_overlord_is_rival: int = 0
    age_female: int = 0
    allied_to_enemy: int = 0
    base: int = None
    base_location_value: int = 0
    belongs_to_international_organization: int = 0
    betrayed_ally: int = 0
    border_distance: float = 0
    call_for_peace: int = 0
    capital: int = 0
    competing_power: int = 0
    conquer_desire: float = 0
    core: int = 0
    culture_view: int = 0
    current_strength: float = 0
    demands_made: int = 0
    desperation: int = 0
    different_culture: int = 0
    different_religion: int = 0
    different_religion_group: int = 0
    diplomatic_reputation: int = 0
    disloyal_subject: int = 0
    enforced_demand: int = 0
    giving_defensive_support: int = 0
    good_interest_rate: int = 0
    has_truce: int = 0
    has_truce_with_target: int = 0
    heir: int = 0
    in_debt: float = 0
    interest_rate_too_high: int = 0
    junior_to: int = 0
    lacks_border: int = 0
    levy_availability: int = 0
    loan_ends_too_late: int = 0
    loan_ends_too_soon: int = 0
    loan_is_insignificant: int = 0
    location_value: int = 0
    low_manpower: int = 0
    making_gains: int = 0
    months_at_war: float = 0
    need_loan: int = 0
    negative_opinion: float = 0
    negative_stability: float = 0
    opinion: float = 0
    peaceoffer: int = 0
    peaceoffer_most_of_wanted: int = 0
    positive_opinion: float = 0
    potential_strength: float = 0
    price: int = 0
    price_percentage_of_treasury_funds: int = 0
    produced_goods: int = 0
    promised_land: int = 0
    province_distance: int = 0
    rank: int = 0
    rank_difference: int = 0
    receiving_defensive_support: int = 0
    recipient_at_war: int = 0
    recipient_civil_war: int = 0
    recipient_is_rival: int = 0
    recipient_occupied_beseiged_locations: int = 0
    recipient_overlord_is_rival: int = 0
    relative_strength: int = 0
    religion_view: int = 0
    royal_ties: float = 0
    same_court_language: int = 0
    same_culture: int = 0
    same_international_organization: int = 0
    same_religion: int = 0
    strategic_interest: int = 0
    target_opinion: float = 0
    too_many_loans: int = 0
    too_much_antagonism: int = 0
    trust_in_actor: float = 0
    victory: int = 0
    want_more: int = 0
    want_something_else: int = 0
    war_enthusiam: int = 0
    war_exhaustion: float = 0
    warscore: float = 0
    would_fracture_recipient_too_much: int = 0
    yesman: int = 0
class ArtistType(Eu5AdvancedEntity):
    potential: Trigger
    icon_folder = 'ARTIST_ICON_PATH' # 12 / 12 icons found
class ArtistWork(Eu5AdvancedEntity):
    allow: Trigger
    captured: bool
    location_modifier: list[Eu5Modifier] = []
    religion_scale_modifier: Eu5ModifierType = None
    icon_folder = 'WORK_OF_ART_ICON_PATH' # 21 / 21 icons found
    # icon_folder = 'WORK_OF_ART_ILLUSTRATION_PATH' # 20 / 21 icons found
class AttributeColumn(Eu5AdvancedEntity):
   pass
class AutoModifier(Eu5AdvancedEntity):
    category: str = ''
    limit: Trigger = None
    potential_trigger: Trigger = None
    requires_real: bool = True
    scales_with: ScriptValue = None # possible types(out of 50): <class 'common.paradox_parser.Tree'>(41), <class 'eu5.eu5lib.ScriptValue'>(38), <class 'eu5.eu5lib.TriggerLocalization'>(9), <class 'eu5.eu5lib.Eu5GameConcept'>(4), <class 'eu5.eu5lib.AutoModifier'>(2), <class 'eu5.eu5lib.Eu5NamedModifier'>(1), <class 'eu5.eu5lib.Eu5ModifierType'>(1)
    type: str = 'country'
class Avatar(Eu5AdvancedEntity):
    allow: Trigger = None
    country_modifier: list[Eu5Modifier]
    god: 'God'
    location_modifier: list[Eu5Modifier] = []
    icon_folder = 'AVATAR_ICON_PATH' # 20 / 20 icons found
class Bias(Eu5AdvancedEntity):
    max: int = None
    min: int = 0
    months: int = 0
    value: float
    yearly_decay: float = None
    yearly_gain: float = 0
    years: int = 0
class CabinetAction(Eu5AdvancedEntity):
    ability: Eu5GameConcept
    allow: Trigger = None
    allow_multiple: bool = None
    country_modifier: list[Eu5Modifier] = []
    days: int = 0
    is_finished: Trigger = None
    location_modifier: list[Eu5Modifier] = []
    map_marker: Tree = None
    on_activate: Effect = None
    on_deactivate: Effect = None
    on_fully_activated: Effect = None
    potential: Trigger = None
    progress: ScriptValue = None
    province_modifier: list[Eu5Modifier] = []
    select_trigger: Any = None # possible types(out of 29): <class 'common.paradox_parser.Tree'>(23), list[common.paradox_parser.Tree](6)
    societal_values: float = 0
    years: int = 0
    icon_folder = 'CABINET_ACTION_ICON_PATH' # 22 / 63 icons found
class CasusBelli(Eu5AdvancedEntity):
    additional_war_enthusiasm: float = 0
    additional_war_enthusiasm_attacker: float = 0
    additional_war_enthusiasm_defender: float = 0
    ai_cede_location_desire: ScriptValue = None
    ai_cede_province_desire: ScriptValue = None
    ai_selection_desire: ScriptValue = None
    ai_subjugation_desire: int = 0
    allow_creation: Trigger = None
    allow_declaration: Trigger = None
    allow_ports_for_reach_ai: bool = False
    allow_release_areas: bool = False
    antagonism_reduction_per_warworth_defender: float = 0
    can_expire: bool = True
    coalition: bool = False
    cut_down_in_size_cb: bool = False
    max_warscore_from_battles: int = 0
    no_cb: bool = None
    province: Trigger = None
    speed: float = 0
    trade: bool = False
    visible: Trigger = None
    war_goal_type: 'Wargoal'
    icon_folder = 'CASUS_BELLI_ICON_PATH' # 29 / 89 icons found

    def get_wiki_filename_prefix(self) -> str:
        return 'CB'

    def get_icon_filename(self) -> str:
        filename = f'{self.name}.dds'
        if (self.get_icon_folder() / filename).exists():
            return filename
        else:
            war_goal_filename = f'{self.war_goal_type.name}.dds'
            if (self.get_icon_folder() / war_goal_filename).exists():
                return war_goal_filename
            else:
                return filename
class CharacterInteraction(Eu5AdvancedEntity):
    ai_tick: Any = None # possible types(out of 27): <class 'str'>(26), list[str](1)
    ai_tick_frequency: int = 0
    ai_will_do: ScriptValue = None
    allow: Trigger = None
    context_menu_click_mode: str = ''
    effect: Effect
    is_consort_action: bool = None
    message: bool
    on_other_nation: bool = False
    on_own_nation: bool = False
    potential: Trigger
    price: str = ''
    price_modifier: ScriptValue = None
    select_trigger: Any # possible types(out of 29): <class 'common.paradox_parser.Tree'>(21), list[common.paradox_parser.Tree](8)
    sound: str = ''
    icon_folder = 'CHARACTER_INTERACTION_ICON_PATH' # 29 / 29 icons found
class ChildEducation(Eu5AdvancedEntity):
    allow: Trigger
    country_modifier: list[Eu5Modifier] = []
    modifier: list[Eu5Modifier]
    price_to_deselect: Price = None
    price_to_select: Price = None
class CoatOfArms(Eu5AdvancedEntity):
    pass
class CountryInteraction(Eu5AdvancedEntity):
    accept: ScriptValue = None
    ai_limit_per_check: int = 0
    ai_prerequisite: Trigger = None
    ai_tick: Any = None # possible types(out of 21): <class 'str'>(20), list[str](1)
    ai_tick_frequency: ScriptValue = None
    ai_will_do: ScriptValue = None
    allow: Trigger
    block_when_at_war: bool = None
    category: str = ''
    cooldown: Tree = None
    diplo_chance: Tree = None
    diplomatic_cost: 'DiplomaticCost' = None
    effect: Effect
    payee: str = ''
    payer: str = ''
    potential: Trigger = None
    price: str = ''
    price_modifier: ScriptValue = None
    reject_effect: Effect = None
    select_trigger: Any # possible types(out of 96): <class 'common.paradox_parser.Tree'>(54), list[common.paradox_parser.Tree](42)
    show_message: bool = True
    show_message_to_target: bool = True
    type: Eu5GameConcept
    use_enroute: bool = True
class CountryRank(Eu5AdvancedEntity):
    allow: Trigger
    character_ai_cooldown: int = 0
    color: PdxColor
    diplomacy_ai_cooldown: int = 0
    language_power_scale: float
    level: int
    rank_modifier: list[Eu5Modifier]
    icon_folder = 'COUNTRY_RANK_ICON_PATH' # 4 / 4 icons found
class CustomizableLocalization(Eu5AdvancedEntity):
    if_invalid_loc: str = ''
    log_loc_errors: bool = None
    parent: 'CustomizableLocalization' = None
    random_valid: bool = False
    suffix: str = ''
    text: Any = None
    type: Any = None # possible types(out of 197): <class 'eu5.eu5lib.AttributeColumn'>(194), <class 'eu5.eu5lib.Eu5GameConcept'>(194)
class DeathReason(Eu5AdvancedEntity):
    possible_parameter: Any = None # possible types(out of 20): <class 'eu5.eu5lib.AttributeColumn'>(9), <class 'eu5.eu5lib.Eu5GameConcept'>(9), <class 'list'>(6), list[tuple](1)
    random: bool = False
    trigger: Trigger = None
    weight: ScriptValue = None
class DesignatedHeirReason(Eu5AdvancedEntity):
    pass
class DiplomaticCost(Eu5AdvancedEntity):
    favors: int = 0
    spy_network: int = 0
class Disaster(Eu5AdvancedEntity):
    can_end: Trigger
    can_start: Trigger
    fire_only_once: bool = False
    image: str
    modifier: list[Eu5Modifier]
    monthly_spawn_chance: ScriptValue
    on_end: Effect
    on_monthly: Effect
    on_start: Effect
    icon_folder = 'DISASTER_ICON_PATH' # 28 / 30 icons found
    # icon_folder = 'DISASTER_ILLUSTRATION_PATH' # 18 / 30 icons found
class Disease(Eu5AdvancedEntity):
    calc_interval_days: int|list[int] # one value or a range
    character_mortality_chance: ScriptValue
    environmental_infection: float = 0
    location_infection_spread_threshold: ScriptValue = None
    location_modifier: list[Eu5Modifier]
    location_stagnation_chance: ScriptValue
    map_color: Tree
    monthly_resistance_reduction: float = None
    monthly_spawn_chance: ScriptValue
    mortality_rate: float|list[float]
    on_spread_to_country: Effect
    percentage_to_meet_their_fate_on_calc: ScriptValue
    r0: ScriptValue
    spawn: Effect
    specific_pop_type_effect: list[Tree] = []
    sub_unit_stagnation_chance: ScriptValue = None
    icon_folder = 'DISEASE_ICON_PATH' # 7 / 7 icons found
class EffectLocalization(Eu5AdvancedEntity):
    first: str = ''
    first_neg: str = ''
    first_past: str = ''
    first_past_neg: str = ''
    global_: str = ''  # extra underscore, because global is a reserved keyword
    global_neg: str = ''
    global_past: str = ''
    global_past_neg: str = ''
    none: str = ''
    none_past: str = ''
    third: str = ''
    third_neg: str = ''
    third_past: str = ''
    third_past_neg: str = ''
class EmploymentSystem(Eu5AdvancedEntity):
    ai_will_do: ScriptValue
    country_modifier: list[Eu5Modifier]
    priority: ScriptValue
class Ethnicity(Eu5AdvancedEntity):
    expressions_brow: Tree = None
    expressions_eyes: Tree = None
    expressions_forehead: Tree = None
    expressions_mouth: Tree = None
    eye_color: Tree = None
    eyelashes: Tree = None
    eyes: Tree = None
    genes = None # todo parsing
    hair_color: Tree = None
    hair_styles: Tree = None
    skin_color: Tree
    template: 'Ethnicity' = None
class FlagDefinition(Eu5AdvancedEntity):
    flag_definition: list[Tree] = []
class FormableCountry(Eu5AdvancedEntity):
    adjective: str = '' # possible types(out of 126): <class 'str'>(126), <class 'eu5.eu5lib.CustomizableLocalization'>(11)
    allow: Trigger = None
    areas: list[Area] = []
    capital_required: bool = True
    color: PdxColor = None
    continents: list[str] = []
    country_name: str  # name in the script
    flag: CoatOfArms = None
    form_effect: Effect
    level: int
    locations: list[Location] = []
    potential: Trigger
    provinces: list[Province] = []
    regions: list[Region] = []
    required_locations_fraction: float = 0
    rule: str
    sub_continents: list[SubContinent] = []
    tag: str
class GameRule(Eu5AdvancedEntity):
    default: str = ''
    options: list = []  # TODO: parsing
class Gene(Eu5AdvancedEntity):
    pass
class GenericAction(Eu5AdvancedEntity):
    ai_prerequisite: Trigger = None
    ai_tick: Any = None # possible types(out of 283): <class 'str'>(279), list[str](4)
    ai_tick_frequency: Any = None # possible types(out of 274): <class 'eu5.eu5lib.ScriptValue'>(270), list[int](4)
    ai_will_do: ScriptValue = None
    allow: Trigger = None
    automation_tick: Any = None # possible types(out of 331): <class 'str'>(312), list[str](19)
    automation_tick_frequency: Any = None # possible types(out of 330): <class 'eu5.eu5lib.ScriptValue'>(311), list[int](19)
    cooldown: Tree = None
    effect: Effect
    exclusive_group: str = ''
    message: str = ''
    player_automated_category: Any = None # possible types(out of 105): <class 'str'>(97), <class 'eu5.eu5lib.Eu5GameConcept'>(28), <class 'eu5.eu5lib.Advance'>(6), <class 'eu5.eu5lib.AttributeColumn'>(5)
    potential: Trigger = None
    price: Any = None # possible types(out of 242): <class 'str'>(237), <class 'eu5.eu5lib.ScriptValue'>(6)
    price_modifier: ScriptValue = None
    select_trigger: Any = None # possible types(out of 326): <class 'common.paradox_parser.Tree'>(178), list[common.paradox_parser.Tree](148)
    should_execute_price: bool = True
    show_in_gui_list: bool = True
    show_message: bool = None
    show_message_to_target: bool = None
    sound: str = ''
    type: Any # possible types(out of 338): <class 'eu5.eu5lib.Eu5GameConcept'>(182), <class 'eu5.eu5lib.AttributeColumn'>(176)
class GenericActionAiList(Eu5AdvancedEntity):
    actions: Any # possible types(out of 68): list[eu5.eu5lib.GenericAction](33), list[tuple](21), <class 'list'>(14)
    potential: Trigger = None
class God(Eu5AdvancedEntity):
    country_modifier: list[Eu5Modifier]
    group: list[Tree] = []
    icon: str = ''
    potential: Trigger = None
    religion: Any = None # possible types(out of 101): <class 'eu5.eu5lib.Religion'>(77), list[common.paradox_parser.Tree](7)
    icon_folder = 'GOD_ICON_PATH' # 23 / 102 icons found
class GoodsDemandCategory(Eu5AdvancedEntity):
    display: Any # possible types(out of 4): <class 'str'>(3), <class 'eu5.eu5lib.AttributeColumn'>(1), <class 'eu5.eu5lib.Eu5GameConcept'>(1)
class GovernmentReform(Eu5AdvancedEntity):
    age: Age = None
    allow: Trigger = None
    block_for_rebel: bool = False
    country_modifier: list[Eu5Modifier]
    government: GovernmentType = None
    icon: 'GovernmentReform' = None
    location_modifier: list[Eu5Modifier] = []
    locked: Trigger = None
    major: bool = False
    male_regnal_names: list[str] = []
    months: int = 0
    on_activate: Effect = None
    on_deactivate: Effect = None
    potential: Trigger = None
    societal_values: list[str] = []
    unique: bool = False
    years: float = None
    icon_folder = 'GOVERNMENT_REFORMS_ILLUSTRATION_PATH' # 285 / 288 icons found
class Hegemon(Eu5AdvancedEntity):
    gain: Trigger
    lose: Trigger
    modifier: list[Eu5Modifier]
    icon_folder = 'HEGEMONY_BORDER_PATH' # 5 / 5 icons found
class HistoricalScore(Eu5AdvancedEntity):
    score: int
    tag: Country
class HolySite(Eu5AdvancedEntity):
    avatar: Avatar = None
    god: God = None
    importance: int
    location: Location
    religions: Any # possible types(out of 207): list[eu5.eu5lib.Religion](188), list[tuple](19)
    type: 'HolySiteType'
class HolySiteType(Eu5AdvancedEntity):
    country_modifier: list[Eu5Modifier] = []
    location_modifier: list[Eu5Modifier] = []
class Insult(Eu5AdvancedEntity):
    trigger: Trigger
class InternationalOrganizationLandOwnershipRule(Eu5AdvancedEntity):
    ai_desire_to_add: ScriptValue
    allow_control_propagation: bool = False
    can_add_trigger: Trigger
    can_remove_trigger: Trigger
    modifier: list[Eu5Modifier]
    on_added: Effect
    on_removed: Effect
    owned_location_color: PdxColor = None
class InternationalOrganizationPayment(Eu5AdvancedEntity):
    get_payee_list: Effect
    get_payer_list: Effect
    maintenance_modifier: list[Tree] = []
    price: Price
    price_multiplier: ScriptValue
    proportion_for_payee: ScriptValue
    proportion_for_payer: ScriptValue
    uses_maintenance: bool
class InternationalOrganizationSpecialStatus(Eu5AdvancedEntity):
    auto_bestowal_trigger: Trigger
    auto_rescind_trigger: Trigger = None
    can_be_invited: bool = True
    can_bestow_trigger: Trigger
    elector: bool = False
    leader: bool = False
    leader_modifier: list[Eu5Modifier] = []
    map_color: Any = None # possible types(out of 22): <class 'str'>(13), <class 'common.paradox_lib.PdxColor'>(9)
    max_countries: ScriptValue = None
    modifier: list[Eu5Modifier] = []
    on_bestowed_effect: Effect = None
    on_rescinded_effect: Effect = None
    priority: int
    special_status_power: Any = None # possible types(out of 16): <class 'eu5.eu5lib.ScriptValue'>(15), <class 'eu5.eu5lib.Eu5GameConcept'>(1), <class 'eu5.eu5lib.Eu5ModifierType'>(1), <class 'eu5.eu5lib.TriggerLocalization'>(1)
    icon_folder = 'INTERNATIONAL_ORGANIZATION_SPECIAL_STATUS_ICON_PATH' # 23 / 24 icons found
class Levy(Eu5AdvancedEntity):
    allow: Trigger = None
    allow_as_crew: Trigger = None
    allowed_culture: list[Culture] = []
    allowed_pop_type: Any = None # possible types(out of 27): <class 'eu5.eu5lib.PopType'>(19), list[eu5.eu5lib.PopType](8)
    country_allow: Trigger = None
    size: float
    unit: 'UnitType'
class Mission(Eu5AdvancedEntity):
    abort: Trigger = None
    chance: int
    icon: str # possible types(out of 11): <class 'str'>(11), <class 'eu5.eu5lib.Mission'>(6)
    missions: list = []  # TODO: parsing
    on_abort: Effect
    on_completion: Effect
    on_start: Effect = None
    player_playstyle: CountryDescriptionCategory
    repeatable: bool
    select_trigger: Tree = None
    visible: Trigger
    icon_folder = 'MISSION_ILLUSTRATION_PATH' # 6 / 11 icons found
class OnAction(Eu5AdvancedEntity):
    effect: Effect = None
    events: Any = None # possible types(out of 34): list[str](33), <class 'list'>(1)
    on_actions: list['OnAction'] = []
    random_events: Tree = None
    random_on_action: Any = None
    trigger: Trigger = None
class ParliamentAgenda(Eu5AdvancedEntity):
    ai_will_do: ScriptValue = None
    allow: Trigger = None
    can_bribe: Trigger = None
    chance: int
    estate: list[Estate] = []
    importance: float = 0
    on_accept: Effect
    on_bribe: Effect = None
    potential: Trigger
    special_status: Any = None # possible types(out of 4): <class 'eu5.eu5lib.Eu5GameConcept'>(3), <class 'eu5.eu5lib.InternationalOrganizationSpecialStatus'>(3), <class 'list'>(1)
    type: AttributeColumn = None
class ParliamentIssue(Eu5AdvancedEntity):
    allow: Trigger = None
    chance: ScriptValue
    estate: CustomizableLocalization = None
    modifier_when_in_debate: list[Eu5Modifier] = []
    on_debate_failed: Effect
    on_debate_passed: Effect
    potential: Trigger = None
    selectable_for: Trigger = None
    special_status: InternationalOrganizationSpecialStatus = None
    type: AttributeColumn = None
    wants_this_parliament_issue_bias: ScriptValue = None
class ParliamentType(Eu5AdvancedEntity):
    allow: Trigger = None
    locked: Trigger = None
    modifier: list[Eu5Modifier]
    potential: Trigger = None
    type: str # international_organization or country
    icon_folder = 'PARLIAMENT_TYPES_ICON_PATH' # 8 / 14 icons found
class PeaceTreaty(Eu5AdvancedEntity):
    ai_desire: ScriptValue = None
    allow: Trigger = None
    antagonism_type: Bias = None
    are_targets_exclusive: bool = False
    base_antagonism: ScriptValue = None
    blocks_full_annexation: bool = False
    category: str
    cost: ScriptValue
    effect: Effect
    potential: Trigger
    select_trigger: Tree = None
class PersistentDna(Eu5AdvancedEntity):
    portrait_info: Tree
    priority: int
    tags: Any # possible types(out of 38): list[str](31), list[eu5.eu5lib.PersistentDna](7)
class RecruitmentMethod(Eu5AdvancedEntity):
    army: bool
    build_time: float = 0
    default: bool = False
    experience: int = 0
    strength: float = 0
    icon_folder = 'RECRUIT_METHOD_ICON_PATH' # 4 / 4 icons found
class Regency(Eu5AdvancedEntity):
    allow: Trigger
    internally_assigned: bool = False
    modifier: list[Eu5Modifier]
    start_effect: Effect
class ReligiousFigure(Eu5AdvancedEntity):
    enabled_for_religion: Trigger
    icon_folder = 'traits/religious_figures' # 2 / 2 icons found
class Resolution(Eu5AdvancedEntity):
    abstain_effect: Effect = None
    ai_proposer_risk: ScriptValue = None
    ai_tick: str = ''
    ai_will_do: Tree # possible types(out of 23): <class 'common.paradox_parser.Tree'>(23), <class 'eu5.eu5lib.ScriptValue'>(22), <class 'eu5.effect.Effect'>(1)
    allow: Trigger
    can_vote: Trigger = None
    cooldown: Tree = None
    days: int = 0
    effect: Effect

    # saved as str when parsing to delay loading the IO list, because it depends on the resolution list
    _international_organization_type: str = None

    is_live: Trigger = None
    loc: str = '' # possible types(out of 3): <class 'str'>(3), <class 'eu5.eu5lib.Eu5GameConcept'>(2), <class 'eu5.eu5lib.Resolution'>(1)
    months: int = 0
    potential: Trigger
    price: ScriptValue = None
    proposal_price: str = ''
    propose_effect: Effect = None
    reject_effect: Effect = None
    requires_explicit_votes: bool = True
    requires_vote: Trigger = None
    select_trigger: list[Tree]
    should_finalize_vote: Trigger = None
    show_message: bool = True
    total_votes_needed: ScriptValue = None
    vote_effect: Effect = None
    vote_ongoing_modifier: list[Eu5Modifier] = []
    votes: ScriptValue = None

    def __init__(self, name: str, display_name: str, **kwargs):
        if 'international_organization_type' in kwargs:
            # saved as private attribute and removed to not override the cached_property
            self._international_organization_type = kwargs['international_organization_type']
            del kwargs['international_organization_type']
        super().__init__(name, display_name, **kwargs)

    @cached_property
    def international_organization_type(self) -> InternationalOrganization|None:
        """Lazy loaded country to avoid infinite recursion, because the IO parsing uses the resolutions"""
        if self._international_organization_type:
            return eu5game.parser.international_organizations[self._international_organization_type]
        else:
            return None

class RivalCriteria(Eu5AdvancedEntity):
    enabled: Trigger
class RoadType(Eu5AdvancedEntity):
    build_time_per_unit_distance: int
    color: PdxColor
    construction_demand: GoodsDemand
    level: int
    maintenance_demand: GoodsDemand
    movement_cost: float
    price_per_unit_distance: Price
    proximity: int = 0
    spline_style_id: int
    icon_folder = 'ROAD_ICON_PATH' # 4 / 4 icons found
class Scenario(Eu5AdvancedEntity):
    country: Country
    flag: Any = None # possible types(out of 8): <class 'eu5.eu5lib.CoatOfArms'>(7), <class 'eu5.eu5lib.Scenario'>(5)
    player_playstyle: str
    player_proficiency: str
class ScriptableHint(Eu5AdvancedEntity):
    hide: Trigger = None
    hint_tag: Eu5GameConcept = None
    player_playstyle: list[Tree] = []
    priority: Trigger = None
    sort_priority: int = None
class ScriptedCountryName(Eu5AdvancedEntity):
    capital_trigger: Trigger
    country_trigger: Trigger
    location_trigger: Trigger
class ScriptedDiplomaticObjective(Eu5AdvancedEntity):
    actor_trigger: Trigger
    cancel_trigger: Trigger
    country_interactions: Tree
    country_relations: Tree
    days_between_checks: int
    improve_relation: bool
    max_allowed: int
    pause_trigger: Trigger
    recipient_list_builder: Trigger
    recipient_priority: ScriptValue
    recipient_trigger: Trigger
class ScriptedEffect(Eu5AdvancedEntity):
   pass
class ScriptedRelation(Eu5AdvancedEntity):
    annulled_by_peace_treaty: bool = False
    block_building: bool = False
    block_when_at_war: bool = None
    break_effect: Effect = None
    break_enabled: Trigger = None
    break_on_becoming_subject: bool = False
    break_on_not_spying: bool = False
    break_on_war: bool = False
    break_visible: bool = True
    buy_price: Price = None
    called_in_defensively: str = ''
    called_in_offensively: str = ''
    cancel_effect: Effect = None
    cancel_enabled: Trigger = None
    cancel_visible: bool = True
    category: Tree = None
    dangerous_relation: bool = False
    diplomatic_capacity_cost: ScriptValue = None
    diplomatic_cost_offer: DiplomaticCost = None
    diplomatic_cost_request: DiplomaticCost = None
    disallow_war: bool = False
    embargo: bool = False
    expire_effect: Effect = None
    favors_to_first: ScriptValue = None
    favors_to_second: ScriptValue = None
    fleet_basing_rights: bool = False
    food_access: bool = False
    giving_color: PdxColor = None
    gold_to_first: int = 0
    gold_to_second: ScriptValue = None
    institution_spread_to_first: ScriptValue = None
    institution_spread_to_second: ScriptValue = None
    is_exempt_from_isolation: bool = False
    is_exempt_from_sound_toll: bool = False
    lifts_fog_of_war: bool = False
    lifts_trade_protection: bool = False
    merchant_fraction_to_first: float = 0
    military_access: bool = False
    monthly_ongoing_price_first_country: Price = None
    mutual_color: str = ''
    offer_declined_effect: Effect = None
    offer_effect: Effect = None
    offer_enabled: Trigger = None
    offer_visible: bool = True
    receiving_color: Any = None
    relation_type: str
    relation_type_for_ai: Eu5GameConcept = None
    request_declined_effect: Effect = None
    request_effect: Effect = None
    request_enabled: Trigger = None
    request_visible: Any = None # possible types(out of 16): <class 'bool'>(15), list[bool](1)
    skip_diplomat_for_cancel: bool = False
    trade_to_first: float = 0
    trade_to_second: float = 0
    type: Eu5GameConcept
    use_with_enemies: bool = False
    uses_diplo_capacity: str = ''
    visible: Trigger = None
    wants_to_give: ScriptValue = None
    wants_to_give_diplo_chance: Tree = None
    wants_to_keep: ScriptValue = None
    wants_to_keep_diplo_chance: Tree = None
    wants_to_receive: ScriptValue = None
    wants_to_receive_diplo_chance: Tree = None
    will_expire_trigger: Trigger = None
class ScriptedTrigger(Eu5AdvancedEntity):
    pass
class Situation(Eu5AdvancedEntity):
    can_end: Trigger
    can_start: Trigger
    international_organization_type: InternationalOrganization = None
    is_data_map: bool = False
    map_color: Tree # possible types(out of 22): <class 'common.paradox_parser.Tree'>(22), <class 'eu5.eu5lib.ScriptValue'>(19), <class 'eu5.effect.Effect'>(3)
    monthly_spawn_chance: ScriptValue
    on_ended: Effect
    on_ending: Effect = None
    on_monthly: Effect
    on_start: Effect
    resolution: Resolution = None
    secondary_map_color: ScriptValue = None
    tooltip: Effect = None
    visible: Trigger
    voters: str = ''
    icon_folder = 'SITUATION_ICON_PATH' # 22 / 22 icons found
    # icon_folder = 'SITUATIONS_ILLUSTRATION_PATH' # 22 / 22 icons found
class SocietalValue(Eu5AdvancedEntity):
    age: Age = None
    allow: Trigger = None
    left_modifier: list[Eu5Modifier]
    opinion_importance_multiplier: float = 0
    right_modifier: list[Eu5Modifier]
class SubjectMilitaryStance(Eu5AdvancedEntity):
    army_logistics_priority: int
    blockade_port_priority: int
    carpet_siege_enemy_locations_priority: int
    carpet_siege_own_locations_attacking_priority: int
    carpet_siege_own_locations_defending_priority: int
    chase_navy_priority: int
    chase_unit_enemy_location_priority: int
    chase_unit_friendly_location_priority: int
    chase_unit_neutral_location_priority: int
    chase_unit_overlord_location_priority: int
    chase_unit_own_location_priority: int
    chase_unit_subject_location_priority: int
    defend_ally_territory_priority: int
    defend_own_territory_priority: int
    hunt_army_priority: int
    hunt_navy_priority: int
    hunt_pirates_priority: int
    is_default: bool = False
    maintain_military_levels_priority: int
    merge_units_priority: int
    navy_logistics_priority: int
    repatriate_ships_priority: int
    repatriate_troops_priority: int
    support_armies_priority: int
    support_sieges_priority: int = None
    suppress_rebel_priority: int
class SubjectType(Eu5AdvancedEntity):
    ai_wants_to_be_overlord: ScriptValue = None
    allow_declaring_wars: bool = False
    annexation_min_opinion: int = 0
    annexation_min_years_before: int = None
    annexation_speed: int
    annexation_stall_opinion: int = 0
    can_attack: Trigger = None
    can_be_force_broken_in_peace_treaty: bool = True
    can_change_heir_selection: bool
    can_change_rank: bool
    can_overlord_build_buildings: bool = False
    can_overlord_build_rgos: bool = False
    can_overlord_build_roads: bool = False
    can_overlord_build_ships: bool = False
    can_overlord_recruit_regiments: bool = False
    can_rival: Trigger = None
    color: PdxColor = None
    creation_visible: Trigger = None
    diplo_chance_accept_overlord: Tree = None
    diplo_chance_accept_subject: Tree = None
    diplomatic_capacity_cost_scale: float
    enabled_through_diplomacy: Trigger = None
    fleet_basing_rights: bool = False
    food_access: bool = False
    government: GovernmentType = None
    great_power_score_transfer: float
    has_limited_diplomacy: bool
    has_overlords_ruler: bool
    institution_spread_to_overlord: ScriptValue
    institution_spread_to_subject: ScriptValue
    is_colonial_subject: bool = False
    join_defensive_wars_always: Trigger = None
    join_offensive_wars_always: Trigger = None
    level: int
    merchants_to_overlord_fraction: float = 0
    minimum_opinion_for_offer: int = 0
    on_disable: Effect = None
    on_enable: Effect = None
    only_overlord_court_language: bool = False
    only_overlord_culture: bool = False
    only_overlord_or_kindred_culture: bool = False
    overlord_can_cancel: bool
    overlord_can_enforce_peace_on_subject: bool = False
    overlord_inherit_if_no_heir: bool = False
    overlord_modifier: list[Eu5Modifier]
    overlord_share_exploration: bool = False
    release_country_enabled: Trigger = None
    strength_vs_overlord: float = 0
    subject_can_cancel: bool = None
    subject_creation_enabled: Trigger = None
    subject_modifier: list[Eu5Modifier]
    subject_pays: Price
    type: Eu5GameConcept = None
    use_overlord_laws: bool = False
    use_overlord_map_color: bool = None
    use_overlord_map_name: bool = True
    visible_through_diplomacy: Trigger
    visible_through_treaty: Trigger = None
    war_score_cost: float = 0
    icon_folder = 'SUBJECT_TYPES_ICON_PATH' # 12 / 19 icons found
class TownSetup(Eu5AdvancedEntity):
    building_counts: dict[Building, int]  # TODO: parsing
class Trait(Eu5AdvancedEntity):
    allow: Trigger = None
    category: Eu5GameConcept
    chance: Tree = None
    flavor: 'TraitFlavor' = None
    modifier: list[Eu5Modifier]
    icon_folder = 'traits' # 101 / 102 icons found
class TraitFlavor(Eu5AdvancedEntity):
    color: PdxColor
class TriggerLocalization(Eu5AdvancedEntity):
    first: str = ''
    first_not: str = ''
    global_: str = ''  # extra underscore, because global is a reserved keyword
    global_not: str = ''
    none: str = ''
    none_not: str = ''
    third: str = ''
    third_not: str = ''
class UnitAbility(Eu5AdvancedEntity):
    ai_will_do: ScriptValue = None
    ai_will_revoke: ScriptValue = None
    allow: Trigger
    animation_gfx_override: int = 0
    army_only: bool = False
    cancel_on_combat: bool = False
    cancel_on_combat_end: bool = None
    cancel_on_move: bool = False
    confirm: bool = False
    duration: int = 0
    finish_effect: Effect = None
    finished_when: Trigger = None
    hidden: Trigger = None
    map: bool = False
    modifier: list[Eu5Modifier] = []
    navy_only: bool = False
    start_effect: Effect = None
    toggle: bool
    icon_folder = 'UNIT_ABILITY_ICON_PATH' # 14 / 14 icons found
class UnitCategory(Eu5AdvancedEntity):
    ai_weight: float = 0
    anti_piracy_warfare: float = 0
    assault: bool = False
    attrition_loss: float = 0
    attrition_weight: float = 0
    auxiliary: bool = False
    blockade_capacity: float = 0
    bombard: bool = False
    build_time: ScriptValue
    combat: Tree = None
    combat_speed: float
    construction_demand: GoodsDemand
    flanking_ability: float
    food_consumption_per_strength: int = 0
    food_storage_per_strength: float = 0
    frontage: float
    initiative: int
    is_army: bool
    is_garrison: bool = False
    maintenance_demand: GoodsDemand
    max_strength: float
    morale_damage_taken: float = 0
    movement_speed: float = 0
    secure_flanks_defense: float = None
    startup_amount: int = 0
    strength_damage_taken: float = 0
    transport_capacity: float = 0
    icon_folder = 'UNIT_CATEGORY_ICON_PATH' # 8 / 8 icons found
    # icon_folder = 'UNIT_TYPE_ILLUSTRATION_PATH' # 8 / 8 icons found
    # icon_folder = 'UNIT_BATTLE_CATEGORY_ICON_PATH' # 7 / 8 icons found
    # icon_folder = 'UNIT_TYPE_ILLUSTRATION_MASK_PATH' # 6 / 8 icons found
class UnitType(Eu5AdvancedEntity):
    age: Age = None
    artillery_barrage: int = 0
    attrition_loss: float = 0
    attrition_weight: float = 0
    blockade_capacity: float = 0
    bombard_efficiency: float = 0
    build_time_modifier: float = 0
    buildable: bool = None
    cannons: int = None
    category: UnitCategory
    color: PdxColor = None
    combat: Tree = None
    combat_power: float = 0
    combat_speed: float = 0
    construction_demand: GoodsDemand = None
    copy_from: 'UnitType' = None
    country_potential: Any = None # possible types(out of 24): <class 'eu5.trigger.Trigger'>(22), <class 'eu5.effect.Effect'>(3), list[common.paradox_parser.Tree](2)
    crew_size: float = 0
    default: bool = False
    flanking_ability: float = 0
    food_consumption_per_strength: float = 0
    food_storage_per_strength: float = 0
    frontage: float = 0
    gfx_tags: Any = None # possible types(out of 153): list[str](152), list[list](1)
    hull_size: int = 0
    impact: Tree = None
    initiative: float = 0
    levy: bool = False
    light: Any = None # possible types(out of 43): <class 'bool'>(42), list[bool](1)
    limit: ScriptValue = None
    location_potential: Trigger = None
    location_trigger: Trigger = None
    maintenance_demand: GoodsDemand = None
    maritime_presence: ScriptValue = None
    max_strength: float = 0
    mercenaries_per_location: Any = None # possible types(out of 78): <class 'common.paradox_parser.Tree'>(76), list[common.paradox_parser.Tree](2)
    morale_damage_done: float = 0
    morale_damage_taken: float = 0
    movement_speed: float = 0
    strength_damage_done: float = 0
    strength_damage_taken: Any = None # possible types(out of 48): <class 'float'>(47), list[float](1)
    transport_capacity: float = 0
    upgrades_to: Any = None # possible types(out of 71): <class 'eu5.eu5lib.UnitType'>(70), list[eu5.eu5lib.UnitType](1)
    upgrades_to_only: 'UnitType' = None
    use_ship_names: bool = None
class Wargoal(Eu5AdvancedEntity):
    attacker: Tree = None
    defender: Any = None # possible types(out of 32): <class 'common.paradox_parser.Tree'>(31), list[common.paradox_parser.Tree](1)
    ticking_war_score: float = 0
    type: str # possible types(out of 56): <class 'str'>(56), <class 'eu5.eu5lib.Wargoal'>(44)
    war_name: str = ''
    war_name_is_country_order_agnostic: bool = False
    icon_folder = 'WARGOAL_ICON_PATH' # 53 / 56 icons found
    # icon_folder = 'CASUS_BELLI_ICON_PATH' # 53 / 56 icons found
