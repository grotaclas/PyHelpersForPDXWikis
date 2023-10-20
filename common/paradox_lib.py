import json
import re
from typing import Any

from colormath.color_conversions import convert_color
from colormath.color_objects import sRGBColor, HSVColor
from functools import cached_property
from pathlib import Path

from common.paradox_parser import Tree
try:
    # when used by PyHelpersForPDXWikis
    from PyHelpersForPDXWikis.localsettings import CACHEPATH
except:  # when used by ck2utils
    from localpaths import cachedir
    CACHEPATH = cachedir


class Game:
    """Represents a paradox game with an installation location (game_path) and holds a reference to the game
    specific parser.

    Has functions to extract the version number of the game from the launcher-settings.json which is used
    by the paradox launcher"""

    # these properties have to be set by the subclasses
    name: str
    short_game_name: str
    game_path: Path
    launcher_settings: Path
    wiki_domain: str
    parser: Any

    @cached_property
    def version(self):
        json_object = json.load(open(self.launcher_settings, encoding='utf-8'))
        self.full_version = json_object['version']
        return json_object['rawVersion']

    @cached_property
    def full_version(self):
        json_object = json.load(open(self.launcher_settings, encoding='utf-8'))
        self.version = json_object['rawVersion']
        return json_object['version']

    @cached_property
    def major_version(self):
        return '.'.join(self.version.split('.')[0:2])

    @cached_property
    def cachepath(self) -> Path | None:
        if CACHEPATH is None:
            return None
        # the full version number also includes the checksum or additional build information. Including it ensures that
        # the cache gets invalidated if the game changes while the version number is unchanged(this can happen in
        # unreleased versions). The re.sub is to avoid potential problems with weird characters in the version string
        path = CACHEPATH / self.short_game_name / re.sub(r'[^a-zA-Z0-9._]', '_', self.full_version)
        path.mkdir(parents=True, exist_ok=True)
        return path


class PdxColor(sRGBColor):
    def __init__(self, r, g, b, is_upscaled=True):
        super().__init__(r, g, b, is_upscaled=is_upscaled)

    @classmethod
    def new_from_parser_obj(cls, color_obj):
        """create an PdxColor object from a Tree/list.

        The Obj must contain a list/tuple of rgb values.
        For example if the following pdx script is parsed into the variable data:
            color = { 20 50 210 }
        then this function could be called in the following way:
            PdxColor.new_from_parser_obj(data['color'])
        """
        if isinstance(color_obj, list):
            return cls(color_obj[0], color_obj[1], color_obj[2], is_upscaled=True)
        elif isinstance(color_obj, Tree) and 'hsv' in color_obj:
            rgb_color = convert_color(HSVColor(color_obj['hsv'][0], color_obj['hsv'][1], color_obj['hsv'][2]), sRGBColor)
            return cls(rgb_color.rgb_r * 255.0, rgb_color.rgb_g * 255.0, rgb_color.rgb_b * 255.0)
        elif isinstance(color_obj, Tree) and 'hsv360' in color_obj:
            rgb_color = convert_color(HSVColor(color_obj['hsv360'][0] / 360.0, color_obj['hsv360'][1] / 100.0, color_obj['hsv360'][2] / 100.0), sRGBColor)
            return cls(rgb_color.rgb_r * 255.0, rgb_color.rgb_g * 255.0, rgb_color.rgb_b * 255.0)
        else:
            raise Exception('Unexpected color type: {}'.format(color_obj))

    @classmethod
    def new_from_rgb_hex(cls, hex_str):
        """
        Converts an RGB hex string like #RRGGBB and assigns the values to
        this sRGBColor object.

        this overrides the parent method, to handle the different is_upscaled correctly

        :rtype: sRGBColor
        """
        colorstring = hex_str.strip()
        if colorstring[0] == '#':
            colorstring = colorstring[1:]
        if len(colorstring) != 6:
            raise ValueError("input #%s is not in #RRGGBB format" % colorstring)
        r, g, b = colorstring[:2], colorstring[2:4], colorstring[4:]
        r, g, b = [int(n, 16) for n in (r, g, b)]
        return cls(r, g, b)

    def get_css_color_string(self) -> str:
        """Returns a string like 'rgb(255, 128, 64)' which can be used to specify colors in CSS"""
        rgb_r, rgb_g, rgb_b = self.get_upscaled_value_tuple()
        return 'rgb({},{},{})'.format(rgb_r, rgb_g, rgb_b)

    @property
    def css_color_string(self) -> str:
        """property version of get_css_color_string"""
        return self.get_css_color_string()


class NameableEntity:
    def __init__(self, name: str, display_name: str, **kwargs):
        self.name = name
        self.display_name = display_name

        for key, value in kwargs.items():
            setattr(self, key, value)

    def __str__(self):
        return self.display_name

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        if other is None:
            return False
        if isinstance(other, str):
            return other == self.display_name or other == self.name
        return self.name == other.name

    def __lt__(self, other):
        return self.display_name < str(other)

    @cached_property
    def default_values(self):
        return {attribute: value for attribute, value in vars(self.__class__).items()
                if not attribute.startswith('__')
                and not callable(value)
                and not isinstance(value, cached_property)
                }


class IconEntity(NameableEntity):
    """NameableEntity with icons"""

    icon: str = ''

    def get_wiki_link(self) -> str:
        return f'[[{self.get_wiki_page_name()}#{self.display_name}|{self.display_name}]]'

    def get_class_name_as_wiki_page_title(self):
        return re.sub(r'(?<!^)(?=[A-Z])', ' ', self.__class__.__name__).capitalize()

    def get_wiki_icon(self, size: str = '') -> str:
        """assumes that it is in the icon template. Subclasses have to override this function if that's not the case"""
        if not self.icon:
            return ''
        if size:
            size = '|' + size
        return f'{{{{icon|{self.display_name}{size}}}}}'

    def get_wiki_link_with_icon(self) -> str:
        return self.get_wiki_icon() + ' ' + self.get_wiki_link()

    def get_wiki_file_tag(self, size: str = '24px') -> str:
        if not self.icon:
            return ''
        filename = self.get_wiki_filename()
        return f'[[File:{filename}|{size}|{self.display_name}]]'

    def get_wiki_filename(self) -> str:
        filename = self.icon.split('/')[-1].replace('.dds', '.png')
        prefix = self.get_wiki_filename_prefix()
        if not filename.lower().startswith(prefix.lower()):
            filename = prefix + ' ' + filename
        return filename

    def get_wiki_filename_prefix(self) -> str:
        """Defaults to the class name. Subclasses can override it to provide their actual names"""
        return self.get_class_name_as_wiki_page_title()

    def get_wiki_page_name(self) -> str:
        """Defaults to the class name. Subclasses can override it to provide their actual names"""
        return self.get_class_name_as_wiki_page_title()
