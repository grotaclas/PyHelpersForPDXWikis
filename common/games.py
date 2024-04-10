from aow4.game import aow4game
from common.paradox_lib import Game
from cs2.game import cs2game
from eu4.eu4_file_generator import eu4game
from millennia.game import millenniagame
from vic3.game import vic3game

# Generic game classes which have wikis, but no code implementation
class EmpireofSin(Game):
    """Never construct this object manually. Use the variable eosgame instead.
    This way all data can be cached without having to pass on references to the game or the parser"""
    name = 'Empire of Sin'
    short_game_name = 'eos'
    wiki_domain = 'eos.paradoxwikis.com'


eosgame = EmpireofSin()


class SurvivingtheAftermath(Game):
    """Never construct this object manually. Use the variable stagame instead.
    This way all data can be cached without having to pass on references to the game or the parser"""
    name = 'Surviving the Aftermath'
    short_game_name = 'sta'
    wiki_domain = 'sta.paradoxwikis.com'


stagame = SurvivingtheAftermath()


class CrusaderKings2(Game):
    """Never construct this object manually. Use the variable ck2game instead.
    This way all data can be cached without having to pass on references to the game or the parser"""
    name = 'Crusader Kings 2'
    short_game_name = 'ck2'
    wiki_domain = 'ck2.paradoxwikis.com'


ck2game = CrusaderKings2()


class ArsenalofDemocracy(Game):
    """Never construct this object manually. Use the variable aodgame instead.
    This way all data can be cached without having to pass on references to the game or the parser"""
    name = 'Arsenal of Democracy'
    short_game_name = 'aod'
    wiki_domain = 'aod.paradoxwikis.com'


aodgame = ArsenalofDemocracy()


class EuropaUniversalis2(Game):
    """Never construct this object manually. Use the variable eu2game instead.
    This way all data can be cached without having to pass on references to the game or the parser"""
    name = 'Europa Universalis 2'
    short_game_name = 'eu2'
    wiki_domain = 'eu2.paradoxwikis.com'


eu2game = EuropaUniversalis2()


class EuropaUniversalis3(Game):
    """Never construct this object manually. Use the variable eu3game instead.
    This way all data can be cached without having to pass on references to the game or the parser"""
    name = 'Europa Universalis 3'
    short_game_name = 'eu3'
    wiki_domain = 'eu3.paradoxwikis.com'


eu3game = EuropaUniversalis3()


class EuropaUniversalisRome(Game):
    """Never construct this object manually. Use the variable euromegame instead.
    This way all data can be cached without having to pass on references to the game or the parser"""
    name = 'Europa Universalis: Rome'
    short_game_name = 'eurome'
    wiki_domain = 'eurome.paradoxwikis.com'


euromegame = EuropaUniversalisRome()


class HeartsofIron2(Game):
    """Never construct this object manually. Use the variable hoi2game instead.
    This way all data can be cached without having to pass on references to the game or the parser"""
    name = 'Hearts of Iron 2'
    short_game_name = 'hoi2'
    wiki_domain = 'hoi2.paradoxwikis.com'


hoi2game = HeartsofIron2()


class HeartsofIron3(Game):
    """Never construct this object manually. Use the variable hoi3game instead.
    This way all data can be cached without having to pass on references to the game or the parser"""
    name = 'Hearts of Iron 3'
    short_game_name = 'hoi3'
    wiki_domain = 'hoi3.paradoxwikis.com'


hoi3game = HeartsofIron3()


class SteelDivision(Game):
    """Never construct this object manually. Use the variable steeldivisiongame instead.
    This way all data can be cached without having to pass on references to the game or the parser"""
    name = 'Steel Division'
    short_game_name = 'steeldivision'
    wiki_domain = 'steeldivision.paradoxwikis.com'


steeldivisiongame = SteelDivision()


class Tyranny(Game):
    """Never construct this object manually. Use the variable tyrannygame instead.
    This way all data can be cached without having to pass on references to the game or the parser"""
    name = 'Tyranny'
    short_game_name = 'tyranny'
    wiki_domain = 'tyranny.paradoxwikis.com'


tyrannygame = Tyranny()


class Victoria1(Game):
    """Never construct this object manually. Use the variable vic1game instead.
    This way all data can be cached without having to pass on references to the game or the parser"""
    name = 'Victoria 1'
    short_game_name = 'vic1'
    wiki_domain = 'vic1.paradoxwikis.com'


vic1game = Victoria1()


class Victoria2(Game):
    """Never construct this object manually. Use the variable vic2game instead.
    This way all data can be cached without having to pass on references to the game or the parser"""
    name = 'Victoria 2'
    short_game_name = 'vic2'
    wiki_domain = 'vic2.paradoxwikis.com'


vic2game = Victoria2()


class CitiesSkylines(Game):
    """Never construct this object manually. Use the variable skylinesgame instead.
    This way all data can be cached without having to pass on references to the game or the parser"""
    name = 'Cities: Skylines'
    short_game_name = 'skylines'
    wiki_domain = 'skylines.paradoxwikis.com'


skylinesgame = CitiesSkylines()


class CrusaderKings3(Game):
    """Never construct this object manually. Use the variable ck3game instead.
    This way all data can be cached without having to pass on references to the game or the parser"""
    name = 'Crusader Kings 3'
    short_game_name = 'ck3'
    wiki_domain = 'ck3.paradoxwikis.com'


ck3game = CrusaderKings3()


class HeartsofIron4(Game):
    """Never construct this object manually. Use the variable hoi4game instead.
    This way all data can be cached without having to pass on references to the game or the parser"""
    name = 'Hearts of Iron 4'
    short_game_name = 'hoi4'
    wiki_domain = 'hoi4.paradoxwikis.com'


hoi4game = HeartsofIron4()


class ImperatorRome(Game):
    """Never construct this object manually. Use the variable imperatorgame instead.
    This way all data can be cached without having to pass on references to the game or the parser"""
    name = 'Imperator: Rome'
    short_game_name = 'imperator'
    wiki_domain = 'imperator.paradoxwikis.com'


imperatorgame = ImperatorRome()


class PrisonArchitect(Game):
    """Never construct this object manually. Use the variable prisonarchitectgame instead.
    This way all data can be cached without having to pass on references to the game or the parser"""
    name = 'Prison Architect'
    short_game_name = 'prisonarchitect'
    wiki_domain = 'prisonarchitect.paradoxwikis.com'


prisonarchitectgame = PrisonArchitect()


class Stellaris(Game):
    """Never construct this object manually. Use the variable stellarisgame instead.
    This way all data can be cached without having to pass on references to the game or the parser"""
    name = 'Stellaris'
    short_game_name = 'stellaris'
    wiki_domain = 'stellaris.paradoxwikis.com'


stellarisgame = Stellaris()


class SurvivingMars(Game):
    """Never construct this object manually. Use the variable survivingmarsgame instead.
    This way all data can be cached without having to pass on references to the game or the parser"""
    name = 'Surviving Mars'
    short_game_name = 'survivingmars'
    wiki_domain = 'survivingmars.paradoxwikis.com'


survivingmarsgame = SurvivingMars()


class VampireTheMasquerade(Game):
    """Never construct this object manually. Use the variable vtmgame instead.
    This way all data can be cached without having to pass on references to the game or the parser"""
    name = 'Vampire: The Masquerade'
    short_game_name = 'vtm'
    wiki_domain = 'vtm.paradoxwikis.com'


vtmgame = VampireTheMasquerade()


class AoWPlanetfall(Game):
    """Never construct this object manually. Use the variable aowplanetfallgame instead.
    This way all data can be cached without having to pass on references to the game or the parser"""
    name = 'AoW: Planetfall'
    short_game_name = 'aowplanetfall'
    wiki_domain = 'aowplanetfall.paradoxwikis.com'


aowplanetfallgame = AoWPlanetfall()

# mapping of existing games by their short names
all_games: dict[str, Game] = {game.short_game_name: game for game in [
    eu4game, vic3game, aow4game, cs2game, millenniagame,  # actually implemented
    eosgame, stagame, ck2game, aodgame, eu2game, eu3game, euromegame, hoi2game, hoi3game, steeldivisiongame,
    tyrannygame, vic1game, vic2game, skylinesgame, ck3game, hoi4game, imperatorgame, prisonarchitectgame,
    stellarisgame, survivingmarsgame, vtmgame, aowplanetfallgame]}


