from functools import cached_property

from PyHelpersForPDXWikis.localsettings import VIC3DIR
from common.paradox_lib import Game


class Victoria3(Game):
    """Never construct this object manually. Use the variable vic3game instead.
    This way all data can be cached without having to pass on references to the game or the parser"""
    short_game_name = 'vic3'
    game_path = VIC3DIR
    launcher_settings = game_path / 'launcher/launcher-settings.json'

    @cached_property
    def parser(self) -> 'Vic3Parser':
        """returns the shared Vic3Parser"""

        # the import has to be inside this method to allow indirect circular dependencies if an entity which is
        # generated by the parser needs to call a method from the parser
        from vic3.parser import Vic3Parser
        return Vic3Parser()


vic3game = Victoria3()
