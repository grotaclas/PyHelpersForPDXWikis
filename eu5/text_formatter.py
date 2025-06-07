import re

from eu5.game import eu5game
from vic3.text_formatter import Vic3WikiTextFormatter


class Eu5WikiTextFormatter(Vic3WikiTextFormatter):

    def __init__(self):
        self.parser = eu5game.parser

    def localize_concept_name(self, concept_name):
        return self.parser.localize('game_concept_' + concept_name)

    def _replace_icons(self, match: re.Match) -> str:
        icon_key = match.group(1).lower().replace('_', ' ')
        return f'{{{{icon|{icon_key}}}}}'

    def apply_localization_formatting(self, text: str) -> str:
        text = super().apply_localization_formatting(text)
        text = re.sub(r"\[\s*Show[a-zA-Z_]+\s*\(\s*'(?P<loc_key>[^']+)'\s*\)\s*]",
                      lambda match: self.parser.localize(match.group('loc_key')), text)
        text = re.sub(r"\[\s*Get[a-zA-Z_]+\s*\(\s*'(?P<loc_key>[^']+)'\s*\).GetNameWithNoTooltip\s*]",
                      lambda match: self.parser.localize(match.group('loc_key')), text)
        return text
