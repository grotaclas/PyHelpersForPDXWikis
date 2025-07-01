import inspect
from pathlib import Path
from functools import cached_property, reduce
import sys
from typing import Callable, TypeVar, Type

from PyHelpersForPDXWikis.localsettings import EU5DIR
from common.file_generator import FileGenerator
from eu5.eu5lib import *
from common.jomini_parser import JominiParser
from common.paradox_lib import GameConcept, NE, AE
from common.paradox_parser import ParadoxParser, ParsingWorkaround


class Eu5Parser(JominiParser):

    # allows the overriding of localization strings
    localizationOverrides = {
        # the default is "Trade Embark/Disembark Cost" which is problematic for redirects and filenames, because of the slash
        'MODIFIER_TYPE_NAME_local_trade_embark_disembark_cost_modifier': 'Trade Embark-Disembark Cost',
        'hanseatic_town_hall_price': "$hanseatic_town_hall$ Price",  # avoid recursion TODO: remove workaround when the loc is fixed ingame
    }

    def __init__(self, game_installation: Path = EU5DIR, language: str = 'english'):
        super().__init__(game_installation / 'game' )
        self.localization_folder_iterator = (game_installation / 'game' / 'main_menu' / 'localization' / language).glob(f'**/*_l_{language}.yml')

    @cached_property
    def formatter(self):
        from eu5.text_formatter import Eu5WikiTextFormatter
        return Eu5WikiTextFormatter()

    def parse_nameable_entities(self, folder: str, entity_class: Type[NE], extra_data_functions: dict[str, Callable[[str, Tree], any]] = None,
                                transform_value_functions: dict[str, Callable[[any], any]] = None, entity_level: int = 0,
                                level_headings_keys: dict[str, 0] = None, parsing_workarounds: list[ParsingWorkaround] = None, localization_prefix: str = '',
                                allow_empty_entities=False) -> dict[str, NE]:
        if extra_data_functions is None:
            extra_data_functions = {}
        if 'display_name' not in extra_data_functions:
            extra_data_functions['display_name'] = lambda entity_name, entity_data: self.formatter.strip_formatting(
                self.localize(localization_prefix + entity_name), strip_newlines=True)
        return super().parse_nameable_entities(folder, entity_class, extra_data_functions, transform_value_functions, entity_level, level_headings_keys,
                                               parsing_workarounds, localization_prefix, allow_empty_entities)

    def parse_advanced_entities(self, folder: str, entity_class: Type[AE], extra_data_functions: dict[str, Callable[[str, Tree], any]] = None,
                                transform_value_functions: dict[str, Callable[[any], any]] = None, localization_prefix: str = '') -> dict[str, AE]:
        if extra_data_functions is None:
            extra_data_functions = {}
        if 'description' not in extra_data_functions:
            extra_data_functions['description'] = lambda name, data: self.formatter.format_localization_text(self.localize(localization_prefix + name + '_desc'))
        return super().parse_advanced_entities(folder, entity_class, extra_data_functions, transform_value_functions, localization_prefix)

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
    def modifier_types(self) -> dict[str, Eu5ModifierType]:
        return self.parse_nameable_entities('main_menu/common/modifier_types', Eu5ModifierType,
                                            allow_empty_entities=True,
                                            extra_data_functions={
            'parser': lambda name, data: self,
            'icon_file': lambda name, data: self.modifier_icons.get_or_default(name, Tree({})).get_or_default('positive', None),
            'negative_icon_file': lambda name, data: self.modifier_icons.get_or_default(name, Tree({})).get_or_default('negative', None),
        })

    def parse_modifier_section_from_wiki_section_ame(self, wiki_section_name: str) -> list[Eu5Modifier]:
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
    def buildings(self):
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
    def defines(self):
        # TODO: add defines from jomini folder

        class SemicolonLineEndWorkaround(ParsingWorkaround):
            """replaces statements like
                pattern = list "christian_emblems_list"
            with
                pattern = { list "christian_emblems_list" }
            """
            replacement_regexes = {r'(?m)^([^#]*?);(\s*(#.*)?)$': r'\1 \2'}


        return self.parser.parse_folder_as_one_file('loading_screen/common/defines', workarounds=[SemicolonLineEndWorkaround()]).merge_duplicate_keys()

    def get_define(self, define: str):
        """get a define by its game syntax e.g. NGame.START_DATE"""
        result = self.defines
        for part in define.split('.'):
            result = result[part]
        return result

    @cached_property
    def estate_privileges(self):
        return self.parse_advanced_entities('in_game/common/estate_privileges', EstatePrivilege)

    @cached_property
    def game_concepts(self):
        """Includes the aliases as well"""
        concepts = self.parse_advanced_entities('main_menu/common/game_concepts', Eu5GameConcept, localization_prefix='game_concept_')
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
    def goods(self):
        return self.parse_advanced_entities('in_game/common/goods', Good)

    @cached_property
    def goods_demand(self):
        return self.parse_nameable_entities('in_game/common/goods_demand', GoodsDemand, extra_data_functions={
            'demands': lambda name, data: [Cost.create_with_goods(key, value) for key, value in data if key in self.goods],
        })

    @cached_property
    def laws(self):
        return self.parse_advanced_entities('in_game/common/laws', Law, extra_data_functions={
            'policies': self._parse_law_policies,
        })

    def _parse_law_policies(self, name: str, data: Tree) -> list[LawPolicy]:
        possible_law_attributes = Law.all_annotations().keys()
        policy_data = data.filter_elements(lambda k, v: k not in possible_law_attributes)
        return self.parse_advanced_entities(policy_data, LawPolicy)


    def parse_dlc_from_conditions(self, conditions):
        pass

    @cached_property
    def prices(self):
        return self.parse_nameable_entities('in_game/common/prices', Price, extra_data_functions={
            'costs': lambda name, data: [Cost.create_with_hardcoded_resource(key, value) for key, value in data if key in HardcodedResource]
        })

    @cached_property
    def production_methods(self):
        return self._parse_production_methods('in_game/common/production_methods')

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
    def script_values(self):
        result = self.parser.parse_folder_as_one_file('main_menu/common/script_values')
        result.update(self.parser.parse_folder_as_one_file('in_game/common/script_values'))
        result.merge_duplicate_keys()
        return result
