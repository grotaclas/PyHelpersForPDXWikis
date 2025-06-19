"""This module contains many classes which represent Victoria 3 game entities.

Most of them are subclasses of NameableEntity which provides a name and display name or of AdvancedEntity
which adds a description, icon, modifiers and required technologies(not all subclasses use all of these)"""
import inspect
from functools import cached_property
from operator import attrgetter

from common.paradox_lib import NameableEntity, PdxColor, AdvancedEntity, Modifier
from common.paradox_parser import Tree
from vic3.game import vic3game


class Vic3AdvancedEntity(AdvancedEntity):
    """Adds various extra fields. Not all of them are used by all subclasses"""

    required_technologies: list['Technology'] = []


class NamedModifier(Vic3AdvancedEntity):
    """Modifier describes several related concepts.
    This class is for entities from the common/modifiers folder which groups together multiple modifiers and
    gives them a name, icon and description
    For the individual modifiers see the class Modifier
    For the possible types of these modifiers see ModifierType"""

    def format_for_wiki(self, time_limit_weeks: int = None) -> str:
        # @TODO: upload icons to the wiki and add them here
        return "Modifier ''“{}”''{} giving:\n* {}".format(
                                                       self.display_name,
                                                       ' for {} weeks'.format(time_limit_weeks) if time_limit_weeks is not None else '',
                                                       '\n* '.join([modifier.format_for_wiki() for modifier in self.modifier]))


class StateResource:
    def __init__(self, building_group: str, amount: int = 0, undiscovered_amount: int = 0, is_arable: bool = False,
                 is_capped: bool = False, is_discoverable: bool = False):
        self.building_group = building_group
        self.amount = amount
        self.undiscovered_amount = undiscovered_amount
        self.is_arable = is_arable
        self.is_capped = is_capped
        self.is_discoverable = is_discoverable

    def get_max_amount(self):
        return self.amount + self.undiscovered_amount


class State(NameableEntity):
    id: int
    arable_land: int = 0
    # arable_resources: list[str]
    # capped_resources: Tree
    provinces: list[str]
    resources: dict[str, StateResource] = []
    subsistence_building: str
    traits: list['StateTrait'] = []
    owners: list[str]
    homelands: list[str]

    def get_strategic_region(self):
        return vic3game.parser.state_to_strategic_region_map[self.name]

    def is_water(self):
        return self.get_strategic_region().is_water


class StateTrait(Vic3AdvancedEntity):
    def __init__(self, name: str, display_name: str,
                 disabling_technologies: list['Technology'] = None,
                 required_techs_for_colonization: list['Technology'] = None, **kwargs):
        kwargs['required_technologies'] = disabling_technologies + required_techs_for_colonization
        super().__init__(name, display_name, **kwargs)
        self.disabling_technologies = disabling_technologies
        self.required_techs_for_colonization = required_techs_for_colonization

    def get_wiki_icon(self) -> str:
        return self.get_wiki_file_tag()

    @cached_property
    def states(self) -> list[State]:
        return [state for state in vic3game.parser.states.values() if self in state.traits]


class StrategicRegion(NameableEntity):
    states: list[State]
    is_water = False

    @cached_property
    def countries(self) -> list['Country']:
        all_countries = vic3game.parser.countries
        return sorted({all_countries[country] for state in self.states for country in state.owners}, key=attrgetter('display_name'))


class Country(NameableEntity):

    def __init__(self, tag: str, display_name: str, color: PdxColor, country_type: str, tier: str, capital_state: State,
                 cultures: list[str]):
        super().__init__(tag, display_name)
        self.tag = tag
        self.color = color
        self.type = country_type
        self.tier = tier
        self.capital_state = capital_state
        self.cultures = cultures

    def exists(self):
        """exists at the start of the game"""
        return self.tag in vic3game.parser.existing_tags

    def is_formable(self):
        return self.tag in vic3game.parser.formable_tags

    def is_event_formable(self):
        return self.tag in vic3game.parser.event_formed_tags

    def is_releasable(self):
        return self.tag in vic3game.parser.releasable_tags

    def is_event_releasable(self):
        return self.tag in vic3game.parser.event_releasable_tags

    def get_wiki_link_with_icon(self):
        return '{{flag|' + self.display_name + '}}'

class LawGroup(NameableEntity):
    laws: list['Law']
    law_category_wiki_pages = {
        'power_structure': 'Power structure laws',
        'economy': 'Economy laws',
        'human_rights': 'Human rights laws'
    }

    def __init__(self, name: str, display_name: str, law_group_category: str):
        super().__init__(name, display_name)
        self.law_group_category = law_group_category
        self.laws = []

    def add_law(self, law: 'Law'):
        self.laws.append(law)

    def get_wiki_page(self) -> str:
        return self.law_category_wiki_pages[self.law_group_category]


class Law(Vic3AdvancedEntity):
    group: LawGroup = None

    def get_wiki_page_name(self) -> str:
        return self.group.get_wiki_page()

    def get_wiki_icon(self) -> str:
        return self.get_wiki_file_tag()


class Technology(Vic3AdvancedEntity):
    wiki_pages = {'production': 'Production technology', 'military': 'Military technology', 'society': 'Society technology'}

    category: str
    era: int

    def get_unlocks(self):
        return vic3game.parser.technology_unlocks[self.name]

    def get_wiki_filename_prefix(self):
        return 'Invention'

    def get_wiki_icon(self) -> str:
        return self.get_wiki_file_tag()

    def get_wiki_page_name(self) -> str:
        return self.wiki_pages[self.category]


class BuildingGroup(NameableEntity):
    parent_group: 'BuildingGroup' = None
    category: str = None
    always_possible: bool = False
    economy_of_scale: bool = False
    is_subsistence: bool = False
    auto_place_buildings: bool = False
    capped_by_resources: bool = False
    discoverable_resource: bool = False
    depletable_resource: bool = False
    can_use_slaves: bool = False
    land_usage: str = None
    cash_reserves_max: int = 0
    stateregion_max_level: bool = False
    urbanization: int = 0
    min_hiring_rate: float = None  # filled from NDefines::NEconomy::DEFAULT_MIN_HIRING_RATE by the parser
    max_hiring_rate: float = None  # filled from NDefines::NEconomy::DEFAULT_MAX_HIRING_RATE by the parser
    proportionality_limit: float = None  # filled from NDefines::NEconomy::EMPLOYMENT_PROPORTIONALITY_LIMIT
    hires_unemployed_only: bool = False
    infrastructure_usage_per_level: int = 0
    fired_pops_become_radical: bool = True
    pays_taxes: bool = True
    is_government_funded: bool = False
    created_by_trade_routes: bool = False
    subsidized: bool = False
    is_military: bool = False
    default_building: str = None
    ignores_productivity_when_hiring: bool = False
    min_productivity_to_hire: float = 0
    owns_other_buildings: bool = False
    always_self_owning: bool = False
    has_trade_revenue: bool = False
    company_headquarter: bool = False
    regional_company_headquarter: bool = False

    def __init__(self, name: str, display_name: str, parent_group: 'BuildingGroup' = None, **kwargs):
        super().__init__(name, display_name)
        for attribute in inspect.get_annotations(BuildingGroup):
            if attribute in kwargs:
                setattr(self, attribute, kwargs[attribute])
            elif (parent_group is not None) and hasattr(parent_group, attribute):
                setattr(self, attribute, getattr(parent_group, attribute))
        self.parent_group = parent_group

    def has_sub_groups(self) -> bool:
        """We assume that default_building means that we are at the lowest level"""
        return self.default_building is None


class Building(Vic3AdvancedEntity):
    building_group: BuildingGroup
    production_method_groups: list[str] = None
    required_construction: int = None
    unique: bool = False
    enable_air_connection: bool = False
    downsizeable: bool = True
    has_max_level: bool = False
    buildable: bool = True
    ignore_stateregion_max_level: bool = False
    canal: str = None
    expandable: bool = True
    location: State = None

    def get_wiki_icon(self) -> str:
        return self.get_wiki_file_tag()

    def get_wiki_page_name(self) -> str:
        return 'List of buildings'

    @cached_property
    def production_methods(self) -> list['ProductionMethod']:
        return [pm for pm in vic3game.parser.production_methods.values() if self in pm.buildings]

    @cached_property
    def building_groups_names_with_parents(self) -> list[str]:
        group_names = []
        bg = self.building_group
        while bg is not None:
            group_names.append(bg.name)
            bg = bg.parent_group
        return group_names


class ProductionMethodGroup(Vic3AdvancedEntity):
    production_methods: list[str] = None


class ProductionMethod(Vic3AdvancedEntity):
    building_modifiers: dict[str, list[Modifier]] = {}
    country_modifiers: dict[str, list[Modifier]] = {}
    state_modifiers: dict[str, list[Modifier]] = {}
    timed_modifiers: list[NamedModifier] = []
    disallowing_laws: list[Law] = []
    unlocking_laws: list[Law] = []
    unlocking_production_methods: list['ProductionMethod'] = []
    unlocking_religions: list[str] = []
    unlocking_principles: list['Principle'] = []
    replacement_if_valid: str = None

    @cached_property
    def groups(self) -> list[ProductionMethodGroup]:
        return [group for group in vic3game.parser.production_method_groups.values()
                if self.name in group.production_methods]

    @cached_property
    def buildings(self) -> list[Building]:
        group_names = {group.name for group in self.groups}
        return [building for building in vic3game.parser.buildings.values()
                if not group_names.isdisjoint(set(building.production_method_groups))]

    def get_wiki_icon(self) -> str:
        return self.get_wiki_file_tag()

    def get_wiki_filename_prefix(self) -> str:
        return 'Method'

    def get_wiki_page_name(self) -> str:
        return 'List of production methods'


class Decree(Vic3AdvancedEntity):
    cost: int = 0
    valid: Tree = None
    unlocking_laws: list[Law] = []  # currently unused

    def get_wiki_icon(self) -> str:
        return self.get_wiki_file_tag()

    def get_wiki_page_name(self) -> str:
        return 'Decrees'


class DiplomaticAction(Vic3AdvancedEntity):
    def get_wiki_icon(self) -> str:
        return self.get_wiki_file_tag()

    def get_wiki_page_name(self) -> str:
        return 'Diplomatic actions'

    def get_wiki_filename(self) -> str:
        return f'Diplomacy {self.display_name.lower()}.png'


class Party(Vic3AdvancedEntity):
    def get_wiki_icon(self) -> str:
        return self.get_wiki_file_tag()

    def get_wiki_page_name(self) -> str:
        return 'Political party'


class Ideology(Vic3AdvancedEntity):
    character_ideology: bool = False
    priority: int = 0
    show_in_list: bool = True
    leader_weight: Tree
    possible: Tree
    law_approvals: dict[Law, str]


class InterestGroup(Vic3AdvancedEntity):
    def get_wiki_link_with_icon(self) -> str:
        return self.get_wiki_icon() + ' ' + self.display_name


class PopType(Vic3AdvancedEntity):
    display_name_without_icon: str


class Achievement(Vic3AdvancedEntity):
    possible: Tree
    happened: Tree


class Character(NameableEntity):
    first_name: str
    last_name: str
    country: Country = None
    female: bool = False
    culture: str = ''
    age: int
    birth_date: str
    dna: str = ''
    religion: str = ''
    interest_group: InterestGroup = None
    ideology: str = ''
    traits: list[str] = []
    commander_rank: str = None
    hq: str
    ruler: bool = False
    heir: bool = False
    ig_leader: bool = False
    is_admiral: bool = False
    is_general: bool = False
    is_agitator: bool = False
    noble: bool = False
    dlc: str = ''
    template: 'Character' = None
    is_template: bool = False
    historical: bool = False

    agitator_usage: Tree = None
    commander_usage: Tree = None
    interest_group_leader_usage: Tree = None

    start: str = None
    end: str = None

    def __init__(self, name: str, display_name: str, **kwargs):
        if 'template' in kwargs:
            kwargs = vars(kwargs['template']) | kwargs
            del kwargs['name']
            del kwargs['display_name']
        if 'first_name' in kwargs:
            display_name = kwargs['first_name'] + ' ' + kwargs['last_name']
        super().__init__(name, display_name, **kwargs)

    def get_roles(self) -> list[str]:
        return [role for role, has_role in {
            'Ruler': self.ruler,
            'Heir': self.heir,
            'Politician': self.ig_leader or self.interest_group_leader_usage,
            'General': self.is_general or (self.commander_usage and self.commander_usage['role'] == 'general'),
            'Admiral': self.is_admiral or (self.commander_usage and self.commander_usage['role'] == 'admiral'),
            'Agitator': self.is_agitator or self.agitator_usage,
        }.items() if has_role]

    @cached_property
    def availability(self) -> str:
        result = ''
        if self.start is not None:
            result = self.start
        if self.end is not None:
            result = f'{result} - {self.end}'
        return result


class PrincipleGroup(Vic3AdvancedEntity):
    blocking_identity: str = None
    primary_for_identity: str = None
    unlocking_identity: str = None
    levels: list[str]


class Principle(Vic3AdvancedEntity):
    ai_weight: Tree
    allows_foreign_investment_in_lower_rank: bool
    background: str
    incompatible_with: str
    institution: str
    institution_modifier: Tree
    leader_modifier: Tree
    member_modifier: Tree
    non_leader_modifier: Tree
    possible: Tree
    power_bloc_modifier: Tree
    remainder: list
    visible: Tree

    group: PrincipleGroup
    level: int