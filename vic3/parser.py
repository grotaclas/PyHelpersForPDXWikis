import inspect
from typing import Callable, TypeVar, Type

from PyHelpersForPDXWikis.localsettings import VIC3DIR
from common.paradox_parser import ParadoxParser
from vic3.vic3lib import *
from common.paradox_lib import NameableEntity
AE = TypeVar('AE', bound=AdvancedEntity)
NE = TypeVar('NE', bound=NameableEntity)


class Vic3Parser:
    """Parses Victoria 3 game data into objects of the vic3lib module.

    This object should not be constructed directly, instead it should be accessed as vic3game.parser so that there
    is only one instance which can cache the data.

    The data can be accessed as properties of this object. They are cached_properties so that the parsing is only done
    once.

    parse_advanced_entities() and parse_advanced_entities() can be used to easily add parsing for new entities.
    """

    # allows the overriding of localisation strings
    localizationOverrides = {'recognized': 'Recognized'}  # there doesn't seem to be a localization for this

    def __init__(self):
        self.parser = ParadoxParser(VIC3DIR / 'game')

    @cached_property
    def _localisation_dict(self):
        localisation_dict = {}
        for path in (VIC3DIR / 'game' / 'localization' / 'english').glob('**/*_l_english.yml'):
            with path.open(encoding='utf-8-sig') as f:
                for line in f:
                    match = re.fullmatch(r'\s*([^#\s:]+):\d?\s*"(.*)"[^"]*', line)
                    if match:
                        localisation_dict[match.group(1)] = match.group(2)
        return localisation_dict

    def localize(self, key: str, default: str = None) -> str:
        """localize the key from the english vic3 localisation files

        if the key is not found, the default is returned
        unless it is None in which case the key is returned
        """
        if default is None:
            default = key

        if key in self.localizationOverrides:
            return self.localizationOverrides[key]
        else:
            return self._localisation_dict.get(key, default)

    def parse_nameable_entities(self, folder: str, entity_class: Type[NE],
                                extra_data_functions: dict[str, Callable[[str, Tree], any]] = None,
                                transform_value_functions: dict[str, Callable[[any], any]] = None) -> dict[str, NE]:
        """parse a folder into objects which are subclasses of NameableEntity

        Args:
            folder: relative to the 'steamapps/common/Victoria 3/game' folder
            entity_class: each entry in the files will create one of these objects. All the data will be passed as
                          keyword arguments to the constructor. If the NameableEntity constructor is not overridden, it
                          will turn these arguments into properties of the object
            extra_data_functions: create extra entries in the data. For each key in this dict, the corresponding function
                                  will be called with the name of the entity and the data dict as parameter. The return
                                  value will be added to the data dict under the same key
            transform_value_functions: the functions in this dict are called with the value of the data which matches
                                       the key of this dict. If the key is not present in the data, the function won't
                                       be called. The function must return the new value for the data

        Returns:
            a dict between the top level keys in the folder and the entity_class objects which were created from them
        """
        if extra_data_functions is None:
            extra_data_functions = {}
        if transform_value_functions is None:
            transform_value_functions = {}
        if 'display_name' not in extra_data_functions:
            extra_data_functions['display_name'] = lambda entity_name, entity_data: self.localize(entity_name)
        entities = {}
        class_attributes = inspect.get_annotations(entity_class)
        for name, data in self.parser.parse_folder_as_one_file(folder):
            entity_values = {}
            for key, func in extra_data_functions.items():
                entity_values[key] = func(name, data)
            for k, v in data:
                if k in transform_value_functions:
                    entity_values[k] = transform_value_functions[k](v)
                elif k in class_attributes and k not in entity_values:
                    entity_values[k] = v
            entities[name] = entity_class(name, **entity_values)
        return entities

    def parse_advanced_entities(self, folder: str, entity_class: Type[AE],
                                extra_data_functions: dict[str, Callable[[str, Tree], any]] = None,
                                transform_value_functions: dict[str, Callable[[any], any]] = None
                                ) -> dict[str, AE]:
        """parse a folder into objects which are subclasses of AdvancedEntity

        See parse_nameable_entities() for a description of the arguments and return value

        This method adds parsing of icon/texture, description(from the _desc localization),
        required_technologies (from the unlocking_technologies section) and modifiers (from the modifier section)


        """
        if extra_data_functions is None:
            extra_data_functions = {}
        if 'icon' not in extra_data_functions:
            extra_data_functions['icon'] = self.parse_icon
        if 'description' not in extra_data_functions:
            extra_data_functions['description'] = lambda name, data: self.localize(name + '_desc')
        if 'required_technologies' not in extra_data_functions:
            extra_data_functions['required_technologies'] = self.parse_technologies_section
        if 'modifiers' not in extra_data_functions:
            extra_data_functions['modifiers'] = self.parse_modifier_section
        return self.parse_nameable_entities(folder, entity_class, extra_data_functions=extra_data_functions,
                                            transform_value_functions=transform_value_functions)

    @cached_property
    def formatter(self):
        from vic3.text_formatter import Vic3WikiTextFormatter
        return Vic3WikiTextFormatter()

    @cached_property
    def defines(self):
        return self.parser.parse_folder_as_one_file('common/defines').merge_duplicate_keys()

    @cached_property
    def script_values(self):
        return self.parser.parse_folder_as_one_file('common/script_values').merge_duplicate_keys()

    @cached_property
    def countries(self):
        """returns a dictionary. keys are tags and values are Country objects."""
        countries = {}
        for file, data in self.parser.parse_files('common/country_definitions/*.txt'):
            for tag, country_data in data:
                if 'capital' in country_data:
                    capital_state = self.states[country_data['capital']]
                else:
                    capital_state = None
                countries[tag] = Country(tag, self.localize(tag), PdxColor.new_from_parser_obj(country_data['color']),
                                         country_type=country_data['country_type'], tier=country_data['tier'],
                                         capital_state=capital_state,
                                         cultures=country_data['cultures'])
        return countries

    @cached_property
    def existing_tags(self):
        """returns a set of tags which exist at the start of the game"""
        tags = set()
        for file, data in self.parser.parse_files('common/history/states/*'):
            for state, state_data in data['STATES']:
                for create_section in state_data.find_all('create_state'):
                    tags.add(create_section['country'].split(':')[1])
        return tags

    @cached_property
    def formable_tags(self):
        """returns a set of tags which can be formed"""
        tags = set()
        for file, data in self.parser.parse_files('common/country_formation/*'):
            a = data.dictionary.keys()
            tags.update(a)
        return tags

    @cached_property
    def releasable_tags(self):
        """returns a set of tags which can be released"""
        tags = set()
        for file, data in self.parser.parse_files('common/country_creation/*'):
            a = data.dictionary.keys()
            tags.update(a)
        return tags

    @cached_property
    def event_releasable_tags(self):
        """tags which get created by create_country"""
        tags = set()
        for file, data in self.parser.parse_files('events/**/*.txt'):
            for create_country_section in data.find_all_recursively('create_country'):
                tags.add(create_country_section['tag'])
        return tags

    @cached_property
    def event_formed_tags(self):
        """tags which get formed with change_tag"""
        tags = set()
        for file, data in self.parser.parse_files('events/**/*.txt'):
            for tag in data.find_all_recursively('change_tag'):
                tags.add(tag)
        return tags

    @cached_property
    def dynamic_country_names(self) -> dict[str, list[str]]:
        dynamic_names = {}
        for tag, dynamic_names_sections in self.parser.parse_folder_as_one_file('common/dynamic_country_names'):
            dynamic_names[tag] = []
            for section in dynamic_names_sections.find_all('dynamic_country_name'):
                if 'is_revolutionary' not in section or not section['is_revolutionary']:
                    dynamic_names[tag].append(self.localize(section['name']))
        return dynamic_names

    def _get_state_resources(self, name, state_data: Tree) -> dict[str, StateResource]:
        resources = {}
        if 'arable_resources' in state_data:
            for arable_resource in state_data['arable_resources']:
                resources[arable_resource] = StateResource(arable_resource, state_data['arable_land'], is_arable=True)
        if 'capped_resources' in state_data:
            for capped_resource, amount in state_data['capped_resources']:
                resources[capped_resource] = StateResource(capped_resource, amount, is_capped=True)
        for resource in state_data.find_all('resource'):
            resources[resource['type']] = StateResource(resource['type'],
                                                        amount=resource.get_or_default('discovered_amount', 0),
                                                        undiscovered_amount=resource.get_or_default(
                                                            'undiscovered_amount', 0))
        return resources

    @cached_property
    def states(self) -> dict[str, State]:
        """returns a dictionary. keys are STATE_ strings and values are State objects."""
        owners = {}
        homelands = {}
        for file, history_data in self.parser.parse_files('common/history/states/*.txt'):
            for name, state_data in history_data['STATES']:
                name_without_prefix = name.removeprefix('s:')
                owners[name_without_prefix] = [create_data['country'].removeprefix('c:') for create_data in
                                               state_data.find_all('create_state')]
                homelands[name_without_prefix] = [culture for culture in state_data.find_all('add_homeland')]

        return self.parse_nameable_entities('map_data/state_regions', State, extra_data_functions={
            'resources': self._get_state_resources,
            'owners': lambda name, data: owners[name] if name in owners else [],
            'homelands': lambda name, data: homelands[name] if name in homelands else [],
        }, transform_value_functions={
            'traits': lambda trait_list: [self.state_traits[trait] for trait in trait_list]
        })

    @cached_property
    def strategic_regions(self) -> dict[str, StrategicRegion]:
        """returns a dictionary. keys are region_ strings and values are StrategicRegion objects."""
        regions = {}
        for file, data in self.parser.parse_files('common/strategic_regions/*.txt'):
            for name, region_data in data:
                regions[name] = StrategicRegion(name, self.localize(name),
                                                states=[self.states[state_name] for state_name in region_data['states']],
                                                is_water=(file.name == 'water_strategic_regions.txt'))
        return regions

    @cached_property
    def state_to_strategic_region_map(self) -> dict[str, StrategicRegion]:
        mapping = {}
        for region in self.strategic_regions.values():
            for state in region.states:
                mapping[state.name] = region
        return mapping

    @cached_property
    def state_population(self) -> dict[str, int]:
        state_populations = {}
        for name_with_s, state in self.parser.parse_folder_as_one_file('common/history/pops', overwrite_duplicate_toplevel_keys=False)['POPS']:
            state_name = name_with_s.removeprefix('s:')
            state_populations[state_name] = 0
            for region_state_name, region_state in state:
                for create_pop in region_state.find_all('create_pop'):
                    state_populations[state_name] += create_pop['size']
        return state_populations

    @cached_property
    def modifier_types(self) -> dict[str, ModifierType]:
        return self.parse_nameable_entities('common/modifier_types', ModifierType)

    def get_modifier_type_or_default(self, modifier_name) -> ModifierType:
        if modifier_name in self.modifier_types:
            return self.modifier_types[modifier_name]
        else:
            # print(f'Warning: use default for unknown modifier "{modifier_name}"', file=sys.stderr)
            modifier_type = ModifierType(modifier_name, self.localize(modifier_name))
            if 'mortality' in modifier_name:
                modifier_type.good = False
                modifier_type.percent = True
            self.modifier_types[modifier_name] = modifier_type
            return modifier_type

    def parse_icon(self, name, data, possible_icon_keys: list[str] = None):
        if possible_icon_keys is None:
            possible_icon_keys = ['icon', 'texture']
        for icon_key in possible_icon_keys:
            if icon_key in data:
                return data[icon_key]
        return ''

    def parse_technologies_section(self, name, data, section_name='unlocking_technologies') -> list[Technology]:
        if section_name not in data:
            return []
        section = data[section_name]
        if not isinstance(section, list):
            raise Exception('Unsupported {} section {}'.format(section_name, section))

        return [self.technologies[tech_name] for tech_name in section]

    def _parse_modifier_data(self, data: Tree):
        return [Modifier(mod_name, self.localize('modifier_' + mod_name),
                         modifier_type=self.get_modifier_type_or_default(mod_name), value=mod_value)
                for mod_name, mod_value in data]

    def parse_modifier_section(self, name, data) -> list[Modifier]:
        if 'modifier' not in data:
            return []
        else:
            return self._parse_modifier_data(data['modifier'])

    @cached_property
    def named_modifiers(self) -> dict[str, NamedModifier]:
        return self.parse_advanced_entities('common/modifiers', NamedModifier, extra_data_functions={
            'modifiers': lambda name, data: self._parse_modifier_data(Tree({name: value for name, value in data if name != 'icon'}))
        })

    @cached_property
    def laws(self) -> dict[str, Law]:
        law_groups = {}
        for lawgroup_name, lawgroup_data in self.parser.parse_folder_as_one_file('common/law_groups'):
            law_groups[lawgroup_name] = LawGroup(lawgroup_name, self.localize(lawgroup_name),
                                                 lawgroup_data['law_group_category'])

        return self.parse_advanced_entities('common/laws', Law, transform_value_functions={
            'group': lambda group_name: law_groups[group_name]})

    def _get_monument_location(self, name, data):
        if 'possible' in data:
            state_name = data['possible']['error_check']['this']['state_region'].replace('s:', '')
            if state_name in self.states:
                return self.states[state_name]
        else:
            return None

    @cached_property
    def buildings(self) -> dict[str, Building]:
        all_buildings = self.parse_advanced_entities('common/buildings', Building,
                                                     transform_value_functions={
                                                         'building_group': lambda building_group:
                                                         self.building_groups[building_group],
                                                         'required_construction': lambda required_construction:
                                                         self.script_values[required_construction],
                                                     },
                                                     extra_data_functions={
                                                         'location': self._get_monument_location
                                                     })

        # bg_monuments_hidden are not actual buildings. They only seem to be used to display them on the map
        return {name: building for name, building in all_buildings.items() if building.building_group.name != 'bg_monuments_hidden'}

    @cached_property
    def building_groups(self) -> dict[str, BuildingGroup]:
        BuildingGroup.hiring_rate = self.defines['NEconomy']['HIRING_RATE']
        BuildingGroup.proportionality_limit = self.defines['NEconomy']['EMPLOYMENT_PROPORTIONALITY_LIMIT']
        building_groups = {}
        for name, data in self.parser.parse_folder_as_one_file('common/building_groups'):
            entity_values = {}
            for k, v in data:
                if k in ['category', 'always_possible', 'economy_of_scale', 'is_subsistence',
                         'auto_place_buildings', 'capped_by_resources',
                         'discoverable_resource', 'depletable_resource', 'can_use_slaves', 'land_usage',
                         'cash_reserves_max', 'stateregion_max_level',
                         'urbanization', 'hiring_rate', 'proportionality_limit',
                         'hires_unemployed_only', 'infrastructure_usage_per_level', 'fired_pops_become_radical',
                         'pays_taxes', 'is_government_funded', 'created_by_trade_routes', 'subsidized', 'is_military',
                         'default_building']:
                    entity_values[k] = v
                elif k == 'parent_group':
                    entity_values['parent_group'] = building_groups[v]
                elif k in ['lens', 'inheritable_construction', 'should_auto_expand']:
                    pass
                else:
                    raise Exception('Unsupported key {} when parsing BuildingGroup "{}"'.format(k, name))
            building_groups[name] = BuildingGroup(name, self.localize(name), **entity_values)

        return building_groups

    def _parse_pm_modifiers(self, modifier_section: Tree):
        result = {}
        for scaling_type, modifiers in modifier_section:
            if scaling_type not in ['workforce_scaled', 'level_scaled', 'throughput_scaled', 'unscaled']:
                raise Exception('Unknow scaling "{}"'.format(scaling_type))
            result[scaling_type] = self._parse_modifier_data(modifiers)
        return result

    @cached_property
    def production_methods(self) -> dict[str, ProductionMethod]:
        production_methods = self.parse_advanced_entities('common/production_methods', ProductionMethod, transform_value_functions={
            'building_modifiers': self._parse_pm_modifiers,
            'country_modifiers': self._parse_pm_modifiers,
            'state_modifiers': self._parse_pm_modifiers,
            'timed_modifiers': lambda modifier_list: [self.named_modifiers[modifier] for modifier in modifier_list],
            'disallowing_laws': lambda law_list: [self.laws[law] for law in law_list],
            'unlocking_laws': lambda law_list: [self.laws[law] for law in law_list],
        })
        del production_methods['pm_dummy']
        for pm in production_methods.values():
            pm.display_name = self.formatter.resolve_nested_localizations(pm.display_name)
            if len(pm.unlocking_production_methods) > 0:
                pm.unlocking_production_methods = [production_methods[pm_name] for pm_name in pm.unlocking_production_methods]
        return production_methods

    @cached_property
    def production_method_groups(self):
        return self.parse_advanced_entities('common/production_method_groups', ProductionMethodGroup)

    @cached_property
    def technologies(self) -> dict[str, Technology]:
        entities = {}
        prerequisites = {}
        for name, data in self.parser.parse_folder_as_one_file('common/technology/technologies'):
            if 'unlocking_technologies' in data:
                # has to be processed later, because the prerequisites can come later in the file
                prerequisites[name] = data['unlocking_technologies']

            entities[name] = Technology(name, self.localize(name),
                                        description=self.localize(name + '_desc'),
                                        icon=data['texture'],
                                        category=data['category'],
                                        required_technologies=[],  # filled later
                                        era=int(data['era'].replace('era_', '')),
                                        modifiers=self.parse_modifier_section(name, data),
                                        )

        for name, required_techs in prerequisites.items():
            entities[name].required_technologies = [entities[required_tech] for required_tech in required_techs]
        return entities

    @cached_property
    def technology_unlocks(self) -> dict[str, list[AE]]:
        unlocks = {tech_name: [] for tech_name in self.technologies.keys()}
        entity_dict_with_possible_tech_requirements = [self.buildings, self.laws, self.production_methods, self.decrees, self.diplomatic_actions, self.parties, self.state_traits]
        for entity_dict in entity_dict_with_possible_tech_requirements:
            for entity in entity_dict.values():
                for tech in entity.required_technologies:
                    unlocks[tech.name].append(entity)
        return unlocks

    @cached_property
    def state_traits(self) -> dict[str, StateTrait]:
        return self.parse_advanced_entities('common/state_traits', StateTrait, extra_data_functions={
            'disabling_technologies': lambda name, data: self.parse_technologies_section('', data, 'disabling_technologies'),
            'required_techs_for_colonization': lambda name, data: self.parse_technologies_section('', data, 'required_techs_for_colonization')
        })

    @cached_property
    def decrees(self) -> dict[str, Decree]:
        return self.parse_advanced_entities('common/decrees', Decree, transform_value_functions={
            'unlocking_laws': lambda law_list: [self.laws[law] for law in law_list]
        })

    @cached_property
    def diplomatic_actions(self) -> dict[str, DiplomaticAction]:
        return self.parse_advanced_entities('common/diplomatic_actions', DiplomaticAction)

    @cached_property
    def parties(self) -> dict[str, Party]:
        parties = {}
        for name, data in self.parser.parse_folder_as_one_file('common/parties'):
            parties[name] = Party(name=name,
                                  display_name=self.localize(data['name']['first_valid']['triggered_desc'][-1]['desc']),
                                  description=self.localize(name + '_desc'),
                                  icon=data['icon']['default'],
                                  required_technologies=self.parse_technologies_section(name, data)
                                  )
        return parties

    @cached_property
    def interest_groups(self) -> dict[str, InterestGroup]:
        return self.parse_advanced_entities('common/interest_groups', InterestGroup)

    @cached_property
    def pop_types(self) -> dict[str, PopType]:
        return self.parse_advanced_entities('common/pop_types', PopType, extra_data_functions={
            'display_name_without_icon': lambda name, data: self.localize(name + '_no_icon')
        })

    @cached_property
    def achievements(self) -> dict[str, Achievement]:
        return self.parse_advanced_entities('common/achievements', Achievement, extra_data_functions={
            'display_name': lambda name, data: self.localize(f'ACHIEVEMENT_{name}'),
            'description': lambda name, data: self.localize(f'ACHIEVEMENT_DESC_{name}')
        })
