
try:
    # when used by PyHelpersForPDXWikis
    from PyHelpersForPDXWikis.localsettings import EU4DIR
except: # when used by ck2utils
    from localpaths import eu4dir
    EU4DIR = eu4dir
from common.paradox_lib import Game
from common.file_generator import FileGenerator
from common.wiki import WikiTextFormatter
from eu4.parser import Eu4Parser

class EuropaUniversalisIV(Game):
    short_game_name = 'eu4'
    game_path = EU4DIR
    launcher_settings = game_path / 'launcher-settings.json'

    def __init__(self):
        """Never construct this object manually. Use the variable eu4game instead.
        This way all data can be cached without having to pass on references to the game or the parser"""
        self.parser = Eu4Parser


eu4game = EuropaUniversalisIV()


class Eu4FileGenerator(FileGenerator):

    parser: Eu4Parser

    def __init__(self):
        super().__init__(eu4game)

    @staticmethod
    def create_wiki_list(elements: list[str], indent=1) -> str:
        return WikiTextFormatter.create_wiki_list(elements, indent)
