import json
import re
from functools import cached_property

from PyHelpersForPDXWikis.localsettings import CS2DIR
from common.paradox_lib import Game
from cs2.localization import CS2Localization


class CitiesSkylines2(Game):
    """Never construct this object manually. Use the variable cs2game instead.
    This way all data can be cached without having to pass on references to the game or the parser"""
    name = 'Cities: Skylines II'
    short_game_name = 'cs2'
    game_path = CS2DIR
    launcher_settings = game_path / 'Launcher/launcher-settings.json'
    wiki_domain = 'cs2.paradoxwikis.com'

    @cached_property
    def parser(self):
        """returns the shared CS2Parser"""

        # the import has to be inside this method to allow indirect circular dependencies if an entity which is
        # generated by the parser needs to call a method from the parser
        from cs2.parser import CS2Parser
        return CS2Parser()

    @cached_property
    def localizer(self) -> CS2Localization:
        """returns the shared localizer"""
        return CS2Localization()

    @cached_property
    def version(self):
        """The version string from the launcher setttings"""
        json_object = json.load(open(self.launcher_settings, encoding='utf-8'))
        return json_object['version']

    @cached_property
    def full_version(self):
        """the build version from boot.config"""
        config_path = self.game_path / 'Cities2_Data' / 'boot.config'
        with open(config_path, 'r') as config_file:
            match = re.search(r'^build-guid=([0-9a-f]{32})$', config_file.read(), flags=re.MULTILINE)
            if match:
                return self.version + '-' + match.group(1)
            else:
                raise Exception(f'No "build-guid" found in "{config_path}"')


cs2game = CitiesSkylines2()
