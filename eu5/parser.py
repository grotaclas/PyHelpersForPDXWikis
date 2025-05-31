import inspect
from pathlib import Path
from functools import cached_property
import sys
from typing import Callable, TypeVar, Type

from PyHelpersForPDXWikis.localsettings import EU5DIR
from eu5.eu5lib import *
from common.jomini_parser import JominiParser
from common.paradox_lib import GameConcept
from common.paradox_parser import ParadoxParser, ParsingWorkaround


class Eu5Parser(JominiParser):


    def __init__(self, game_installation: Path = EU5DIR):
        super().__init__(game_installation / 'game' )
        self.localization_folder_iterator = (game_installation / 'game' / 'main_menu' / 'localization' / 'english').glob('**/*_l_english.yml')

    @cached_property
    def formatter(self):
        from eu5.text_formatter import Eu5WikiTextFormatter
        return Eu5WikiTextFormatter()

    @cached_property
    def modifier_types(self) -> dict[str, ModifierType]:
        return self.parse_nameable_entities('main_menu/common/modifier_types', Eu5ModifierType, extra_data_functions={'parser': lambda name, data: self})

    @cached_property
    def buildings(self):
        return self.parse_advanced_entities('in_game/common/building_types', Building,
                                            transform_value_functions={
                                                'build_time': lambda value: self.script_values[value] if isinstance(value, str) else value,
                                                'employment_size': lambda value: self.script_values[value] if isinstance(value, str) else value,
                                            })

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

    def parse_dlc_from_conditions(self, conditions):
        pass

    @cached_property
    def script_values(self):
        result = self.parser.parse_folder_as_one_file('main_menu/common/script_values')
        result.update(self.parser.parse_folder_as_one_file('in_game/common/script_values'))
        result.merge_duplicate_keys()
        return result
