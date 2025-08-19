from typing import TypeVar, Type, Callable, Any

from PyHelpersForPDXWikis.localsettings import VIC3DIR
from common.jomini_parser import JominiParser
from common.paradox_parser import QuestionmarkEqualsWorkaround, ParsingWorkaround
from vic3.vic3lib import *
from common.paradox_lib import AE

Vic3AE = TypeVar('Vic3AE', bound=Vic3AdvancedEntity)


class Vic3Parser(JominiParser):
    """Parses Victoria 3 game data into objects of the vic3lib module.

    This object should not be constructed directly, instead it should be accessed as vic3game.parser so that there
    is only one instance which can cache the data.

    The data can be accessed as properties of this object. They are cached_properties so that the parsing is only done
    once.

    parse_advanced_entities() and parse_advanced_entities() can be used to easily add parsing for new entities.
    """

    # allows the overriding of localization strings
    localizationOverrides = {'recognized': 'Recognized', # there doesn't seem to be a localization for this
                             'GNI': 'Guarani (GNI)',  # there are two tags called Guarani: GNI and GRI
                             }

    def __init__(self):
        super().__init__(VIC3DIR / 'game')
        self.localization_folder_iterator = (VIC3DIR / 'game' / 'localization' / 'english').glob('**/*_l_english.yml')

    def parse_dlc_from_conditions(self, conditions: Tree):
        feature_dlc_map = {
            'agitators': 'Voice of the People',
            'exiles': 'Voice of the People',
            'voice_of_the_people_content': 'Voice of the People',
            'voice_of_the_people_preorder': 'Voice of the People preorder',
            'rp1_content': 'Colossus of the South',
            'ep1_content': 'Sphere of Influence',
            'ep1_cosmetics': 'Sphere of Influence',
            'foreign_investment': 'Sphere of Influence',
            'power_bloc_features': 'Sphere of Influence',
        }
        dlcs = []
        for key, value in conditions:
            if key == 'has_dlc_feature':
                dlcs.append(feature_dlc_map[value])
            elif key == 'has_v2_soundtrack_dlc_trigger' and value == 'yes':
                dlcs.append('Victoria 2 Remastered Soundtrack')
            elif key == 'has_american_buildings_dlc_trigger' and value == 'yes':
                dlcs.append('American Buildings Pack')
            elif key == 'has_mp1_soundtrack_dlc_trigger' and value == 'yes':
                dlcs.append('Melodies for the Masse')
            elif key == 'has_agitators_cosmetics_dlc_trigger' and value == 'yes':
                dlcs.append('Voice of the People')
            else:
                raise Exception(f'unknown condition {key}: {value}')
        if len(dlcs) > 1:
            raise Exception(f'more than one DLC is not supported: {dlcs}')
        return dlcs[0]

    def parse_advanced_entities(self, folder: str, entity_class: Type[AE], extra_data_functions: dict[str, Callable[[str, Tree], Any]] = None,
                                transform_value_functions: dict[str, Callable[[Any], Any]] = None,
                                localization_prefix: str = '',
                                allow_empty_entities=False,
                                parsing_workarounds: list[ParsingWorkaround] = None,) -> dict[str, AE]:
        """parse a folder into objects which are subclasses of AdvancedEntity

        See parse_nameable_entities() for a description of the arguments and return value

        This method adds parsing of icon/texture, description(from the _desc localization),
        required_technologies (from the unlocking_technologies section) and modifiers (from the modifier section)


        """
        if extra_data_functions is None:
            extra_data_functions = {}
        if 'required_technologies' not in extra_data_functions:
            extra_data_functions['required_technologies'] = self.parse_technologies_section
        return super().parse_advanced_entities(folder, entity_class, extra_data_functions, transform_value_functions, localization_prefix, allow_empty_entities, parsing_workarounds)

    @cached_property
    def formatter(self):
        from vic3.text_formatter import Vic3WikiTextFormatter
        return Vic3WikiTextFormatter()

    @cached_property
    def defines(self):
        return self.parser.parse_folder_as_one_file('common/defines').merge_duplicate_keys()

    @cached_property
    def countries(self) -> dict[str, Country]:
        """returns a dictionary. keys are tags and values are Country objects."""
        countries = {}
        for file, data in self.parser.parse_files('common/country_definitions/*.txt'):
            for tag, country_data in data:
                if 'dynamic_country_definition' in country_data and country_data['dynamic_country_definition']:  # ignore dynamic countries
                    continue
                if 'capital' in country_data:
                    capital_state = self.states[country_data['capital']]
                else:
                    capital_state = None
                countries[tag] = Country(tag, self.localize(tag), self.parse_color_value(country_data['color']),
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
            # sometimes dynamic_names_sections is a list, because there are multiple sections for the same tag. To make
            # parsing easier, we always use a list
            if not isinstance(dynamic_names_sections, list):
                dynamic_names_sections = [dynamic_names_sections]
            for tag_section in dynamic_names_sections:
                for section in tag_section.find_all('dynamic_country_name'):
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

    def _get_state_trait_list(self, trait_list) -> list[StateTrait]:
        """trait_list can be a list of the trait keys or a list of lists with trait keys"""
        result = []
        for trait_or_list in trait_list:
            if not isinstance(trait_or_list, list):
                trait_or_list = [trait_or_list]
            for trait_str in trait_or_list:
                result.append(self.state_traits[trait_str])
        return result

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
            'traits': self._get_state_trait_list
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

    def parse_technologies_section(self, name, data, section_name='unlocking_technologies') -> list[Technology]:
        if section_name not in data:
            return []
        section = data[section_name]
        if not isinstance(section, list):
            raise Exception('Unsupported {} section {}'.format(section_name, section))

        return [self.technologies[tech_name] for tech_name in section]

    @cached_property
    def modifier_types(self) -> dict[str, Vic3ModifierType]:
        return self.parse_nameable_entities('common/modifier_type_definitions', Vic3ModifierType, extra_data_functions={'parser': lambda name, data: self})

    @cached_property
    def named_modifiers(self) -> dict[str, NamedModifier]:
        return self.parse_advanced_entities('common/static_modifiers', NamedModifier, extra_data_functions={
            'modifier': lambda name, data: self._parse_modifier_data(Tree({name: value for name, value in data if name != 'icon'}))
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
        if 'potential' not in data:
            return None
        try:
            conditions = data['potential']['error_check']['this']
        except (KeyError, TypeError):  # new format?
            conditions = data['potential']
        try:
            state_name = None
            if isinstance(conditions, list):
                for condition in conditions:
                    if 'state_region' in condition:
                        state_name = condition['state_region'].replace('s:', '')
            else:
                state_name = conditions['state_region'].replace('s:', '')
            if state_name is not None and state_name in self.states:
                return self.states[state_name]
        except KeyError:  # no state_region region check in the trigger, so it isn't a monument and we can ignore it
            return None
        return None

    @cached_property
    def buildings(self) -> dict[str, Building]:
        all_buildings = self.parse_advanced_entities('common/buildings', Building,
                                                     transform_value_functions={
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
        BuildingGroup.min_hiring_rate = self.defines['NEconomy']['DEFAULT_MIN_HIRING_RATE']
        BuildingGroup.max_hiring_rate = self.defines['NEconomy']['DEFAULT_MAX_HIRING_RATE']
        BuildingGroup.proportionality_limit = self.defines['NEconomy']['EMPLOYMENT_PROPORTIONALITY_LIMIT']
        building_groups = {}
        unparsed_bgs = [(name, data) for name, data in self.parser.parse_folder_as_one_file('common/building_groups')]
        while len(unparsed_bgs) > 0:
            name, data = unparsed_bgs.pop(0)
            if 'parent_group' in data and data['parent_group'] not in building_groups:
                # delay parsing till some time after the parent group
                unparsed_bgs.append((name, data))
            else:
                building_groups[name] = self._parse_building_group(building_groups, data, name)

        return building_groups

    def _parse_building_group(self, parsed_building_groups: dict[str, BuildingGroup], data, name: str) -> BuildingGroup:
        entity_values = {}
        for k, v in data:
            if k in ['category', 'always_possible', 'economy_of_scale', 'is_subsistence',
                     'auto_place_buildings', 'capped_by_resources',
                     'discoverable_resource', 'depletable_resource', 'can_use_slaves', 'land_usage',
                     'cash_reserves_max', 'stateregion_max_level',
                     'urbanization', 'min_hiring_rate', 'max_hiring_rate', 'proportionality_limit',
                     'hires_unemployed_only', 'infrastructure_usage_per_level', 'fired_pops_become_radical',
                     'pays_taxes', 'is_government_funded', 'created_by_trade_routes', 'subsidized', 'is_military',
                     'default_building', 'ignores_productivity_when_hiring',
                     'min_productivity_to_hire', 'owns_other_buildings', 'always_self_owning', 'has_trade_revenue', 'company_headquarter', 'regional_company_headquarter',
                     'construction_efficiency_modifier']:
                entity_values[k] = v
            elif k == 'parent_group':
                entity_values['parent_group'] = parsed_building_groups[v]
            elif k in ['lens', 'inheritable_construction', 'should_auto_expand', 'economy_of_scale_ai_factor', 'foreign_investment_ai_factor',
                       'is_shown_in_outliner']:
                pass
            else:
                raise Exception('Unsupported key {} when parsing BuildingGroup "{}"'.format(k, name))
        group = BuildingGroup(name, self.localize(name), **entity_values)
        return group

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
                                        modifier=self.parse_modifier_section(name, data),
                                        )

        for name, required_techs in prerequisites.items():
            entities[name].required_technologies = [entities[required_tech] for required_tech in required_techs]
        return entities

    @cached_property
    def technology_unlocks(self) -> dict[str, list[Vic3AE]]:
        unlocks = {tech_name: [] for tech_name in self.technologies.keys()}
        entity_dict_with_possible_tech_requirements = [self.buildings, self.laws, self.production_methods, self.decrees, self.diplomatic_actions, self.parties, self.state_traits, self.ideologies]
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
        return self.parse_advanced_entities('common/decrees', Decree)

    @cached_property
    def diplomatic_actions(self) -> dict[str, DiplomaticAction]:
        return self.parse_advanced_entities('common/diplomatic_actions', DiplomaticAction)

    @cached_property
    def parties(self) -> dict[str, Party]:
        parties = {}
        for name, data in self.parser.parse_folder_as_one_file('common/parties'):
            parties[name] = Party(name=name,
                                  display_name=self.localize(
                                      data['name']['first_valid']['triggered_desc'][-1]['desc']
                                      if 'first_valid' in data['name']
                                      else data['name']['desc']
                                  ),
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

    def _character_end(self, name, data):
        end = '0'
        for usage in ['agitator_usage', 'commander_usage', 'interest_group_leader_usage']:
            if usage in data:
                if 'latest_usage_date' in data[usage] and str(data[usage]['latest_usage_date']) > end:
                    end = str(data[usage]['latest_usage_date'])
        if end == '0':
            end = None
        return end

    def _character_start(self, name, data):
        start = '0'
        for usage in ['agitator_usage', 'commander_usage', 'interest_group_leader_usage']:
            if usage in data:
                if 'earliest_usage_date' in data[usage] and (start == '0' or str(data[usage]['earliest_usage_date']) < start):
                    start = str(data[usage]['earliest_usage_date'])
        if start == '0':
            start = None
        return start


    @cached_property
    def characters(self) -> dict[str, Character]:
        transform_value_functions = {
            'first_name': self.localize,
            'last_name': self.localize,
            'country': lambda tag: self.countries[tag.removeprefix('c:')],
            'interest_group': lambda ig: self.interest_groups.get(ig),
            'ideology': self.localize,
            'culture': lambda c: self.localize((c if not isinstance(c, list) else c[-1]).removeprefix('cu:')),
            'religion': lambda c: self.localize(c.removeprefix('rel:')),
            'traits': lambda traits: [self.localize(trait) for trait in traits],
        }
        template_chars = self.parse_nameable_entities(f'common/character_templates/', Character,
                                                      transform_value_functions=transform_value_functions,
                                                      extra_data_functions={'is_template': lambda name, data: True,
                                                                            'start': self._character_start,
                                                                            'end': self._character_end,
                                                                            })
        class RandomListWorkaround(ParsingWorkaround):

            def apply_to_string(self, file_contents: str):
                next_random_list = file_contents.find('random_list')
                while next_random_list != -1:
                    opened_brackets = 0
                    for i, c in enumerate(file_contents[next_random_list:]):
                        if c == '{':
                            opened_brackets += 1
                        elif c== '}':
                            opened_brackets -= 1
                        if opened_brackets == 0 and i > 14:
                            break
                    old_file_contents = file_contents
                    before = file_contents[:next_random_list]
                    after = file_contents[next_random_list + i + 1:]
                    file_contents = before + after
                    next_random_list = file_contents.find('random_list')
                return file_contents

        transform_value_functions['template'] = lambda template: template_chars[template]
        chars = self.parse_nameable_entities(f'common/history/characters/', Character,
                                             parsing_workarounds=[QuestionmarkEqualsWorkaround(), RandomListWorkaround()],
                                             entity_level=2, level_headings_keys={'country': 1},
                                             transform_value_functions=transform_value_functions,
                                             extra_data_functions={
                        # 'display_name': lambda name, data:
                        #     self.localize(data["first_name"]) + ' ' + self.localize(data["last_name"]) if 'first_name' in data else data['template'],
                        'name': lambda name, data:
                            data['first_name'] + '_' + data['last_name'] if 'first_name' in data else template_chars[data['template']].first_name + '_' + template_chars[data['template']].last_name,

                    },
                                             )

        # remove used templates
        templates_to_remove = [char.template.name for char in chars.values() if char.template]
        # and special templates
        templates_to_remove.append('default')
        #return template_chars | chars
        # filter out templated characters
        return {name: char for name, char in (template_chars | chars).items() if name not in templates_to_remove}

    def _parse_technologies_from_ideology_data(self, name, data):
        technologies = []
        if 'possible' in data:
            for tree in data['possible'].find_all('owner'):
                for techname in tree.find_all('has_technology_researched'):
                    technologies.append(self.technologies[techname])
        return technologies

    @cached_property
    def ideologies(self) -> dict[str, Ideology]:
        return self.parse_advanced_entities('common/ideologies', Ideology, extra_data_functions={
            'law_approvals': lambda name, data: {law: approval for k, v in data if k.startswith('lawgroup_') for law, approval in v},
            'required_technologies': self._parse_technologies_from_ideology_data,
        })

    @cached_property
    def principle_groups(self) -> dict[str, PrincipleGroup]:
        return self.parse_advanced_entities('common/power_bloc_principle_groups', PrincipleGroup)

    @cached_property
    def _principle_name_to_group_map(self) -> dict[str, PrincipleGroup]:
        return {principle: principle_group for principle_group in self.principle_groups.values() for principle in principle_group.levels}

    @cached_property
    def _principle_name_to_level_map(self) -> dict[str, int]:
        return {principle: level for principle_group in self.principle_groups.values() for level, principle in enumerate(principle_group.levels, start=1)}

    @cached_property
    def principles(self) -> dict[str, Principle]:
        return self.parse_advanced_entities('common/power_bloc_principles', Principle, extra_data_functions={
            'display_name': lambda name, data: f'{self._principle_name_to_group_map[name].display_name}{self._principle_name_to_level_map[name]}',
            'group': lambda name, data: self._principle_name_to_group_map[name],
            'level': lambda name, data: self._principle_name_to_level_map[name],
        })

    @cached_property
    def religions(self) -> dict[str, Religion]:
        return self.parse_advanced_entities('common/religions', Religion)
