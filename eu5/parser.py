import inspect
from pathlib import Path
from functools import cached_property
import sys
from typing import Callable, TypeVar, Type

from PyHelpersForPDXWikis.localsettings import EU5DIR
from eu5.eu5lib import Eu5GameConcept
from common.jomini_parser import JominiParser
from common.paradox_lib import GameConcept
from common.paradox_parser import ParadoxParser
from stellaris.stellaris.specimen import description


class Eu5Parser(JominiParser):


    def __init__(self, game_installation: Path = EU5DIR):
        super().__init__(game_installation / 'game' )
        self.localization_folder_iterator = (game_installation / 'game' / 'main_menu' / 'localization' / 'english').glob('**/*_l_english.yml')

    @cached_property
    def formatter(self):
        from eu5.text_formatter import Eu5WikiTextFormatter
        return Eu5WikiTextFormatter()

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

    def parse_dlc_from_conditions(self, conditions):
        pass
