from enum import Enum, Flag
from functools import cached_property
from operator import attrgetter


class CS2BaseEnum(Enum):
    def __bool__(self):
        # treat _None as false
        return self.name != '_None'

    @cached_property
    def display_name(self) -> str:
        from cs2.game import cs2game
        return cs2game.localizer.localize_enum(self)


class CS2BaseFlag(Flag, CS2BaseEnum):
    def __iter__(self):
        """for backwards compatibility with python versions below 3.11"""
        for flag in sorted(self.__class__, key=attrgetter('display_name')):
            if flag and flag in self:
                yield flag


class DLC(Enum):
    """This is not an enum in C#. Instead, it is the class Game.Dlc.Dlc. But the numbers are used to reference
    the DLCs in several places and that's why it is represented as an enum here"""
    PdxLoginRequirement = -2  # not a real DLC, but it is used in a similar way
    BaseGame = -1  # to simplify code
    LandmarkBuildings = 0
    SanFranciscoSet = 1
    CS1TreasureHunt = 2
    BeachProperties = 3
    DeluxeRelaxRadio = 4

    def __str__(self):
        return self.name

    @cached_property
    def display_name(self):
        """Hardcoded names, because I didnt find them anywhere in the files"""
        return {'PdxLoginRequirement': 'Paradox login',
                'BaseGame': '',
                'LandmarkBuildings': 'Landmark Buildings',
                'SanFranciscoSet': 'San Francisco Set',
                'CS1TreasureHunt': 'Treasure Hunt',
                'BeachProperties': 'Beach Properties',
                'DeluxeRelaxRadio': 'Deluxe Relax Station',
                }[self.name]

    @cached_property
    def icon(self):
        if self == DLC.BaseGame:
            return ''
        return '{{icon|' + {'PdxLoginRequirement': 'pdxlogin',
                            'LandmarkBuildings': 'preorder',
                            'SanFranciscoSet': 'sfc',
                            'CS1TreasureHunt': 'Treasure Hunt',
                            'BeachProperties': 'bp'
                            }[self.name] + '}}'

