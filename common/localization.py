import re
from functools import cached_property
from typing import Iterator

class Localizer:
    # allows the overriding of localization strings
    localizationOverrides = {}

    localization_folder_iterator: Iterator


    @cached_property
    def _localization_dict(self) -> dict[str, str]:
        return {}

    def localize(self, key: str, default: str = None, return_none_instead_of_default=False) -> str|None:
        """localize the key from the english localization files

        if the key is not found, the behavior depends on return_none_instead_of_default:
            if it is true, None is returned
            if it is false, the default is returned unless it is None in which case the key is returned
        """

        if key in self.localizationOverrides:
            return self.localizationOverrides[key]
        elif key in self._localization_dict:
            return self._localization_dict[key]
        else:
            if return_none_instead_of_default:
                return None
            elif default is None:
                return key
            else:
                return default

class JominiLocalizer(Localizer):

    @cached_property
    def _localization_dict(self) -> dict[str, str]:
        localization_dict = {}
        for path in self.localization_folder_iterator:
            with path.open(encoding='utf-8-sig') as f:
                for line in f:
                    match = re.fullmatch(r'\s*([^#\s:]+):\d?\s*"(.*)"[^"]*', line)
                    if match:
                        localization_dict[match.group(1)] = match.group(2)
        return localization_dict