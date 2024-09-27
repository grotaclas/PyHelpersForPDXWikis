import re
from functools import cached_property
from typing import Iterator

from common.paradox_parser import ParadoxParser


class JominiParser:
    """Shared functions between newer paradox games like ck3 and vic3"""

    # allows the overriding of localization strings
    localizationOverrides = {}

    localization_folder_iterator: Iterator

    def __init__(self, game_path):
        self.parser = ParadoxParser(game_path)

    @cached_property
    def _localization_dict(self):
        localization_dict = {}
        for path in self.localization_folder_iterator:
            with path.open(encoding='utf-8-sig') as f:
                for line in f:
                    match = re.fullmatch(r'\s*([^#\s:]+):\d?\s*"(.*)"[^"]*', line)
                    if match:
                        localization_dict[match.group(1)] = match.group(2)
        return localization_dict

    def localize(self, key: str, default: str = None) -> str:
        """localize the key from the english localization files

        if the key is not found, the default is returned
        unless it is None in which case the key is returned
        """
        if default is None:
            default = key

        if key in self.localizationOverrides:
            return self.localizationOverrides[key]
        else:
            return self._localization_dict.get(key, default)