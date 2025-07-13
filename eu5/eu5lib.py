import re
from enum import StrEnum
from functools import cached_property
from pathlib import Path

from common.paradox_lib import GameConcept, NameableEntity, AdvancedEntity, PdxColor, ModifierType, Modifier, IconMixin
from common.paradox_parser import Tree
from eu5.game import eu5game


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

    icon_file: str = None
    "relative path to the icon file"
    negative_icon_file: str = None
    "relative path to the file for the negative icon(if any)"

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
        if display_name != '(unused)':
            display_name = self.parser.formatter.strip_formatting(display_name, strip_newlines=True)
        description = self.parser.localize('MODIFIER_TYPE_DESC_' + self.name)
        description = self.parser.formatter.format_localization_text(description, [])
        return display_name, description

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

    def get_icon_filename(self) -> str:
        if self.icon:
            name = self.icon
        else:
            name = self.name
        return f'{name}.dds'

    def get_icon_path(self) -> Path:
        base_icon_folder = eu5game.game_path / 'game/main_menu/gfx/interface/icons'
        if self.icon_folder is None:
            icon_folder = re.sub(r'(?<!^)(?=[A-Z])', '_', self.__class__.__name__).lower()
            path = base_icon_folder / icon_folder
            if not path.exists():
                # try plural
                icon_folder += 's'
                path = base_icon_folder / icon_folder
                if not path.exists():
                    raise Exception(f'No icon folder for class "{self.__class__.__name__}"')
        else:
            if self.icon_folder in eu5game.parser.defines['NGameIcons']:
                base_icon_folder = eu5game.game_path / 'game/main_menu'
                icon_folder = eu5game.parser.defines['NGameIcons'][self.icon_folder]
            else:
                icon_folder = self.icon_folder

        return base_icon_folder / icon_folder / self.get_icon_filename()

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


class Trigger(Tree):
    """Placeholder"""
    pass


class Effect(Tree):
    """Placeholder"""
    pass


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
    in_tree_of: any  # possible types: {<class 'list'>, <class 'str'>}
    modifier_while_progressing: Tree
    potential: Trigger = None
    requires: list['Advance'] = []
    research_cost: float  # percentage?
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
    default_market_price: float = 1
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
    court_language: str = ''
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
    allow_male: bool = None
    allowed: Trigger = None
    allowed_estates: list[Estate] = []
    cached: bool = None
    calc: Tree = None
    candidate_country: Trigger = None
    heir_is_allowed: Trigger = None
    ignore_ruler: bool = False
    include_ruler_siblings: bool = None
    locked: Trigger = None
    max_possible_candidates: int = None
    potential: Trigger = None
    show_candidates: bool = None
    sibling_score: Tree = None  # @TODO: value calculation
    succession_effect: Effect = None
    term_duration: int = 0
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
    wants_this_policy_bias: any = None  # scripted number

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
