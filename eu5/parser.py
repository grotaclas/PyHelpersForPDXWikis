import copy
import pprint
import uuid
from collections.abc import MutableMapping, Iterable
from functools import reduce
from typing import Callable, Type

from PyHelpersForPDXWikis.localsettings import EU5DIR
from common.cache import disk_cache
from common.file_generator import FileGenerator
from eu5.eu5lib import *
from common.jomini_parser import JominiParser
from common.paradox_lib import NE, AE, ME
from common.paradox_parser import ParsingWorkaround, ScriptedWorkaround


class Eu5Parser(JominiParser):
    _class_property_map_overrides: dict[Type[NE], str] = {
        Location: 'locations',
        Country: 'countries_including_formables',
        Language: 'languages_including_dialects',
    }

    # allows the overriding of localization strings
    localizationOverrides = {
        # the default is "Trade Embark/Disembark Cost" which is problematic for redirects and filenames, because of the slash
        'MODIFIER_TYPE_NAME_local_trade_embark_disembark_cost_modifier': 'Trade Embark-Disembark Cost',
        'BGP': 'Burgundy (BGP)',
        'MAM': 'Egypt (MAM)'
    }

    def __init__(self, game_installation: Path = EU5DIR, language: str = 'english'):
        super().__init__(game_installation / 'game' )
        self.localization_folder_iterator = (game_installation / 'game' / 'main_menu' / 'localization' / language).glob(f'**/*_l_{language}.yml')

    @cached_property
    def formatter(self):
        from eu5.text_formatter import Eu5WikiTextFormatter
        return Eu5WikiTextFormatter()

    def parse_nameable_entities(self, folder: str, entity_class: Type[NE], extra_data_functions: dict[str, Callable[[str, Tree], Any]] = None,
                                transform_value_functions: dict[str, Callable[[Any], Any]] = None, entity_level: int = 0,
                                level_headings_keys: dict[str, 0] = None, parsing_workarounds: list[ParsingWorkaround] = None, localization_prefix: str = '',
                                allow_empty_entities=False,
                                localization_suffix: str = '',
                                ) -> dict[str, NE]:

        if extra_data_functions is None:
            extra_data_functions = {}
        if 'display_name' not in extra_data_functions:
            extra_data_functions['display_name'] = lambda entity_name, entity_data: self.formatter.strip_formatting(
                self.localize(localization_prefix + entity_name + localization_suffix), strip_newlines=True)
        return super().parse_nameable_entities(folder, entity_class, extra_data_functions, transform_value_functions, entity_level, level_headings_keys,
                                               parsing_workarounds, localization_prefix, allow_empty_entities, localization_suffix)

    def parse_advanced_entities(self, folder: str|Tree, entity_class: Type[AE], extra_data_functions: dict[str, Callable[[str, Tree], Any]] = None,
                                transform_value_functions: dict[str, Callable[[Any], Any]] = None, localization_prefix: str = '', allow_empty_entities=False,
                                parsing_workarounds: list[ParsingWorkaround] = None,
                                description_localization_prefix: str = None,
                                description_localization_suffix: str = '_desc',
                                localization_suffix: str = '',
                                ) -> dict[str, AE]:
        if extra_data_functions is None:
            extra_data_functions = {}
        if '_unformatted_description' not in extra_data_functions and 'description' not in extra_data_functions:
            if description_localization_prefix is None:
                description_localization_prefix = localization_prefix
            extra_data_functions['_unformatted_description'] = lambda name, data: self.localize(f'{description_localization_prefix}{name}{description_localization_suffix}', default='')
        if '_formatter' not in extra_data_functions:
            extra_data_functions['_formatter'] = lambda name, data: self.formatter
        return self.parse_nameable_entities(folder, entity_class, extra_data_functions, transform_value_functions, localization_prefix=localization_prefix, allow_empty_entities=allow_empty_entities, parsing_workarounds=parsing_workarounds, localization_suffix=localization_suffix)

    @cached_property
    def modifier_icons(self) -> Tree:
        return self.parser.parse_folder_as_one_file('main_menu/common/modifier_icons').merge_duplicate_keys()

    @cached_property
    def default_modifier_icon(self) -> str:
        for name, data in self.modifier_icons:
            if data.get_or_default('default', False):
                return data['positive']
        return ''

    @cached_property
    @disk_cache(eu5game, classes_to_cache={Eu5ModifierType})
    def modifier_types(self) -> dict[str, Eu5ModifierType]:
        return self.parse_nameable_entities('main_menu/common/modifier_type_definitions', Eu5ModifierType,
                                            allow_empty_entities=True,
                                            extra_data_functions={
            'parser': lambda name, data: self,
            'icon_file': lambda name, data: self.modifier_icons.get_or_default(name, Tree({})).get_or_default('positive', None),
            'negative_icon_file': lambda name, data: self.modifier_icons.get_or_default(name, Tree({})).get_or_default('negative', None),
        })

    @cached_property
    def named_modifiers(self) -> dict[str, Eu5NamedModifier]:
        return self.parse_advanced_entities('main_menu/common/static_modifiers', Eu5NamedModifier,
                                            localization_prefix='STATIC_MODIFIER_NAME_',
                                            description_localization_prefix='STATIC_MODIFIER_DESC_',
                                            description_localization_suffix='',
                                            extra_data_functions={
                                                'modifier': lambda name, data: self._parse_modifier_data(
                                                    Tree({name: value for name, value in data if name not in ['category', 'decaying', 'game_data']}),
                                                    modifier_class=Eu5Modifier),
                                                'category': lambda name, data: data['game_data']['category'],
                                                'decaying': lambda name, data: data['game_data']['decaying'] if 'decaying' in data['game_data'] else False,
                                            })

    def _parse_modifier_data(self, data: Tree,
                             modifier_class: Type[ME] = Eu5Modifier,
                             excludes: Iterable[str] = ('potential_trigger', 'scale', 'pure_tooltip_entry')
                             ) -> list[ME]:
        """@TODO: parse potential_trigger and scale and pure_tooltip_entry"""
        return super()._parse_modifier_data(data, modifier_class, excludes)

    def parse_modifier_section_from_wiki_section_name(self, wiki_section_name: str) -> list[Eu5Modifier]:
        """
        Can get the modifiers from an arbitrary section which is specified by a dot-separated string which can be used
        as a section name on the wiki
        Args:
            wiki_section_name: dot separated string which specifies the file and section.
            e.g. common.religions.christian.catholic.definition_modifier to get the modifiers
            from the section definition_modifier in catholic in the file common/religions/christian.txt
        """
        if wiki_section_name.startswith('main_menu.'):
            path = self.parser.base_folder
        else:
            path = self.parser.base_folder / 'in_game'
        file_data = None
        outer_section = None
        for section_component in wiki_section_name.split('.'):
            if file_data is None:
                if (path / section_component).exists() and (path / section_component).is_dir():
                    path = path / section_component
                else:
                    path = path / (section_component + '.txt')
                    if not (path.exists() and path.is_file()):
                        raise Exception(f'No file found for "{wiki_section_name}"')
                    file_data = self.parser.parse_file(path.relative_to(self.parser.base_folder))
            else:
                if section_component in file_data:
                    outer_section = file_data
                    file_data = file_data[section_component]
                else:
                    raise Exception(f'Section "{section_component}" not found for "{wiki_section_name}"')

        return self.parse_modifier_section('', outer_section, section_component, Eu5Modifier)

    def resolve_entity_reference(self, entity_class: Type[NE], entity_name):
        if entity_class == ScriptValue:
            if not entity_name:
                return None
            elif not isinstance(entity_name, str):  # will be handled by super class
                return self._parse_script_value(f'inline_script_value_{uuid.uuid1()}', entity_name)

        return super().resolve_entity_reference(entity_class, entity_name)

    def _parse_goods_demand(self, value):
        if isinstance(value, str):
            if value in self.goods_demand:
                return self.goods_demand[value]
            elif value in self.production_methods:
                FileGenerator.warn(f'Expected goods demand, but got production method "{value}"')
                return self.production_methods[value]
        elif isinstance(value, list):
            FileGenerator.warn(f'Expected goods demand, but got multiple entries "{",".join(value)}"')
            return self._parse_goods_demand(value[0])
        FileGenerator.warn(f'Expected goods demand, but got type "{type(value)}"')
        return value

    @cached_property
    def advances(self) -> dict[str, Advance]:
        return self.parse_advanced_entities('in_game/common/advances', Advance,
                                            extra_data_functions={
                                                'age_specialization': lambda name, data: data['for'] if 'for' in data else None,
                                                'modifiers': lambda name, data: self._parse_modifier_data(
                                                    data,
                                                    excludes=list(Advance.all_annotations().keys()) + ['requires', 'for']),
                                            },
                                            transform_value_functions={
                                                # so that the parser passes the value through even though requires is not an attribute
                                                'requires': lambda c: c,
                                                'unlock_production_method': lambda pm_strings: [
                                                    self.all_production_methods[pm]
                                                    for pm in (
                                                        pm_strings if not isinstance(pm_strings, str)
                                                        else [pm_strings])],
                                            },
                                            )

    @cached_property
    def age(self) -> dict[str, Age]:
        return self.parse_advanced_entities('in_game/common/age', Age, extra_data_functions={
            'long_name': lambda name, data: self.formatter.strip_formatting(self.localize(f'age_format_{name}'))
        })

    @cached_property
    def building_category(self) -> dict[str, BuildingCategory]:
            return self.parse_advanced_entities('in_game/common/building_categories', BuildingCategory, allow_empty_entities=True)

    @cached_property
    def buildings(self) -> dict[str, Building]:
        buildings = self.parse_advanced_entities('in_game/common/building_types', Building,
                                            transform_value_functions={
                                                'build_time': lambda value: self.script_values[value] if isinstance(value, str) else value,
                                                'construction_demand': self._parse_goods_demand,
                                                'employment_size': lambda value: (self.script_values[value] if isinstance(value, str) else value) * 1000,
                                                'destroy_price': lambda value: self.prices[value] if isinstance(value, str) else value,
                                                'obsolete': lambda value: [value] if isinstance(value, str) else value,
                                                'price': lambda value: self.prices[value] if isinstance(value, str) else value,
                                                'pop_size_created': lambda value: (self.script_values[value] if isinstance(value, str) else value) * 1000,
                                                'possible_production_methods': lambda value: [self.production_methods[pm] if isinstance(pm, str) else pm for pm in value],
                                                'unique_production_methods': lambda value: [list(self._parse_production_methods(tree).values()) for tree in (value if isinstance(value, list) else [value])],
                                            })
        # replace str references in obsolete by references to the building objects
        for building in list(buildings.values()):
            building.obsolete = [buildings[building_name] for building_name in building.obsolete]

        return buildings

    @cached_property
    def climates(self) -> dict[str, Climate]:
        return self.parse_advanced_entities('in_game/common/climates', Climate)

    def _parse_province_data(self, area: str, province_data: Tree) -> dict[str, Province]:
        return {
            province: Province(province,
                               self.formatter.strip_formatting(
                                   self.localize(province), strip_newlines=True
                               ),
                               _area = area,
                               locations={location: self.locations[location]
                                          for location in locations}
                               )
            for province, locations in province_data
        }

    @cached_property
    @disk_cache(eu5game, classes_to_cache={Continent, SubContinent, Region, Area, Province})
    def _map_entities(self):
        sub_continents = {}
        regions = {}
        areas = {}
        provinces = {}
        continents = {
            name: Continent(name,
                            self.formatter.strip_formatting(self.localize(name), strip_newlines=True),
                            sub_continents=self._update_and_return_new_elements(
                                sub_continents,
                                self._parse_sub_continents(name, data, regions, areas, provinces)
                            ))
            for name, data in self.parser.parse_file(
                'in_game/map_data/' + self.default_map.get_or_default('setup', 'definitions.txt')
            )
        }
        return continents, sub_continents, regions, areas, provinces

    def _parse_sub_continents(self, continent_name, continent_data, regions, areas, provinces):
        return {
            sub: SubContinent(sub,
                              self.formatter.strip_formatting(self.localize(sub), strip_newlines=True),
                              _continent=continent_name,
                              regions=self._update_and_return_new_elements(
                                  regions,
                                  self._parse_regions(sub, sub_data, areas, provinces)))
            for sub, sub_data in continent_data
        }

    def _parse_regions(self, sub_continent_name, sub_continent_data, areas, provinces):
        return {
            region_name: Region(region_name,
                                self.formatter.strip_formatting(self.localize(region_name), strip_newlines=True),
                                _sub_continent=sub_continent_name,
                                areas=self._update_and_return_new_elements(
                                    areas,
                                    self._parse_areas(region_name, region_data, provinces)
                                ))
            for region_name, region_data in sub_continent_data
        }


    def _parse_areas(self, region_name, region_data, provinces):
        return {
            area_name: Area(area_name,
                            self.formatter.strip_formatting(self.localize(area_name), strip_newlines=True),
                            _region=region_name,
                            provinces=self._update_and_return_new_elements(provinces, self._parse_provinces(area_name, area_data)))
            for area_name, area_data in region_data
        }

    def _parse_provinces(self, area_name, area_data):
        return {
            province_name:
                Province(province_name,
                         self.formatter.strip_formatting(self.localize(province_name), strip_newlines=True),
                         _area=area_name,
                         locations={location: self.locations[location] for
                                    location in
                                    locations}
                         ) for province_name, locations in area_data
        }

    @staticmethod
    def _update_and_return_new_elements(original: dict, new_elements: dict) -> dict:
        original.update(new_elements)
        return new_elements

    @cached_property
    def continents(self):
        return self._map_entities[0]

    @cached_property
    def sub_continents(self) -> dict[str, SubContinent]:
        return self._map_entities[1]

    @cached_property
    def regions(self) -> dict[str, Region]:
        return self._map_entities[2]

    @cached_property
    def areas(self) -> dict[str, Area]:
        return self._map_entities[3]

    @cached_property
    def provinces(self) -> dict[str, Province]:
        return self._map_entities[4]

    @cached_property
    def tag_specific_descriptions(self) -> dict[str, str]:
        tag_to_description = {}
        for custom_loc in self.customizable_localization['country_history'].text.values():
            if not custom_loc.fallback:
                for tag in custom_loc.trigger.find_all_recursively('tag'):
                    tag_to_description[tag] = custom_loc.display_name

        return tag_to_description

    @cached_property
    def country_description_categories(self) -> dict[str, CountryDescriptionCategory]:
        return self.parse_nameable_entities('in_game/common/country_description_categories', CountryDescriptionCategory,
                                            allow_empty_entities=True,
                                            extra_data_functions={
                                                'display_name': lambda name, data: self.formatter.strip_formatting(
                                                    self.localize('country_description_category_name_' + name), strip_newlines=True),
                                                'description': lambda name, data: self.formatter.format_localization_text(
                                                    self.localize('country_description_category_desc_' + name)),
                                            })

    @cached_property
    @disk_cache(eu5game, classes_to_cache={Country})
    def countries(self) -> dict[str, Country]:
        """countries from in_game/setup/countries with additional data from main_menu/setup """

        countries_from_ingame_setup = self.parser.parse_folder_as_one_file('in_game/setup/countries')
        tag: str
        country_data: Tree
        for tag, country_data in countries_from_ingame_setup:
            if tag in self.setup_data['countries']['countries']:
               country_data.update(self.setup_data['countries']['countries'][tag])

        return self.parse_advanced_entities(countries_from_ingame_setup, Country,
                                            transform_value_functions={
                                                'currency_data': lambda currency_data: [
                                                    ResourceValue.create_with_hardcoded_resource(key, value) for key, value in
                                                    currency_data if key in HardcodedResource],
                                                # @TODO: remove this workaround for duplicate description_category sections
                                                'description_category': lambda cat: self.country_description_categories[
                                                    cat if isinstance(cat, str) else cat[0]],
                                            },
                                            extra_data_functions={
                                                # the default rank seems to be county. Pass it as extra data, so that it is set
                                                # in the object instead of in the class, so that it gets cached correctly
                                                'default_rank': lambda name, data: self.country_ranks['rank_county'],
                                            }
        )

    @cached_property
    def countries_including_formables(self): # -> dict[str, Country|FormableCountry]:
        results = self.countries.copy()
        for formable_name, formable_country in self.formable_countries.items():
            if hasattr(formable_country, 'tag') and formable_country.tag not in results:
                results[formable_country.tag] = formable_country
        return results

    @cached_property
    @disk_cache(eu5game)
    def setup_data(self) -> Tree:
        """main_menu/setup including templates"""
        template_data_without_include = {
            filename.stem: self._fix_law_values(data)
            for filename, data in self.parser.parse_files('main_menu/setup/templates/*.txt')
        }
        template_data = {}
        for filename, template in template_data_without_include.items():
            template_data[filename] = self._resolve_includes(template, template_data, template_data_without_include)

        return self._resolve_includes(self._fix_law_values(self.parser.parse_folder_as_one_file('main_menu/setup/start/')),
                                      template_data,
                                      other_templates={},
                                      recursive=True
                                      )

    def _fix_law_value(self, law_value):
        if isinstance(law_value, list):
            law_value = Tree({law_key: law_value
                              for law_tree in law_value
                              for law_key, law_value in law_tree})
        if isinstance(law_value, Tree):
            law_value = self._fix_law_values(law_value)
        return law_value

    def _fix_law_values(self, data: Tree):
        """If there are multiple law sections, the parser turns them into a list of Tree.
         This function merges the trees from that list.
         It goes recursively through the data to fix the sections wherever they are"""
        for key, value in data:
            if key in ['laws', 'government']:
                data[key] = self._fix_law_value(value)
            elif isinstance(value, Tree):
                self._fix_law_values(value)
        return data

    def _resolve_includes(self, data: Tree, templates, other_templates, recursive=False):
        if 'include' in data or recursive:
            new_template = Tree({})
            for key, value in data:
                if key == 'include':
                    if not isinstance(value, list):
                        value = [value]
                    for include_file in value:
                        if include_file in templates:
                            included_data = templates[include_file]
                        else:
                            included_data = other_templates[include_file]
                        new_template.update(copy.deepcopy(included_data))
                elif key in new_template:
                    if isinstance(value, Tree) or isinstance(value, MutableMapping):
                        new_template[key].update(value)
                    elif isinstance(value, list) or isinstance(new_template[key], list):
                        if not isinstance(new_template[key], list):
                            new_template[key] = [new_template[key]]
                        if not isinstance(value, list):
                            value = [value]
                        new_template[key].extend(value)
                    elif value is None and new_template[key] is not None:
                        pass
                    else:
                        new_template[key] = value
                else:
                    if key in ['laws', 'government']:
                        value = self._fix_law_value(value)
                    if isinstance(value, Tree):
                        new_template[key] = self._resolve_includes(value, templates, other_templates, recursive)
                    else:
                        new_template[key] = value

            return new_template
        else:
            return data

    @cached_property
    def culture_groups(self) -> dict[str, CultureGroup]:
        return self.parse_nameable_entities('in_game/common/culture_groups', CultureGroup, allow_empty_entities=True)

    @cached_property
    @disk_cache(eu5game, classes_to_cache={Culture})
    def cultures(self) -> dict[str, Culture]:
        return self.parse_advanced_entities('in_game/common/cultures', Culture, transform_value_functions={
            # @TODO: remove this workaround for duplicate culture_groups sections
            'culture_groups': lambda groups: [self.culture_groups[g] for g2 in groups for g in g2] if len(groups) > 0 and isinstance(groups[0], list) else [self.culture_groups[g] for g in groups]
        })

    @cached_property
    def default_map(self) -> Tree:
        return self.parser.parse_file('in_game/map_data/default.map')


    @cached_property
    def defines(self):
        # TODO: add defines from jomini folder
        class DoubleSlashCommentWorkaround(ParsingWorkaround):
            """removes lines which start with spaces and //
            they are not valid paradox script and cause a debug message when loading, but the defines have them
            """
            replacement_regexes = {r'(?m)^\s*//.*$': ''}

        return self.parser.parse_folder_as_one_file('loading_screen/common/defines', workarounds=[DoubleSlashCommentWorkaround()]).merge_duplicate_keys()

    def get_define(self, define: str):
        """get a define by its game syntax e.g. NGame.START_DATE"""
        result = self.defines
        for part in define.split('.'):
            result = result[part]
        return result

    @cached_property
    def dynasties(self) -> dict[str, Dynasty]:
        """Only scripted dynasties from setup, but not from the dynasty names"""
        return self.parse_advanced_entities(self.setup_data['dynasty_manager'], Dynasty, extra_data_functions={
                                            'display_name': lambda entity_name, entity_data: self.formatter.strip_formatting(
                                                self.localize(entity_data['name']['name']),
                                                strip_newlines=True)
                                            })

    @cached_property
    def dynasty_names(self) -> dict[str, Dynasty|Language]:
        """Includes dynasty names from setup (with their Dynasty)
         and from the languages and dialects(with their Language)"""
        names = {dynasty_name: language
                 for language in self.languages_including_dialects.values()
                 for dynasty_name in language.dynasty_names}
        names.update(self.dynasties)
        return names

    @cached_property
    def earthquakes(self) -> dict[str, Location]:
        """earthquake zone locations from the earthquakes list in game/in_game/map_data/default.map """
        return {name: self.locations[name] for name in self.default_map['earthquakes']}

    @cached_property
    def estates(self) -> dict[str, Estate]:
        return self.parse_advanced_entities('in_game/common/estates', Estate)

    @cached_property
    def estate_privileges(self) -> dict[str, EstatePrivilege]:
        return self.parse_advanced_entities('in_game/common/estate_privileges', EstatePrivilege)

    @cached_property
    def events(self) -> dict[str, Event]:
        return {event_id: event for event_file in self.event_files.values() for event_id, event in event_file.events.items()}

    @cached_property
    def event_files(self) -> dict[str, EventFile]:
        event_files = {}
        for path, filedata in self.parser.parse_files('in_game/events/**/*.txt', [ScriptedWorkaround()]):
            filename = str(path.relative_to(self.parser.base_folder / 'in_game/events' ))
            namespaces = []
            scripted_triggers = {}
            scripted_effects = {}
            unparsed_events = Tree({})
            for k, v in filedata:
                if k == 'namespace':
                    if isinstance(v, list):
                        namespaces.extend(v)
                    else:
                        namespaces.append(v)
                elif k == 'scripted_trigger':
                    scripted_triggers.update(self.parse_advanced_entities(
                        Tree({
                            trigger_data['id']: trigger_data
                            for trigger_data in (
                                v if isinstance(v, list) else [v]
                            )
                        }),
                        ScriptedTrigger
                    ))
                elif k == 'scripted_effect':
                    scripted_effects.update(self.parse_advanced_entities(
                        Tree({
                            effect_data['id']: effect_data
                            for effect_data in (
                                v if isinstance(v, list) else [v]
                            )
                        }),
                        ScriptedEffect
                    ))
                elif '.' in k and k.partition('.')[0] in namespaces:
                    unparsed_events[k] = v
                else:
                    raise Exception(f'Unexpected key {k} when parsing event file {filename}')

            events = self.parse_advanced_entities(unparsed_events, Event,
                                            transform_value_functions={
                                                'option': lambda option: self.parse_advanced_entities(
                                                    Tree({
                                                        option_data['name']: option_data
                                                        for option_data in (
                                                            option if isinstance(option, list) else [option]
                                                        )
                                                    }),
                                                    EventOption
                                                )
                                            })
            event_file = EventFile(filename=filename, namespaces=namespaces,
                                   scripted_triggers=scripted_triggers, scripted_effects=scripted_effects,
                                   events=events)
            for event in events.values():
                event.event_file = event_file
            event_files[filename] = event_file


        return event_files

    @cached_property
    def flag_definitions(self) -> dict[str, FlagDefinitionList]:
        """Includes dummy flag definitions for countries which use the coa which has the same name as their tag"""
        result = {}
        for tag, flag_definitions_data in self.parser.parse_folder_as_one_file('main_menu/common/flag_definitions').merge_duplicate_keys():
            if tag == 'DEFAULT':
                continue  # default is special and would need different handling
            flag_definitions = flag_definitions_data['flag_definition']
            if isinstance(flag_definitions, Tree):
                flag_definitions = [flag_definitions]
            result[tag] = FlagDefinitionList(
                tag=tag,
                parser=self,
                flag_definitions=list(
                    self.parse_advanced_entities(
                        Tree({
                            f'{tag}_flag_definition_{i}': flag_def
                            for i, flag_def in enumerate(flag_definitions)
                        }),
                        FlagDefinition,
                        extra_data_functions={
                            'tag': lambda _name, _data: tag
                        }
                    ).values()
                )
            )
        tags_with_coas_without_flag_def = (set(self.countries_including_formables.keys()) & set(
            self.coat_of_arms.keys())) - set(result.keys())
        for tag in tags_with_coas_without_flag_def:
            result[tag] = FlagDefinitionList(
                tag=tag,
                parser=self,
                flag_definitions=[
                    FlagDefinition(
                        f'{tag}_dummy_flag_definition',
                        f'{tag}_dummy_flag_definition',
                        coa=self.coat_of_arms[tag],
                        priority=1,
                        dummy=True,
                    ),
                ]
            )
        return result

    @cached_property
    def game_concepts(self) -> dict[str, Eu5GameConcept]:
        """Includes the aliases as well"""
        concepts = self.parse_advanced_entities('main_menu/common/game_concepts', Eu5GameConcept,
                                                localization_prefix='game_concept_',
                                                allow_empty_entities=True,
                                                extra_data_functions={
                                                    'description': lambda name, data: self.localize('game_concept_' + name + '_desc', default='')
                                                })
        for name in list(concepts.keys()):  # iterate over a new list so that we can add to the concepts variable during the iteration
            concept = concepts[name]
            aliases = []
            for alias in concept.alias:
                if alias in concepts:
                    raise Exception(f'Alias "{alias}" from concept "{name}" already exists as a concept')
                alias_concept = Eu5GameConcept(alias, self.localize('game_concept_' + alias), description=concept.description, family=concept.family, is_alias=True)
                concepts[alias] = alias_concept
                aliases.append(alias_concept)
            concept.alias = aliases
        return concepts

    @cached_property
    def goods(self) -> dict[str, Good]:
        return self.parse_advanced_entities('in_game/common/goods', Good)

    @cached_property
    def goods_demand(self) -> dict[str, GoodsDemand]:
        return self.parse_nameable_entities('in_game/common/goods_demand', GoodsDemand, extra_data_functions={
            'demands': lambda name, data: [Cost.create_with_goods(key, value) for key, value in data if key in self.goods],
        })

    @cached_property
    def government_types(self) -> dict[str, GovernmentType]:
        return self.parse_advanced_entities('in_game/common/government_types', GovernmentType)

    @cached_property
    def impassable_mountains(self) -> dict[str, Location]:
        """wasteland locations from the impassable_mountains list in game/in_game/map_data/default.map """
        return {name: self.locations[name] for name in self.default_map['impassable_mountains']}

    @cached_property
    def institution(self) -> dict[str, Institution]:
        return self.parse_advanced_entities('in_game/common/institution', Institution)

    @cached_property
    def lakes(self) -> dict[str, Location]:
        """lake locations from the lakes list in game/in_game/map_data/default.map """
        return {name: self.locations[name] for name in self.default_map['lakes']}

    @cached_property
    def language_families(self) -> dict[str, LanguageFamily]:
        return self.parse_nameable_entities('in_game/common/language_families', LanguageFamily)

    @cached_property
    def languages(self) -> dict[str, Language]:
        languages = self.parse_advanced_entities('in_game/common/languages', Language)
        for language in languages.values():
            if language.dialects:
                language.dialects = self.parse_advanced_entities(language.dialects, Language, allow_empty_entities=True)
        return languages

    @cached_property
    def languages_including_dialects(self) -> dict[str, Language]:
        results = {}

        for language_name, language in self.languages.items():
            results[language_name] = language
            if language.dialects:
                for dialect_name, dialect in language.dialects.items():
                    if dialect_name in results:
                        print(f'Error {dialect_name} already defined {results[dialect_name]}')
                    else:
                        results[dialect_name] = dialect
        return results

    @cached_property
    def laws(self) -> dict[str, Law]:
        return self.parse_advanced_entities('in_game/common/laws', Law, extra_data_functions={
            'policies': self._parse_law_policies,
        })

    def _parse_law_policies(self, name: str, data: Tree) -> list[LawPolicy]:
        possible_law_attributes = Law.all_annotations().keys()
        policy_data = data.filter_elements(lambda k, v: k not in possible_law_attributes)
        return self.parse_advanced_entities(policy_data, LawPolicy, allow_empty_entities=True)

    @cached_property
    def law_policies(self) -> dict[str, LawPolicy]:
        return {name: policy for law in self.laws.values() for name, policy in law.policies.items()}


    @cached_property
    @disk_cache(game=eu5game, classes_to_cache={Location})
    def locations(self) -> dict[str, Location]:
        return self.parse_advanced_entities('in_game/map_data/' + self.default_map.get_or_default('location_templates', 'location_templates.txt'), Location, extra_data_functions={
            'is_earthquakes_zone': lambda name, data: name in self.default_map['earthquakes'],
            'is_impassable_mountains': lambda name, data: name in self.default_map['impassable_mountains'],
            'is_lake': lambda name, data: name in self.default_map['lakes'],
            'is_non_ownable': lambda name, data: name in self.default_map['non_ownable'],
            'is_sea': lambda name, data: name in self.default_map['sea_zones'],
            'is_volcano': lambda name, data: name in self.default_map['volcanoes'],
        })

    @cached_property
    def location_ranks(self) -> dict[str, LocationRank]:
        return self.parse_advanced_entities('in_game/common/location_ranks', LocationRank)

    def get_province(self, location: Location):
        return self._prov_for_loc[location.name]

    @cached_property
    def _prov_for_loc(self):
        return {location: province
                for province in self.provinces.values()
                for location in province.locations.keys()}

    @cached_property
    def named_colors(self) -> dict[str, PdxColor]:
        return self._parse_named_colors(['../jomini/loading_screen/common/named_colors', 'main_menu/common/named_colors'])

    @cached_property
    def non_ownable(self) -> dict[str, Location]:
        """corridor locations from the non_ownable list in game/in_game/map_data/default.map """
        return {name: self.locations[name] for name in self.default_map['non_ownable']}

    def parse_dlc_from_conditions(self, conditions):
        pass

    @cached_property
    def pop_types(self) -> dict[str, PopType]:
        pop_types = self.parse_advanced_entities('in_game/common/pop_types', PopType,
                                            extra_data_functions={
                                                'possible_estates_with_triggers': lambda name, data: {
                                                    estate: data[estate.name]
                                                    for estate in self.estates.values()
                                                    if estate.name in data
                                                }
                                            })
        for pop_type in pop_types.values():
            if not isinstance(pop_type.promote_to, list):
                pop_type.promote_to = [pop_type.promote_to]
            pop_type.promote_to = [pop_types[p] for p in pop_type.promote_to]
        return pop_types

    @cached_property
    def prices(self) -> dict[str, Price]:
        return self.parse_nameable_entities('in_game/common/prices', Price, allow_empty_entities=True, extra_data_functions={
            'costs': lambda name, data: [Cost.create_with_hardcoded_resource(key, value) for key, value in data if key in HardcodedResource]
        })

    @cached_property
    def production_methods(self) -> dict[str, ProductionMethod]:
        return self._parse_production_methods('in_game/common/production_methods')

    @cached_property
    def all_production_methods(self) -> dict[str, ProductionMethod]:
        """Also includes unique production methods which are defined in buildings"""
        production_methods = self.production_methods.copy()
        for building in self.buildings.values():
            for pm_list in building.unique_production_methods:
                for pm in pm_list:
                    production_methods[pm.name] = pm
        return production_methods

    def _parse_production_methods(self, data_source: str | Tree):
        if isinstance(data_source, list):
            FileGenerator.warn(f'Multiple production method sections:{[[name for name, data in tree] for tree in data_source]}')
            data_source = reduce(lambda t1, t2: t1.update(t2), data_source)
        return self.parse_nameable_entities(data_source, ProductionMethod,
                                            extra_data_functions={
                                                'input': lambda name, data: [Cost.create_with_goods(key, value) for key, value in data if key in self.goods],
                                            },
                                            transform_value_functions={
                                                'produced': lambda value: self.goods[value]
                                            })

    @cached_property
    def religious_aspects(self) -> dict[str, ReligiousAspect]:
        aspects = self.parse_advanced_entities('in_game/common/religious_aspects', ReligiousAspect)
        for aspect in aspects.values():
            if aspect.opinions:
                aspect.opinions = {aspects[key]: value for key, value in aspect.opinions}
            else:
                aspect.opinions =  {}
        return aspects

    @cached_property
    def religious_factions(self) -> dict[str, ReligiousFaction]:
        return self.parse_advanced_entities('in_game/common/religious_factions', ReligiousFaction)

    @cached_property
    def religious_focuses(self) -> dict[str, ReligiousFocus]:
        return self.parse_advanced_entities('in_game/common/religious_focuses', ReligiousFocus)

    @cached_property
    def religion_groups(self) -> dict[str, ReligionGroup]:
        return self.parse_advanced_entities('in_game/common/religion_groups', ReligionGroup)

    @cached_property
    def religious_schools(self) -> dict[str, ReligiousSchool]:
        return self.parse_advanced_entities('in_game/common/religious_schools', ReligiousSchool)

    @cached_property
    def religions(self) -> dict[str, Religion]:
        return self.parse_advanced_entities('in_game/common/religions', Religion, transform_value_functions={
            # so that the parser passes the value through even though important_country is not an attribute
            'important_country': lambda c: c,
        })

    @cached_property
    def script_values(self) -> dict[str, ScriptValue]:
        # @TODO: this needs to be parsed differently, because some entries could be duplicated and their order matters
        tree_data = self.parser.parse_folder_as_one_file('main_menu/common/script_values')
        tree_data.update(self.parser.parse_folder_as_one_file('in_game/common/script_values'))
        tree_data.merge_duplicate_keys()
        script_values = {}

        for name, data in tree_data:
            script_values[name] = self._parse_script_value(name, data)

        return script_values

    def _parse_script_value(self, name, data):
        entity_data = {}
        if isinstance(data, Tree):
            # value with calculation
            calculations = Tree({})
            for k, v in data:
                if k == 'value' and not isinstance(v, Tree):
                    entity_data['value'] = v
                elif k == 'desc':
                    entity_data['desc'] = self.formatter.format_localization_text(self.localize(v))
                else:
                    calculations[k] = v
            entity_data['calculations'] = calculations
        else:
            entity_data['direct_value'] = data
        return ScriptValue(name, name, **entity_data)

    @cached_property
    def sea_zones(self) -> dict[str, Location]:
        """sea tiles from sea_zones list in game/in_game/map_data/default.map """
        return {name: self.locations[name] for name in self.default_map['sea_zones']}

    @cached_property
    def topography(self) -> dict[str, Topography]:
        return self.parse_advanced_entities('in_game/common/topography', Topography)

    @cached_property
    def vegetation(self) -> dict[str, Vegetation]:
        return self.parse_advanced_entities('in_game/common/vegetation', Vegetation)

    @cached_property
    def volcanoes(self) -> dict[str, Location]:
        """volcanoe locations from the volcanoes list in game/in_game/map_data/default.map """
        return {name: self.locations[name] for name in self.default_map['volcanoes']}

    ############################################
    #                                          #
    #  Autogenerated classes with helper.py    #
    #                                          #
    ############################################


    @cached_property
    def coat_of_arms(self) -> dict[str, CoatOfArms]:
        return self.parse_advanced_entities('main_menu/common/coat_of_arms/coat_of_arms', CoatOfArms)
    @cached_property
    def achievements(self) -> dict[str, Achievement]:
        return self.parse_advanced_entities('main_menu/common/achievements', Achievement,
                                            description_localization_prefix='ACHIEVEMENT_DESC_', description_localization_suffix='', # Used in 1/1 Examples: {'ACHIEVEMENT_DESC_until_death_do_us_apart': 'Secure a Royal Marriage with another country.'}
                                            localization_prefix='ACHIEVEMENT_', # Used in 1/1 Examples: {'ACHIEVEMENT_until_death_do_us_apart': 'Until death do us apart'}
                                            )
    @cached_property
    def ai_diplochance(self) -> dict[str, AiDiplochance]:
        return self.parse_advanced_entities('in_game/common/ai_diplochance', AiDiplochance, allow_empty_entities=True)
    @cached_property
    def artist_types(self) -> dict[str, ArtistType]:
        return self.parse_advanced_entities('in_game/common/artist_types', ArtistType, allow_empty_entities=True,
                                            description_localization_prefix='ARTIST_TYPE_DESC_', description_localization_suffix='', # Used in 12/12 Examples: {'ARTIST_TYPE_DESC_calligrapher': "Calligraphers create art through intricate combinations of letters, that may be exposed in books or scrolls, usually in palaces and temples. Famous calligraphers of the era include Mir Emad Hassani, Han Seok-bong, or the #italic Kan'ei Sanpitsu#!.", 'ARTIST_TYPE_DESC_sculptor': 'A sculptor shapes clay, stone, marble, wood, and other materials into art. Famous sculptors of the era include Donatello, Michelangelo, and Gianlorenzo Bernini.'}
                                            localization_prefix='ARTIST_TYPE_NAME_', # Used in 12/12 Examples: {'ARTIST_TYPE_NAME_iconographer': 'Iconographer', 'ARTIST_TYPE_NAME_jurist': 'Jurist'}
                                            )
    @cached_property
    def artist_work(self) -> dict[str, ArtistWork]:
        return self.parse_advanced_entities('in_game/common/artist_work', ArtistWork,
                                            # localization_prefix='', localization_suffix='', # Used in 21/21 Examples: {'novel': 'Novel', 'temple_tower': 'Temple Tower'}
                                            description_localization_prefix='', description_localization_suffix='_desc', # Used in 21/21 Examples: {'painting_desc': 'Capturing a moment in time or giving an important moment in our history a visual representation, the art of painting on any surface is highly valued.', 'temple_tower_desc': 'A crowning piece of architecture for a religious building, a $temple_tower$ will elevate the importance of its $temple$. The Tower will be able to shape our settlements and show our devotion to the divine.'}
                                            )
    @cached_property
    def attribute_columns(self) -> dict[str, AttributeColumn]:
        return self.parse_advanced_entities('in_game/common/attribute_columns', AttributeColumn,
                                            )
    @cached_property
    def auto_modifiers(self) -> dict[str, AutoModifier]:
        return self.parse_advanced_entities('in_game/common/auto_modifiers', AutoModifier,
                                            localization_prefix='AUTO_MODIFIER_NAME_', # Used in 74/74 Examples: {'AUTO_MODIFIER_NAME_positive_yanantin': 'Positive [yanantin|e]', 'AUTO_MODIFIER_NAME_positive_harmony': 'Yáng'}
                                            )
    @cached_property
    def avatars(self) -> dict[str, Avatar]:
        return self.parse_advanced_entities('in_game/common/avatars', Avatar,
                                            # localization_prefix='', localization_suffix='', # Used in 20/20 Examples: {'krishna_avatar': 'Kṛṣṇa', 'chhinnamasta_avatar': 'Chinnamastā'}
                                            description_localization_prefix='', description_localization_suffix='_desc', # Used in 20/20 Examples: {'kurma_avatar_desc': "$kurma_avatar$ is the second [avatar|e] of [ShowGodName('vishnu_god')], represented as a turtle or tortoise. He is equated to the World-Turtle that supports the world on its shell, and is revered for his steadiness and firmness.", 'bhuvaneshvari_avatar_desc': '$bhuvaneshvari_avatar$ $shakti_common_desc$ Devī as the World Mother.'}
                                            )
    @cached_property
    def biases(self) -> dict[str, Bias]:
        return self.parse_advanced_entities('in_game/common/biases', Bias,
                                            # localization_prefix='', localization_suffix='', # Used in 1003/1003 Examples: {'opinion_international_law': 'International Reputation', 'opinion_threatened_us': 'Threatened us'}
                                            )
    @cached_property
    def cabinet_actions(self) -> dict[str, CabinetAction]:
        return self.parse_advanced_entities('in_game/common/cabinet_actions', CabinetAction,
                                            # localization_prefix='', localization_suffix='', # Used in 63/63 Examples: {'expel_people': 'Expel People', 'aid_constantinople': 'Aid Constantinople'}
                                            # localization_prefix='', localization_suffix='_active', # Used in 63/63 Examples: {'study_institutions_active': "Promoting Institutions in [SCOPE.sProvince('target').GetNameWithNoTooltip]", 'increase_control_area_active': "Increasing Control in [SCOPE.sArea('selected_area').GetNameWithNoTooltip]"}
                                            # localization_prefix='', localization_suffix='_action', # Used in 63/63 Examples: {'encourage_migration_action': "Encourage [migration|e] to [SCOPE.sLocation('target').GetName]", 'reform_taxation_system_action': 'Reform the Tax System'}
                                            # localization_prefix='', localization_suffix='_action_progress', # Used in 63/63 Examples: {'send_secret_royal_inspectors_action_progress': "[SCOPE.sProvince('target').GetAverageControl|V2%]", 'kbo_sharia_courts_action_progress': 'Enforcing $sharia$ Administration'}
                                            # localization_prefix='', localization_suffix='_action_progress_wordier', # Used in 63/63 Examples: {'diplomatic_endeavors_action_progress_wordier': "[diplomatic_reputation|e]: [SCOPE.sCountry('actor').GetModifierValue('diplomatic_reputation')]", 'pop_promote_action_action_progress_wordier': "[SCOPE.sCountry('actor').GetDoubleModifierValue('global_pop_promotion_speed','global_pop_promotion_speed_modifier')]"}
                                            # localization_prefix='', localization_suffix='_action_progress_tooltip', # Used in 63/63 Examples: {'pru_deal_with_robber_barons_action_progress_tooltip': 'Dealing with the Robber Barons', 'send_people_to_the_colonies_action_progress_tooltip': ''}
                                            description_localization_prefix='', description_localization_suffix='_desc', # Used in 63/63 Examples: {'byz_extensive_conscription_desc': 'During times of war and when our faith is at risk, as we struggle to protect what is holy, it falls upon our shoulders to call all able-bodied pious men to serve and donate their dues against our heathen foes.', 'reduced_paperwork_desc': "As a [ShowHegemonyName('economic_hegemon')] we can use our government to make sure our economy is more efficient."}
                                            )
    @cached_property
    def casus_belli(self) -> dict[str, CasusBelli]:
        return self.parse_advanced_entities('in_game/common/casus_belli', CasusBelli,
                                            # localization_prefix='', localization_suffix='', # Used in 86/86 Examples: {'cb_humiliate': 'Humiliate', 'cb_chinese_unification': "Unify [ShowSubContinentNameWithNoTooltip('china')]"}
                                            description_localization_prefix='', description_localization_suffix='_desc', # Used in 86/86 Examples: {'cb_horde_vs_civ_desc': 'There can be no peace between tribes and settlers! Their possessions belong to the Horde!', 'cb_take_shogunate_desc': 'We have the right to become $JAPANESE_SHOGUNATE_LEADER_MALE$, let us take it.'}
                                            )
    @cached_property
    def character_interactions(self) -> dict[str, CharacterInteraction]:
        return self.parse_advanced_entities('in_game/common/character_interactions', CharacterInteraction,
                                            # localization_prefix='', localization_suffix='', # Used in 29/29 Examples: {'resign_as_grand_master': 'Resign as Grandmaster', 'promote_to_head_of_cabinet': 'Promote to Head of Cabinet'}
                                            # localization_prefix='', localization_suffix='_act', # Used in 29/29 Examples: {'commission_art_act': '$commission_art$', 'marry_lowborn_act': '$marry_lowborn$'}
                                            description_localization_prefix='', description_localization_suffix='_desc', # Used in 29/29 Examples: {'make_regent_ruler_desc': 'The [character|e] will become the new [ruler|e] of the [country|e].', 'favor_heir_desc': 'The [character|e] will be favored to be our new successor.'}
                                            # localization_prefix='', localization_suffix='_act_past', # Used in 29/29 Examples: {'ennoble_act_past': "[recipient.GetName] has been elevated to the [SCOPE.sCountry('actor').GetGovernment.GetEstateName('nobles_estate')].", 'resign_as_grand_master_act_past': "[SCOPE.sCharacter('recipient').GetName] resigned as [ruler|e] of [SCOPE.sCountry('actor').GetName]."}
                                            # localization_prefix='', localization_suffix='_past', # Used in 29/29 Examples: {'pap_reassign_cleric_past': '[recipient.GetNameWithNoTooltip] Reassigned', 'tribal_arrange_marriage_past': "[SCOPE.sCharacter('recipient').GetName] has married!"}
                                            # description_localization_prefix='', description_localization_suffix='_desc_specific', # Used in 29/29 Examples: {'resign_as_grand_master_desc_specific': "[SCOPE.sCharacter('recipient').GetName] will resign as [ruler|e] of [SCOPE.sCountry('actor').GetName].", 'marry_lowborn_desc_specific': "[SCOPE.sCharacter('recipient').GetName] will marry a [lowborn|e], to the disgrace of the [actor.GetFlavorRank]."}
                                            )
    @cached_property
    def child_educations(self) -> dict[str, ChildEducation]:
        return self.parse_advanced_entities('in_game/common/child_educations', ChildEducation,
                                            # localization_prefix='', localization_suffix='', # Used in 5/5 Examples: {'administrative_education': 'Administrative Education', 'military_education': 'Military Education'}
                                            description_localization_prefix='', description_localization_suffix='_desc', # Used in 5/5 Examples: {'expensive_in_depth_education_desc': 'Our wealth is sufficient when it comes to securing in-depth education for our heir. Access to some of the best tutors and material source will grant us unique knowledge as well as the best education money can buy.', 'military_education_desc': 'Projecting military strength is the backbone of our nation. A focus on military matters and the study of the nature of war as well as management of our armed forces are pivotal for educational purposes.'}
                                            )
    @cached_property
    def country_interactions(self) -> dict[str, CountryInteraction]:
        return self.parse_advanced_entities('in_game/common/country_interactions', CountryInteraction,
                                            # localization_prefix='', localization_suffix='', # Used in 96/96 Examples: {'lordship_of_ireland_surrender_and_regrant': 'Surrender and Regrant', 'ask_to_lift_interdict': 'Request Lifting Interdict'}
                                            # localization_prefix='', localization_suffix='_act', # Used in 96/96 Examples: {'enforce_landfriede_act': "Enforce the Landfriede upon [SCOPE.sCountry('recipient').GetName].", 'send_to_prussian_crusade_act': "Send a [character|E] to [SCOPE.sCountry('recipient').GetName] to participate in the #Y Prussian Crusade#!"}
                                            # localization_prefix='', localization_suffix='_effect_text_past', # Used in 96/96 Examples: {'ask_for_dukedom_effect_text_past': "[SCOPE.sCountry('recipient').GetName] raised the [country_rank|e] of [SCOPE.sCountry('actor').GetName] to [ShowCountryRankName('rank_duchy')].", 'request_elector_status_effect_text_past': "[SCOPE.sCountry('actor').GetName] became an [elector|e] in the [GetUniqueInternationalOrganization('hre').GetName]."}
                                            description_localization_prefix='', description_localization_suffix='_desc', # Used in 96/96 Examples: {'lordship_of_ireland_bestow_lieutenant_status_desc': "We will make them a [ShowSpecialStatusName('lieutenant')] in the [GetUniqueInternationalOrganization('lordship_of_ireland').GetName].", 'bestow_kingdom_title_desc': "We will bestow a $kingdom_title$ to a [member|e] of the [GetUniqueInternationalOrganization('hre').GetName], allowing them to be elevated to the rank of a [ShowCountryRankName('rank_kingdom')].$kingdom_title_available_titles$"}
                                            # localization_prefix='', localization_suffix='_effect_text', # Used in 96/96 Examples: {'request_county_privileges_effect_text': "[SCOPE.sCountry('recipient').GetName] grants privileges to [SCOPE.sCountry('actor').GetName], giving them the right to enact [SCOPE.sGovernmentReform('target').GetName].", 'force_embargo_effect_text': "[SCOPE.sCountry('actor').GetName] force [SCOPE.sCountry('recipient').GetName] to embargo [SCOPE.sCountry('target').GetName]"}
                                            )
    @cached_property
    def country_ranks(self) -> dict[str, CountryRank]:
        return self.parse_advanced_entities('in_game/common/country_ranks', CountryRank,
                                            # localization_prefix='', localization_suffix='', # Used in 4/4 Examples: {'rank_county': 'County', 'rank_empire': 'Empire'}
                                            description_localization_prefix='', description_localization_suffix='_desc', # Used in 4/4 Examples: {'rank_empire_desc': 'This is the highest [country_rank|e] and represents the most prestigious or powerful [countries|e] in the world.', 'rank_duchy_desc': 'This [country_rank|e] represents a small- to medium-sized [country|e], usually with a single [province|e], but it is larger or more populous than a $rank_county$.'}
                                            )

    def _parse_customizable_localization_text_entry(self, data: Tree | list[Tree]) -> dict[
        str, CustomizableLocalizationTextEntry]:
        if not isinstance(data, list):
            data = [data]
        return self.parse_advanced_entities(
            Tree({custom_loc_entry['localization_key']: custom_loc_entry for custom_loc_entry in data}),
            CustomizableLocalizationTextEntry,
            extra_data_functions={
                'display_name': lambda name, data: self.formatter.format_localization_text(self.localize(name))
            })

    @cached_property
    def customizable_localization(self) -> dict[str, CustomizableLocalization]:
        return self.parse_advanced_entities('in_game/common/customizable_localization', CustomizableLocalization,
                                            transform_value_functions={
                                                'text': self._parse_customizable_localization_text_entry,
                                            })
    @cached_property
    def death_reason(self) -> dict[str, DeathReason]:
        return self.parse_advanced_entities('in_game/common/death_reason', DeathReason, allow_empty_entities=True,
                                            localization_prefix='DEATH_REASON_', # Used in 49/49 Examples: {'DEATH_REASON_poison_arrow': '[CHARACTER.GetHeSheFormal|U] killed by a poison arrow.', 'DEATH_REASON_froze': '[CHARACTER.GetHeSheFormal|U] froze to death.'}
                                            # localization_prefix='DEATH_REASON_', localization_suffix='_location', # Used in 16/49 Examples: {'DEATH_REASON_assassination_location': "[CHARACTER.GetHeSheFormal|U] was assassinated in [SCOPE.sLocation('location').GetName].", 'DEATH_REASON_camp_location': "[CHARACTER.GetHeSheFormal|U] died while the army was camped in [SCOPE.sLocation('location').GetName]."}
                                            )
    @cached_property
    def designated_heir_reason(self) -> dict[str, DesignatedHeirReason]:
        return self.parse_advanced_entities('in_game/common/designated_heir_reason', DesignatedHeirReason,
                                            localization_prefix='HEIR_REASON_', # Used in 3/3 Examples: {'HEIR_REASON_preferred_heir_of_ruler': "Ruler's Choice", 'HEIR_REASON_designated_as_appanage': 'Designated as $appanage$'}
                                            allow_empty_entities=True
                                            )
    @cached_property
    def diplomatic_costs(self) -> dict[str, DiplomaticCost]:
        return self.parse_advanced_entities('in_game/common/diplomatic_costs', DiplomaticCost,
                                            allow_empty_entities=True,
                                            )
    @cached_property
    def disasters(self) -> dict[str, Disaster]:
        return self.parse_advanced_entities('in_game/common/disasters', Disaster,
                                            # localization_prefix='', localization_suffix='', # Used in 30/30 Examples: {'succession_crisis': 'Succession Crisis', 'decline_of_majapahit': 'Decline of Majapahit'}
                                            description_localization_prefix='', description_localization_suffix='_desc', # Used in 30/30 Examples: {'time_of_troubles_desc': 'A time of both social and economic problems, our nation is struggling with both famine and war as well as the opposition against the Church and aristocracy.', 'ciompi_revolt_desc': 'A time of uncertainty for Florence, the Ciompi, which are comprised of citizens, peasants, and members of low-tier guilds, are threatening with an open revolt. Heavy taxation and very little representation are some of the factors that have given way to the rise of such a widespread revolt.'}
                                            )
    @cached_property
    def diseases(self) -> dict[str, Disease]:
        return self.parse_advanced_entities('in_game/common/diseases', Disease,
                                            # localization_prefix='', localization_suffix='', # Used in 7/7 Examples: {'smallpox': 'Smallpox', 'bubonic_plague': 'Bubonic Plague'}
                                            description_localization_prefix='', description_localization_suffix='_desc', # Used in 7/7 Examples: {'measles_desc': 'Measles, also known as morbili, rubeola, and red measles, is a plague that spreads extremely fast from person to person, causing fever, coughs, sneezes, and a great flat rash that eventually covers the entire body. It preys most eagerly on children, who are at great risk of death if they fall on its claws.', 'bubonic_plague_desc': 'A great pestilence that sweeps through busy trade routes, sparing neither low nor high. Those infected suffer black swellings in the groin and armpits, terrible fever, and death. Some believe it is carried by the vermin that scurry in our streets and fields, spreading foul sickness from one poor soul to another.'}
                                            )
    @cached_property
    def effect_localization(self) -> dict[str, EffectLocalization]:
        return self.parse_advanced_entities('in_game/common/effect_localization', EffectLocalization, extra_data_functions={
            'global_': lambda name, data: data['global'] if 'global' in data else ''
        })
    @cached_property
    def employment_systems(self) -> dict[str, EmploymentSystem]:
        return self.parse_advanced_entities('in_game/common/employment_systems', EmploymentSystem,
                                            # localization_prefix='', localization_suffix='', # Used in 3/3 Examples: {'first_come_first_serve': 'First Come, First Serve', 'equality': 'Equality'}
                                            description_localization_prefix='', description_localization_suffix='_desc', # Used in 3/3 Examples: {'capitalism_desc': 'Buildings are filled in order of which makes the most profit.', 'first_come_first_serve_desc': 'Buildings are filled in the order they were built.'}
                                            )
    @cached_property
    def ethnicities(self) -> dict[str, Ethnicity]:
        return self.parse_advanced_entities('in_game/common/ethnicities', Ethnicity)
    @cached_property
    def formable_countries(self) -> dict[str, FormableCountry]:
        return self.parse_advanced_entities('in_game/common/formable_countries', FormableCountry,
                                            # localization_prefix='', localization_suffix='', # Used in 127/127 Examples: {'denmark_f': 'Denmark', 'MGE_f': '$MGE$'}
                                            description_localization_prefix='', description_localization_suffix='_desc', # Used in 125/127 Examples: {'WES_f_desc': "With the clerical influences over our lands slowly fading into the past it is time to form a new state for [ShowAreaName('westphalia_area')] and proclaim a new era for our people.", 'PUN_f_desc': "We must unite the [ShowCultureName('punjabi')] people if we are ever to be able to stand against foreign invaders. Together we will build a modern state with armies capable of taking on the many enemies who would attack us for our lands, and who would do anything to extinguish our faith!"}
                                            extra_data_functions={
                                                'country_name': lambda name, data: data['name'] if 'name' in data else data['tag'],
                                            }
                                            )
    @cached_property
    def game_rules(self) -> dict[str, GameRule]:
        return self.parse_advanced_entities('main_menu/common/game_rules', GameRule,
                                            localization_prefix='rule_', # Used in 22/22 Examples: {'rule_black_death_date_rule': 'Black Death Outbreak Year', 'rule_player_difficulty': 'Player Difficulty'}
                                            )

    # @TODO: genes are a nested structure. this just gets the category
    @cached_property
    def genes(self) -> dict[str, Gene]:
        return self.parse_advanced_entities('in_game/common/genes', Gene)
    @cached_property
    def generic_actions(self) -> dict[str, GenericAction]:
        return self.parse_advanced_entities('in_game/common/generic_actions', GenericAction,
                                            # localization_prefix='', localization_suffix='', # Used in 337/337 Examples: {'union_bribe_nobility': 'Bribe Nobility', 'rot_select_core_region': 'Select Core Region'}
                                            description_localization_prefix='', description_localization_suffix='_desc', # Used in 337/337 Examples: {'start_a_treasure_voyage_desc': "The glory of the [GetInternationalOrganization('middle_kingdom').GetName] shall be known in each and every corner of the known and the unknown world. In order to make this into a reality, let us send a glorious voyage to explore the unexplored and to spread the fame of the [GetInternationalOrganization('middle_kingdom').GetLeaderCountry.GetName].", 'request_aid_desc': "Our order is the bastion of our faith, defenders of true believers, and a shield against those who wish to harm our people. Granting aid to our cause should be the prime directive for the [GetCountry('PAP').GetGovernment.GetRulerTitle]."}
                                            )
    @cached_property
    def generic_action_ai_lists(self) -> dict[str, GenericActionAiList]:
        return self.parse_advanced_entities('in_game/common/generic_action_ai_lists', GenericActionAiList)

    def _parse_religion_in_god(self, religion_entry) -> [Religion]:
        if isinstance(religion_entry, str):
            return [self.religions[religion_entry]]
        elif isinstance(religion_entry, list):
            result = []
            for r in religion_entry:
                result += self._parse_religion_in_god(r)
            return result
        elif isinstance(religion_entry, Tree):
            return self._parse_religion_in_god(religion_entry['religion'])


    @cached_property
    def gods(self) -> dict[str, God]:
        return self.parse_advanced_entities('in_game/common/gods', God,
                                            # localization_prefix='', localization_suffix='', # Used in 102/102 Examples: {'shakti_god': 'Śakti', 'ikenga_god': 'Ikenga'}
                                            description_localization_prefix='', description_localization_suffix='_desc', # Used in 102/102 Examples: {'huitzilopochtli_god_desc': "[ShowGodName('huitzilopochtli_god')] is the solar and war deity of sacrifice for the people of [ShowLocationName('tenochtitlan')].", 'yuma_sammang_god_desc': "$yuma_sammang_god$ is the supreme god and Mother Earth of the [ShowCultureName('limbu_culture')] people."}
                                            transform_value_functions={
                                                'religion': self._parse_religion_in_god
                                            }
                                            )
    @cached_property
    def goods_demand_category(self) -> dict[str, GoodsDemandCategory]:
        return self.parse_advanced_entities('in_game/common/goods_demand_category', GoodsDemandCategory,
                                            allow_empty_entities=True,
                                            # localization_prefix='', localization_suffix='', # Used in 13/13 Examples: {'government_activities': 'Government Activities', 'mills_input': 'Mills Input'}
                                            )
    @cached_property
    def government_reforms(self) -> dict[str, GovernmentReform]:
        return self.parse_advanced_entities('in_game/common/government_reforms', GovernmentReform,
                                            # localization_prefix='', localization_suffix='', # Used in 287/287 Examples: {'the_court_of_wards_and_liveries': 'The Court of Wards and Liveries', 'taluqdar_nobility': 'Taluqdar Nobility'}
                                            description_localization_prefix='', description_localization_suffix='_desc', # Used in 287/287 Examples: {'religious_tolerance_desc': 'Our country is populated by people who practice different beliefs and confessions. Therefore, it would be prudent to govern in a tolerant manner with them, ensuring their support for our government.', 'great_and_minor_councils_of_genoa_desc': "Created by Admiral Andrea Doria after his reformation of the Genoese government, the $great_and_minor_councils_of_genoa$ are the two legislatures of the state. The Great Council represents the members of the [ShowEstateTypeName('burghers_estate')] while the Minor Council is made of the [ShowEstateTypeName('nobles_estate')]."}
                                            )
    @cached_property
    def hegemons(self) -> dict[str, Hegemon]:
        return self.parse_advanced_entities('in_game/common/hegemons', Hegemon,
                                            # localization_prefix='', localization_suffix='', # Used in 5/5 Examples: {'diplomatic_hegemon': 'Diplomatic Hegemon', 'naval_hegemon': 'Naval Hegemon'}
                                            description_localization_prefix='', description_localization_suffix='_desc', # Used in 5/5 Examples: {'cultural_hegemon_desc': 'The Cultural Hegemon is the [great_power|e] with the highest [cultural_influence|e].', 'military_hegemon_desc': 'The Military Hegemon is the [great_power|e] with the highest [army|e] size.'}
                                            )
    @cached_property
    def heir_selections(self) -> dict[str, HeirSelection]:
        return self.parse_advanced_entities('in_game/common/heir_selections', HeirSelection,
                                            # localization_prefix='', localization_suffix='', # Used in 43/43 Examples: {'favorite_son_elective_succession': 'Favored Son Succession', 'unigeniture': 'Unigeniture'}
                                            description_localization_prefix='', description_localization_suffix='_desc', # Used in 43/43 Examples: {'diarchic_election_desc': "It is a unique type of [heir_selection|e] of the Republic of [GetCountry('GEN').GetName] in which the [ruler|e] is chosen from the families of [ShowDynastyName('spinola_dynasty')] and [ShowDynastyName('doria_dynasty')].", 'admiralty_regime_heir_selection_desc': "It is a type of [heir_selection|e] of a [ShowGovernmentReformName('admiralty_regime_reform')], in which the new ruler is elected from the leading admirals. In case no admiral is available, a provisional council will lead the state until a fitting candidate has been found."}
                                            )
    @cached_property
    def historical_scores(self) -> dict[str, HistoricalScore]:
        return self.parse_advanced_entities('in_game/common/historical_scores', HistoricalScore,
                                            # localization_prefix='', localization_suffix='', # Used in 21/21 Examples: {'hs_tamerlane': 'Timur of the Timurid Empire', 'hs_enrique_de_impotent': 'Enrique IV of Castile'}
                                            description_localization_prefix='', description_localization_suffix='_desc', # Used in 21/21 Examples: {'hs_may_stuart_desc': 'Mary, Queen of Scots, a monarch of beauty and tragedy, struggled to maintain her rule amidst political turmoil and religious conflict. Her tumultuous reign and exile ended in execution, leaving a legacy intertwined with intrigue and the fate of Scotland.', 'hs_tamerlane_desc': 'Timur, the fearsome conqueror of Central Asia, forged a vast empire through relentless military campaigns and unmatched tactical brilliance. Though his reign was marked by destruction, he also patronized art and architecture, leaving a legacy of both devastation and cultural splendor.'}
                                            )
    @cached_property
    def holy_sites(self) -> dict[str, HolySite]:
        return self.parse_advanced_entities('in_game/common/holy_sites', HolySite,
                                            # localization_prefix='', localization_suffix='', # Used in 207/207 Examples: {'aranmula_parthasarathy_temple': 'Aranmula Parthasarathy Temple', 'pyramid_magician': 'Pyramid of the Magician'}
                                            )
    @cached_property
    def holy_site_types(self) -> dict[str, HolySiteType]:
        return self.parse_advanced_entities('in_game/common/holy_site_types', HolySiteType,
                                            # localization_prefix='', localization_suffix='', # Used in 10/10 Examples: {'islam_holy_site': 'Islamic Holy Site', 'christian_holy_site': 'Christian Holy Site'}
                                            description_localization_prefix='', description_localization_suffix='_desc', # Used in 10/10 Examples: {'shrine_desc': 'Built on a place of significant spiritual relevance, a $shrine$ serves as a keeper of that spirituality and to organize worship of it.', 'city_desc': 'The very epitome of civilization, a City is a bustling metropolis of industry, great temples, and seats of governmental authority sprawled across multiple districts.'}
                                            )
    @cached_property
    def insults(self) -> dict[str, Insult]:
        return self.parse_advanced_entities('in_game/common/insults', Insult,
                                            # localization_prefix='', localization_suffix='', # Used in 74/74 Examples: {'insult_no_army': 'What are you going to do, bleed on me?', 'insult_against_deccani': 'While we were building a civilization, you have kept in hiding among the vagrants of the Deccan. Bow now or meet your end at the hands of the heirs of Timur and Genghis.'}
                                            )
    @cached_property
    def international_organizations(self) -> dict[str, InternationalOrganization]:
        return self.parse_advanced_entities('in_game/common/international_organizations', InternationalOrganization,
                                            # localization_prefix='', localization_suffix='', # Used in 35/35 Examples: {'red_turban_rebels': 'Red Turban Rebels', 'union': '$game_concept_union$'}
                                            description_localization_prefix='', description_localization_suffix='_desc', # Used in 35/35 Examples: {'catholic_league_desc': "The $catholic_league$ is a defensive alliance of [ShowReligionAdjective('catholic')] countries desire to contain the growing influence and the spread of the [reformation|e] within the [GetUniqueInternationalOrganization('hre').GetName]. Although inherently [ShowReligionAdjectiveWithNoTooltip('catholic')], [ShowReligionAdjective('lutheran')] and [ShowReligionAdjective('calvinist')] states can join too if they see a political advantage from working with the League.", 'guelphs_io_desc': "The $guelphs_io$ are the group of [ShowCultureGroupName('italian_group')] states who aligns itself with the interests of the [GetCountry('PAP').GetLongName] in [ShowRegionName('italy_region')]."}
                                            )
    @cached_property
    def international_organization_land_ownership_rules(self) -> dict[str, InternationalOrganizationLandOwnershipRule]:
        return self.parse_advanced_entities('in_game/common/international_organization_land_ownership_rules', InternationalOrganizationLandOwnershipRule,
                                            # localization_prefix='', localization_suffix='', # Used in 4/8 Examples: {'hre_land_ownership': 'Imperial Land', 'high_kingship_land_ownership': 'High Kingship Region'}
                                            description_localization_prefix='', description_localization_suffix='_desc', # Used in 3/8 Examples: {'high_kingship_land_ownership_desc': 'The [region|e] innately tied to the High Kingship.', 'lordship_of_ireland_land_ownership_desc': 'The [region|e] innately tied to the Lordship of Ireland.'}
                                            )
    @cached_property
    def international_organization_payments(self) -> dict[str, InternationalOrganizationPayment]:
        return self.parse_advanced_entities('in_game/common/international_organization_payments', InternationalOrganizationPayment,
                                            # localization_prefix='', localization_suffix='', # Used in 8/8 Examples: {'imperial_contribution': 'Imperial Contribution', 'union_contribution': 'Union Contribution'}
                                            description_localization_prefix='', description_localization_suffix='_desc', # Used in 8/8 Examples: {'imperial_contribution_desc': '$imperial_gold_contribution_desc$ The gold gets directly transferred to the current [hre_emperor|e], the previous one if a [regency|e] is active.', 'imperial_army_contribution_desc': "The contribution in [manpower|e] from the different members of the [GetUniqueInternationalOrganization('hre').GetName]. [ShowLawName('military_contribution')] determines who has to contribute with how many soldiers to the army of the [hre_emperor|e]."}
                                            )
    @cached_property
    def international_organization_special_statuses(self) -> dict[str, InternationalOrganizationSpecialStatus]:
        return self.parse_advanced_entities('in_game/common/international_organization_special_statuses', InternationalOrganizationSpecialStatus,
                                            # localization_prefix='', localization_suffix='', # Used in 24/24 Examples: {'japanese_emperor': 'Tennō', 'imperial_prelate': 'Imperial Prelate'}
                                            description_localization_prefix='', description_localization_suffix='_desc', # Used in 24/24 Examples: {'imperial_prelate_desc': "The $imperial_prelate$ is a [special_status|e] reserved for all members which are a [ShowGovernmentTypeName('theocracy')] without being [ShowSpecialStatusName('archbishop_elector')].", 'imperial_peasant_republic_desc': "Members which have the [ShowGovernmentReformName('peasant_republic_reform')] or a variation of it can assume the [special_status|e] of $imperial_peasant_republic$."}
                                            )
    @cached_property
    def levies(self) -> dict[str, Levy]:
        return self.parse_advanced_entities('in_game/common/levies', Levy)
    @cached_property
    def missions(self) -> dict[str, Mission]:
        return self.parse_advanced_entities('in_game/common/missions', Mission,
                                            # localization_prefix='', localization_suffix='', # Used in 11/11 Examples: {'generic_conquer_province': 'Regional Expansion', 'generic_capital_economy': 'Develop a $capital_economy_focus$'}
                                            description_localization_prefix='', description_localization_suffix='_DESCRIPTION', # Used in 11/11 Examples: {'generic_vassal_ties_DESCRIPTION': 'We must ensure a stable relationship with our $vassal$!', 'progress_and_literacy_DESCRIPTION': 'Tending to the literacy needs of our people is paramount.'}
                                            # localization_prefix='', localization_suffix='_BUTTON_TOOLTIP', # Used in 11/11 Examples: {'capable_cabinet_BUTTON_TOOLTIP': 'The delegation of advisory seats is pivotal towards the proper administration of our lands', 'generic_colonize_explore_BUTTON_TOOLTIP': 'The unknown offers limitless potential for growth, wealth, and prestige. We must embrace it.'}
                                            # localization_prefix='', localization_suffix='_BUTTON_DETAILS', # Used in 11/11 Examples: {'generic_vassal_ties_BUTTON_DETAILS': 'In turbulent times of uncertainty, we must look to our trusty $vassal$ in order to endure whatever obstacles and foes appear in our path. Only through cooperation and amicable relations shall we persevere!', 'development_of_infrastructure_BUTTON_DETAILS': '$development_of_infrastructure_BUTTON_TOOLTIP$'}
                                            # description_localization_prefix='', description_localization_suffix='_CRITERIA_DESCRIPTION', # Used in 11/11 Examples: {'generic_vassal_ties_CRITERIA_DESCRIPTION': 'Our relationship with our $vassal$ is stronger than ever.', 'development_of_infrastructure_CRITERIA_DESCRIPTION': 'We have developed our capital adequately.'}
                                            )
    @cached_property
    def on_action(self) -> dict[str, OnAction]:
        return self.parse_advanced_entities('in_game/common/on_action', OnAction, allow_empty_entities=True)
    @cached_property
    def parliament_agendas(self) -> dict[str, ParliamentAgenda]:
        return self.parse_advanced_entities('in_game/common/parliament_agendas', ParliamentAgenda,
                                            # localization_prefix='', localization_suffix='', # Used in 121/121 Examples: {'pa_resist_new_world': 'Contain $new_world$', 'pa_remove_festival_grounds': 'Address $festival_grounds$ Complaints'}
                                            description_localization_prefix='', description_localization_suffix='_desc', # Used in 121/121 Examples: {'pa_lessen_tax_burden_for_nobles_desc': '$lessen_tax_burden_desc$', 'pa_move_towards_innovative_desc': '$entrench_desc$ nurture our innovative roots.'}
                                            )
    @cached_property
    def parliament_issues(self) -> dict[str, ParliamentIssue]:
        return self.parse_advanced_entities('in_game/common/parliament_issues', ParliamentIssue,
                                            # localization_prefix='', localization_suffix='', # Used in 93/93 Examples: {'gravel_road_development_burghers': '$gravel_road_development$', 'found_college_of_justice': 'Establish the College of Justice'}
                                            description_localization_prefix='', description_localization_suffix='_desc', # Used in 93/93 Examples: {'expand_diplomatic_corps_religion_desc': '$expand_diplomatic_corps_generic_desc$ It is vital for us to improve our contacts to our religious brethren.', 'promote_burghers_member_desc': 'The burghers are vital to our state, both as merchants and members of the guilds. We should promote the capable members of their estate to our government.'}
                                            )
    @cached_property
    def parliament_types(self) -> dict[str, ParliamentType]:
        return self.parse_advanced_entities('in_game/common/parliament_types', ParliamentType,
                                            # localization_prefix='', localization_suffix='', # Used in 12/12 Examples: {'hre_court_assembly': 'Court Assembly', 'assembly': 'Assembly'}
                                            description_localization_prefix='', description_localization_suffix='_desc', # Used in 12/12 Examples: {'hre_court_assembly_desc': "From the old days of [GetCharacter('ogk_otto_liudolfinger').GetName], the $hre_court_assembly$ is an ancient and primitive style of assembly within the [GetUniqueInternationalOrganization('hre').GetName]. Due to the lack of codified processes, the discussion of law implementations with the [GetUniqueInternationalOrganization('hre').GetLeaderTitle] tend to be not as efficient as they could be.", 'estate_parliament_desc': 'Representatives of the Estates will gather in the parliament to discuss issues and find common ground in achieving these goals.'}
                                            )
    @cached_property
    def peace_treaties(self) -> dict[str, PeaceTreaty]:
        return self.parse_advanced_entities('in_game/common/peace_treaties', PeaceTreaty,
                                            # localization_prefix='', localization_suffix='', # Used in 48/48 Examples: {'cancel_debt': 'Cancel Debt', 'peace_revoke_clan_autonomy': 'Revoke Clan Autonomy'}
                                            )
    @cached_property
    def persistent_dna(self) -> dict[str, PersistentDna]:
        return self.parse_advanced_entities('in_game/common/persistent_dna', PersistentDna)
    @cached_property
    def recruitment_method(self) -> dict[str, RecruitmentMethod]:
        return self.parse_advanced_entities('in_game/common/recruitment_method', RecruitmentMethod,
                                            # localization_prefix='', localization_suffix='', # Used in 4/4 Examples: {'elite_training': 'Additional', 'normal_training': 'Normal'}
                                            description_localization_prefix='', description_localization_suffix='_desc', # Used in 4/4 Examples: {'normal_navy_method_desc': 'This is the default way of building a [ship|e].', 'elite_training_desc': 'The soldiers in [regiments|e] will have more [experience|e], at the cost of longer training.'}
                                            )
    @cached_property
    def regencies(self) -> dict[str, Regency]:
        return self.parse_advanced_entities('in_game/common/regencies', Regency,
                                            # localization_prefix='', localization_suffix='', # Used in 14/14 Examples: {'consort_regency': 'Consort Regency', 'overlord_regency': 'Overlord Regency'}
                                            description_localization_prefix='', description_localization_suffix='_desc', # Used in 14/14 Examples: {'fratricide_succesion_regency_desc': 'The new [ruler|e] is elected by God himself as he favors one of the sons of the old [ruler|e] over the others.', 'subject_regency_desc': "When a [country|e] is an [overlord|e] and has no [ruler|e], a powerful [subject|e]'s [ruler] may instead rule it as a [regent|e]."}
                                            )
    @cached_property
    def religious_figures(self) -> dict[str, ReligiousFigure]:
        return self.parse_advanced_entities('in_game/common/religious_figures', ReligiousFigure,
                                            # localization_prefix='', localization_suffix='', # Used in 2/2 Examples: {'guru': 'Gurū', 'muslim_scholar': 'Scholar'}
                                            description_localization_prefix='', description_localization_suffix='_desc', # Used in 2/2 Examples: {'guru_desc': 'Someone immersed in profound spirituality and in search of the path towards enlightenment, a $guru$ is a very devout person that not only performs religious and spiritual practices and exercises, but is also willing to teach and serve as a spiritual guide.', 'muslim_scholar_desc': "A learned individual and knowledgeable about [ShowReligionGroupAdjective('muslim')] Law, scholars debate the principles of jurisprudence and theology of [ShowReligionGroupNameWithNoTooltip('muslim')]."}
                                            )
    @cached_property
    def resolutions(self) -> dict[str, Resolution]:
        return self.parse_advanced_entities('in_game/common/resolutions', Resolution,
                                            # localization_prefix='', localization_suffix='', # Used in 21/23 Examples: {'excommunicate_resolution': 'Excommunication', 'parliament_issue_vote': 'Vote for Parliament Issue'}
                                            # localization_prefix='', localization_suffix='_specific', # Used in 21/23 Examples: {'repeal_law_specific': "Repeal [SCOPE.sLaw('target').GetName]", 'apostolicae_servitutis_specific': '$apostolicae_servitutis$'}
                                            # description_localization_prefix='', description_localization_suffix='_specific_desc', # Used in 21/23 Examples: {'christiana_pietas_specific_desc': '$christiana_pietas_desc$', 'immensa_aeterni_dei_specific_desc': '$immensa_aeterni_dei_desc$'}
                                            description_localization_prefix='', description_localization_suffix='_desc', # Used in 21/23 Examples: {'libertas_ecclesiae_desc': '$libertas_ecclesiae$ is the notion of freedom of ecclesiastical authority from secular or the temporal power, which guided the Reform movement which began in the 11th century.\\nBut what if a puppet of the Holy Roman Emperor is sitting on the Throne of Saint Peter?', 'immensa_aeterni_dei_desc': 'Reorganize the Roman Curia, establishing permanent congregations of cardinals to advise the Pope on various subjects.'}
                                            )
    @cached_property
    def rival_criteria(self) -> dict[str, RivalCriteria]:
        return self.parse_advanced_entities('in_game/common/rival_criteria', RivalCriteria,)
    @cached_property
    def road_types(self) -> dict[str, RoadType]:
        return self.parse_advanced_entities('in_game/common/road_types', RoadType,
                                            # localization_prefix='', localization_suffix='', # Used in 4/4 Examples: {'modern_road': 'Modern Road', 'paved_road': 'Paved Road'}
                                            description_localization_prefix='', description_localization_suffix='_desc', # Used in 4/4 Examples: {'railroad_desc': 'The [road|e] has been upgraded to a rail connection, massively increasing travel speed and logistics.', 'modern_road_desc': 'The [road|e] has a modern flat surface and is of good quality.'}
                                            )
    @cached_property
    def scenarios(self) -> dict[str, Scenario]:
        return self.parse_advanced_entities('main_menu/common/scenarios', Scenario,
                                            description_localization_prefix='', description_localization_suffix='_desc', # Used in 9/9 Examples: {'VEN_scenario_desc': 'The Most Serene Republic of Venice is the most important and powerful of the merchant republics of the Mediterranean Sea and controls important commercial ports and islands all across it.', 'FLA_scenario_desc': 'As one of the wealthiest countries in the Low Countries, thanks to the wealthy market center of Bruges, Flanders is well-positioned to navigate the complexities of diplomacy, benefiting from its position as a middleman.'}
                                            )
    @cached_property
    def scriptable_hints(self) -> dict[str, ScriptableHint]:
        return self.parse_advanced_entities('in_game/common/scriptable_hints', ScriptableHint,
                                            allow_empty_entities=True,
                                            # localization_prefix='', localization_suffix='', # Used in 54/54 Examples: {'hint_market_out_of_supply': 'Market Out of Supply', 'hint_no_allies': 'No allies'}
                                            # localization_prefix='', localization_suffix='_administrative', # Used in 54/54 Examples: {'hint_low_stability_administrative': '\\"A nation with high stability is, of course, a nation in a state of prosperity! When harvests are plentiful, so too is the flow of wealth into our coffers.\\"', 'hint_increasing_trade_advantage_administrative': 'Core to our strategy: Predict the next wave in price through the roll of the dice and the heavenly alignment of the stars.'}
                                            # localization_prefix='', localization_suffix='_diplomatic', # Used in 54/54 Examples: {'hint_in_deficit_diplomatic': '\\"As the saying goes, we need to spend money to make money! Ensuring that our buildings and pops are profitable is the best way to turn the ship around.\\"', 'hint_has_possible_law_diplomatic': '\\"A State without Laws is a a building without pillars, a body without limbs. Better too many, than too few.\\"'}
                                            # localization_prefix='', localization_suffix='_military', # Used in 54/54 Examples: {'hint_war_exhaustion_military': '\\"War weariness may be dangerous, but it is primarily a result of poor tactics. Huge losses and significant defeats will quickly turn our people against us.\\"', 'hint_has_unmarried_adult_ruler_military': '\\"ABC\\"'}
                                            description_localization_prefix='', description_localization_suffix='_hint_text', # Used in 54/54 Examples: {'hint_estates_hint_text': '$hint_estates_hint_text_1$\\n\\n$hint_estates_hint_text_2$\\n\\n$hint_estates_hint_text_3$', 'hint_low_devotion_hint_text': '$game_concept_devotion_desc$ If it falls too low, not only will we forgo any benefits to [religious_influence|E] and reduced chance of [rebellion|E], but we will start receiving penalties to [estate|E] satisfaction.\\n\\nYou should aim to keep your devotion as high as possible in order to minimize any potential penalties.\\n\\nLike most important values, promoting religious zeal is not an overnight affair , so make sure to think long term.'}
                                            )
    @cached_property
    def scripted_country_names(self) -> dict[str, ScriptedCountryName]:
        return self.parse_advanced_entities('in_game/common/scripted_country_names', ScriptedCountryName,
                                            # localization_prefix='', localization_suffix='', # Used in 11/11 Examples: {'nova_scotia_scripted_country_name': 'Nova Scotia', 'swan_river_colony_scripted_country_name': 'Swan River'}
                                            # localization_prefix='', localization_suffix='_ADJ', # Used in 11/11 Examples: {'new_spain_scripted_country_name_ADJ': 'New Spanish', 'swan_river_colony_scripted_country_name_ADJ': 'Swan River'}
                                            )
    @cached_property
    def scripted_diplomatic_objectives(self) -> dict[str, ScriptedDiplomaticObjective]:
        return self.parse_advanced_entities('in_game/common/scripted_diplomatic_objectives', ScriptedDiplomaticObjective)
    @cached_property
    def scripted_effects(self) -> dict[str, ScriptedEffect]:
        class ScriptedEffectsWorkaround(ParsingWorkaround):
            """replaces statements like
                $effect$
            with
                _only_parameter = "$effect$"
            """
            replacement_regexes = {r'(?m)^(\s*)(\$[^$]+\$)\s*$': r'\1_only_parameter = "\2"'}

        return self.parse_advanced_entities('in_game/common/scripted_effects', ScriptedEffect,
                                            allow_empty_entities=True,
                                            parsing_workarounds=[ScriptedEffectsWorkaround()])
    @cached_property
    def scripted_lists(self) -> dict[str, ScriptedList]:
        return self.parse_advanced_entities('in_game/common/scripted_lists', ScriptedList,
                                            )
    @cached_property
    def scripted_relations(self) -> dict[str, ScriptedRelation]:
        return self.parse_advanced_entities('in_game/common/scripted_relations', ScriptedRelation,
                                            localization_prefix='', localization_suffix='_relation', # Used in 30/30 Examples: {'anti_coalition_treaty_relation': 'Anti Coalition Treaty', 'agitate_for_liberty_relation': 'Agitate for Liberty'}
                                            description_localization_prefix='', description_localization_suffix='_relation_desc', # Used in 30/30 Examples: {'block_foreign_building_relation_desc': 'A [country|e] will forbid another one from [building|e] [foreign_buildings|e] in their territory.', 'sow_discontent_relation_desc': 'A [country|e] will increase the discontent inside another country, reducing their [stability|e].'}
                                            )
    @cached_property
    def scripted_triggers(self) -> dict[str, ScriptedTrigger]:
        triggers = self.parse_advanced_entities('main_menu/common/scripted_triggers', ScriptedTrigger)
        triggers.update(self.parse_advanced_entities('in_game/common/scripted_triggers', ScriptedTrigger))
        return triggers
    @cached_property
    def situations(self) -> dict[str, Situation]:
        return self.parse_advanced_entities('in_game/common/situations', Situation,
                                            # localization_prefix='', localization_suffix='', # Used in 22/22 Examples: {'western_schism': 'Western Schism', 'little_ice_age': 'Little Ice Age'}
                                            description_localization_prefix='', description_localization_suffix='_desc', # Used in 22/22 Examples: {'treaty_of_tordesillas_desc': "This treaty was signed in [GetSituationByKey('treaty_of_tordesillas').MakeScope.GetVariable('treaty_location').GetLocation.GetName] by the [GetSituationByKey('treaty_of_tordesillas').MakeScope.GetVariable('var_east_country').GetCountry.GetLongName] and the [GetSituationByKey('treaty_of_tordesillas').MakeScope.GetVariable('var_west_country').GetCountry.GetLongName]. It establishes a set of rules and rights that allow the two powers to claim exclusive rights to the colonization and exploitation of any newly discovered lands on the continent of [ShowContinentName('america')].", 'fall_of_delhi_desc': "A century of overextension and a crumbling central authority have hurt the rule and reputation of the mighty [GetCountry('DLH').GetName]. Beyond their borders are vultures and enemies, waiting to strike at any moment. The great [GetCountry('DLH').GetFlavorRank] of their forefathers will be brought to its knees in but an instant lest they succeed in safeguarding their people from internal and external threats."}
                                            # localization_prefix='', localization_suffix='_info', # Used in 6/22 Examples: {'hundred_years_war_info': "This is a conflict that will create [wars|e] between [GetCountry('ENG').GetName] and [GetCountry('FRA').GetName] until one side has reached their goals.", 'great_pestilence_info': "[ROOT.GetVariable('great_pestilence_origin').GetLocation.GetName]"}
                                            # localization_prefix='', localization_suffix='_monthly', # Used in 3/22 Examples: {'hundred_years_war_monthly': 'If there is [peace|e] there is a chance of either side restarting the conflict.', 'black_death_monthly': '• This plague will spread to nearby [locations|e], and across trade-routes\\n• It will kill many [pops|E], [armies|e] and [characters|E] where it has spread'}
                                            )

    def _parse_societal_value_one_side(self, side: str, societal_value_name: str, data: Tree) -> SocietalValueOneSide:
        name = f'{societal_value_name}_{side}'
        left, _vs, right = societal_value_name.partition('_vs_')
        if side == 'left':
            short_name = left
        else:
            short_name = right
        display_name = self.localize(f'{short_name}_focus')
        modifier = self.parse_modifier_section(societal_value_name, data, f'{side}_modifier', Eu5Modifier)
        return SocietalValueOneSide(name, display_name, short_name=short_name, modifier=modifier, side=side)

    @cached_property
    def societal_values(self) -> dict[str, SocietalValue]:
        return self.parse_advanced_entities('in_game/common/societal_values', SocietalValue,
                                            # localization_prefix='', localization_suffix='', # Used in 16/16 Examples: {'traditionalist_vs_innovative': 'Traditionalist vs Innovative', 'spiritualist_vs_humanist': 'Spiritualist vs Humanist'}
                                            description_localization_prefix='', description_localization_suffix='_desc', # Used in 16/16 Examples: {'capital_economy_vs_traditional_economy_desc': 'A [country|e] with a capital economy is more focused on earning money, particularly from [trade|e] and [towns_and_cities|e], while one with a traditional economy is more oriented about living off what the land provides.', 'serfdom_vs_free_subjects_desc': 'A country with high serfdom is about exploiting the peasants as much as possible, whereas a country with free subjects treats peasants as human beings.'}
                                            extra_data_functions= {
                                                'left': lambda name, data: self._parse_societal_value_one_side('left', name, data),
                                                'right': lambda name, data: self._parse_societal_value_one_side('right', name, data),
                                            }
                                            )
    @cached_property
    def subject_military_stances(self) -> dict[str, SubjectMilitaryStance]:
        return self.parse_advanced_entities('in_game/common/subject_military_stances', SubjectMilitaryStance,
                                            # localization_prefix='', localization_suffix='', # Used in 5/5 Examples: {'defensive_military_stance': 'Defensive', 'supportive_military_stance': 'Supportive'}
                                            description_localization_prefix='', description_localization_suffix='_desc', # Used in 5/5 Examples: {'normal_military_stance_desc': 'The [subject|e] will take a balanced approach to military tactics.', 'supportive_military_stance_desc': 'The [subject|e] will take a supportive approach to military tactics, helping your units.'}
                                            # description_localization_prefix='', description_localization_suffix='_desc_all', # Used in 5/5 Examples: {'supportive_military_stance_desc_all': 'All our [subjects|e] will take a supportive approach to military tactics, helping your units.', 'passive_military_stance_desc_all': 'All our [subjects|e] will take a passive approach to military tactics, doing low-risk actions like blockading as well as defending friendly territory.'}
                                            )
    @cached_property
    def subject_types(self) -> dict[str, SubjectType]:
        return self.parse_advanced_entities('in_game/common/subject_types', SubjectType,
                                            # localization_prefix='', localization_suffix='', # Used in 19/19 Examples: {'tributary': 'Tributary', 'appanage': 'Appanage'}
                                            description_localization_prefix='', description_localization_suffix='_desc', # Used in 19/19 Examples: {'trade_company_desc': "A $trade_company$ is an investment conglomerate, directed at incurring monetary benefits for itself and its [overlord|e]. They are always a [ShowGovernmentTypeName('republic')] and get increased [ShowModifierTypeName('trade_efficiency')], as well as increased payment obligations to their overlord compared to a regular [ShowSubjectTypeName('vassal')].", 'dominion_desc': "A $dominion$ is a self-governed [subject|e] with relative autonomy, exclusive for a [ShowGovernmentTypeName('monarchy')] of the same [religion_group|e] as the [overlord|e]. Additionally, to be able to create a $dominion$, both countries must be in a [union|e] or the overlord must be either $ENG$ or $GBR$. A $dominion$ enjoys increased [ShowModifierTypeName('country_cabinet_efficiency')], a bigger increase compared to a regular [ShowSubjectTypeName('vassal')]."}
                                            )
    @cached_property
    def town_setups(self) -> dict[str, TownSetup]:
        return self.parse_advanced_entities('in_game/common/town_setups', TownSetup)
    @cached_property
    def traits(self) -> dict[str, Trait]:
        return self.parse_advanced_entities('in_game/common/traits', Trait,
                                            # localization_prefix='', localization_suffix='', # Used in 102/102 Examples: {'cruel': 'Cruel', 'child_gallant': 'Gallant'}
                                            description_localization_prefix='desc_', description_localization_suffix='', # Used in 102/102 Examples: {'desc_naval_showman': 'This Admiral is a Naval Showman. [ships|e] commanded by this leader will receive more prestige and naval tradition from battles.', 'desc_naval_gunner': 'This Admiral is known as a Naval Gunner. Constant drill of gunnery crews commanded by this leader means heavy [ships|e] will deal more damage.'}
                                            # description_localization_prefix='', description_localization_suffix='_die_desc', # Used in 102/102 Examples: {'child_intelligent_die_desc': "[CHARACTER.GetName]'s passing is mourned and also felt as a loss of a very capable person.", 'buccaneer_die_desc': 'With [CHARACTER.GetHerHim] gone our enemies will feel safer with the shipping lanes again.'}
                                            )
    @cached_property
    def trait_flavor(self) -> dict[str, TraitFlavor]:
        return self.parse_advanced_entities('in_game/common/trait_flavor', TraitFlavor)
    @cached_property
    def trigger_localization(self) -> dict[str, TriggerLocalization]:
        return self.parse_advanced_entities('in_game/common/trigger_localization', TriggerLocalization, extra_data_functions={
            'global_': lambda name, data: data['global'] if 'global' in data else '',
        })
    @cached_property
    def unit_abilities(self) -> dict[str, UnitAbility]:
        return self.parse_advanced_entities('in_game/common/unit_abilities', UnitAbility,
                                            # localization_prefix='', localization_suffix='', # Used in 14/14 Examples: {'gather_food': 'Gather Food', 'raid_clan_holdings': 'Raid Clan Holdings'}
                                            description_localization_prefix='', description_localization_suffix='_desc', # Used in 14/14 Examples: {'gather_food_desc': 'Our soldiers will gather food instead of focusing on their duties.', 'hire_prisoners_as_mercenaries_desc': 'This will bribe the [prisoners|e] to fight for our [country|e] as a band of [mercenaries|e].'}
                                            )
    @cached_property
    def unit_categories(self) -> dict[str, UnitCategory]:
        return self.parse_advanced_entities('in_game/common/unit_categories', UnitCategory,
                                            # localization_prefix='', localization_suffix='', # Used in 8/8 Examples: {'army_cavalry': 'Cavalry', 'army_auxiliary': 'Auxiliary'}
                                            description_localization_prefix='', description_localization_suffix='_desc', # Used in 8/8 Examples: {'army_artillery_desc': 'Range weapons managed by a crew of specialists that launch projectiles mainly meant for the breaching and destruction of fortifications. ', 'navy_light_ship_desc': 'Light Ships are small and relatively cheap vessels with a shallow keel that focus on speed, agility and ease of navigation.'}
                                            )

    def _parse_mercenaries_per_location(self, data):
        if not isinstance(data, list):
            data = [data]
        # return [{self.pop_types[pop_type]: factor} for tree in data for pop_type, factor in tree]
        return [{self.pop_types[tree['pop_type']]: tree['multiply']} for tree in data]
        r = []
        for tree in data:
            a = {}
            # for pop_type, factor in tree:
            a[self.pop_types[tree['pop_type']]] = tree['multiply']
            r.append(a)
        return r
        # return [{self.pop_types[pop_type]: factor} ]

    @cached_property
    def unit_types(self) -> dict[str, UnitType]:
        return self.parse_advanced_entities('in_game/common/unit_types', UnitType,
                                            # localization_prefix='', localization_suffix='', # Used in 265/265 Examples: {'n_kilwan_dhow': '$ZAN_ADJ$ Dhow', 'n_square_rigged_caravel': 'Square-Rigged Caravel'}
                                            description_localization_prefix='', description_localization_suffix='_desc', # Used in 265/265 Examples: {'n_age_4_reformation_galley_desc': '$unit_template_desc$', 'a_men_at_arms_desc': 'Armored footmen outfitted with a medley of hand-to-hand weapons, $a_men_at_arms$ are heavy melee infantry who can break through enemy formations.'}
                                            transform_value_functions={
                                                'mercenaries_per_location': self._parse_mercenaries_per_location,
                                                # so that the parser passes the value through even though copy_from and upgrades_to_only are not attributes
                                                'copy_from': lambda c: c,
                                                'upgrades_to_only': lambda c: c,
                                            },
                                            )
    @cached_property
    def wargoals(self) -> dict[str, Wargoal]:
        return self.parse_advanced_entities('in_game/common/wargoals', Wargoal,
                                            localization_prefix='war_goal_', # Used in 53/53 Examples: {'war_goal_hundred_years_war_wargoal': 'Win The Hundred Years War', 'war_goal_clan_expansion_wargoal': 'Clan Expansion'}
                                            description_localization_prefix='war_goal_', description_localization_suffix='_desc', # Used in 53/53 Examples: {'war_goal_take_country_desc': '[war_goal|e] is to take the enemy country. Get bonus [war_score|e] from winning sieges of enemy fortifications and from occupying enemy territory.', 'war_goal_take_capital_imperial_desc': "[war_goal|e] is to take Emperor's Capital."}
                                            )