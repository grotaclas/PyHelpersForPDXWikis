import json
import re
from collections import ChainMap
from dataclasses import dataclass
from itertools import groupby

from colormath.color_conversions import convert_color
from colormath.color_objects import sRGBColor, HSVColor
from enum import Flag, Enum
from functools import cached_property, lru_cache
from typing import Any, Callable, Dict, get_origin, get_args, get_type_hints, TypeVar
from pathlib import Path

from common.paradox_parser import Tree

try:
    # when used by PyHelpersForPDXWikis
    from PyHelpersForPDXWikis.localsettings import CACHEPATH
except:  # when used by ck2utils
    from localpaths import cachedir
    CACHEPATH = cachedir


def unsorted_groupby(iterable, key):
    """
    wrapper around itertools.groupby which works even if values with the same keys are non-consecutive

      iterable
        Elements to divide into groups according to the key function.
      key
        A function for computing the group category for each element.
        If the key function is not specified or is None, the element itself
        is used for grouping.
    """
    return groupby(sorted(iterable, key=key), key=key)


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
        return json_object['rawVersion'].removeprefix('v')

    @cached_property
    def full_version(self):
        json_object = json.load(open(self.launcher_settings, encoding='utf-8'))
        self.version = json_object['rawVersion'].removeprefix('v')
        return json_object['version']

    @cached_property
    def major_version(self):
        return '.'.join(self.version.split('.')[0:2])

    def is_pre_release_version(self) -> bool:
        """Assumes that pre-release versions start with 0. Subclasses should override it if necessary"""
        return self.version.startswith('0.')

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

    @classmethod
    @lru_cache(maxsize=1)
    def all_annotations(cls) -> ChainMap:
        """Returns a dictionary-like ChainMap that includes annotations for all
           attributes defined in cls or inherited from superclasses."""
        return ChainMap(*(get_type_hints(c) for c in cls.mro()))


class IconMixin:
    icon: str = ''

    def get_wiki_link(self) -> str:
        """Subclasses should usually override get_wiki_link_target or get_wiki_page_name instead"""
        target = self.get_wiki_link_target()
        if target == self.display_name:
            return f'[[{target}]]'
        else:
            return f'[[{target}|{self.display_name}]]'

    def get_wiki_link_target(self):
        return f'{self.get_wiki_page_name()}#{self.display_name}'

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
        icon = self.get_wiki_icon()
        if icon:  # only add space if there is actually an icon
            icon += ' '
        return icon + self.get_wiki_link()

    def get_wiki_file_tag(self, size: str|None = '24px', link: str = None) -> str:
        """link='self' can be used to link the image to this entity"""
        filename = self.get_wiki_filename()
        if filename:
            if link is None:
                link_param = ''
            else:
                if link == 'self':
                    link = self.get_wiki_link_target()
                link_param = f'|link={link}'
            if size is None or size == '':
                size_param = ''
            else:
                size_param = f'|{size}'
            return f'[[File:{filename}{size_param}|{self.display_name}{link_param}]]'

        return ''

    def get_wiki_filename(self) -> str:
        if not self.icon:
            return ''
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


class IconEntity(NameableEntity, IconMixin):
    """NameableEntity with icons"""


class AttributeEntity:
    """
    Base class for entities which use class attributes with annotations to specify which data they contain

    add_attributes is used to populate the object which in turn uses transform_value_functions and extra_data_functions and the annotations to process the data
    """

    transform_value_functions: dict[str, Callable[[any], any]] = {}
    """ the functions in this dict are called with the value of the data which matches
           the key of this dict. If the key is not present in the data, the function won't
           be called. The function must return the new value for the data"""
    extra_data_functions: dict[str, Callable[[Dict[str, any]], any]] = {}
    """ extra_data_functions: create extra entries in the data. For each key in this dict, the corresponding function
          will be called with the name of the entity and the data dict as parameter. The return
          value will be added to the data dict under the same key"""

    ignored_attributes: list[str] = []
    """ ignored_attributes: these attributes are ignored when adding attributes"""

    def __contains__(self, item):
        return hasattr(self, item)

    def add_attributes(self, attributes: Dict[str, any]):
        annotations = self.all_annotations()
        for key, value in attributes.items():
            if key in self.ignored_attributes:
                continue
            elif key in self.transform_value_functions:
                value = self.transform_value_functions[key](value)
            elif key in annotations:  # special handling based on the type. So far only for enums
                attribute_type = annotations[key]
                origin = get_origin(attribute_type)
                if origin == list:  # List[<sub_type>]
                    sub_type = get_args(attribute_type)[0]
                    # checking for None is needed, because issubclass throws an exception when it is used on GenericAliases
                    if get_origin(sub_type) is None:
                        if issubclass(sub_type, Flag):
                            value = sub_type(value)
                        elif issubclass(sub_type, Enum):
                            value = [sub_type(element) for element in value]
                # checking for None is needed, because issubclass throws an exception when it is used on GenericAliases
                elif origin is None and issubclass(attribute_type, Enum):
                    value = attribute_type(value)
            setattr(self, key, value)
        for key, f in self.extra_data_functions.items():
            setattr(self, key, f(attributes))

    @classmethod
    @lru_cache(maxsize=1)
    def all_annotations(cls) -> ChainMap:
        """Returns a dictionary-like ChainMap that includes annotations for all
           attributes defined in cls or inherited from superclasses."""
        return ChainMap(*(get_type_hints(c) for c in cls.mro()))




class ModifierType(NameableEntity):
    percent: bool = False
    already_percent: bool = False  # used by ck3
    boolean: bool = False
    num_decimals: int = None
    good: bool = None
    neutral: bool = None
    prefix: str = None
    postfix: str = None

    description: str

    # new format
    decimals: int = None
    color: str = None

    # parser: 'JominiParser' = None  # breaks all_annotations
    parser: any

    def __init__(self, name: str, display_name: str, **kwargs):
        super().__init__(name, display_name, **kwargs)
        if self.decimals is not None:
            self.num_decimals = self.decimals
        if self.color == 'good':
            self.good = True
        if self.color == 'bad':
            self.good = False
        if self.color == 'neutral':
            self.neutral = True
        self.display_name, self.description = self._get_fully_localized_display_name_and_desc()

    def _get_fully_localized_display_name_and_desc(self) -> (str, str):
        display_name = self.parser.localize(
            key='modifier_' + self.name,
            # version 1.7 removed the modifier_ prefix from the localisations, but I'm not sure if that's always the case, so this code allows both
            default=self.parser.localize(self.name))
        display_name = self.parser.formatter.format_localization_text(display_name, [])
        description = self.parser.localize(self.name + '_desc')
        description = self.parser.formatter.format_localization_text(description, [])
        return display_name, description

    @cached_property
    def icon(self):
        icon = self.display_name
        # remove links
        icon = re.sub(r'\[\[([^|]*\|)?([^]|]+)[^]]*]]', r'\2', icon)
        # remove icon tags
        icon = re.sub(r'\{\{icon\|[^}]*}}(&nbsp;)?\s*', '', icon)

        return icon

    def get_color_for_value(self, value) -> str:
        if self.good is not None and value != 0:
            if self.boolean:
                if value:
                    value_for_coloring = 1
                else:
                    value_for_coloring = -1
            else:
                self.assert_number(value)
                if self.good:
                    value_for_coloring = value
                else:
                    value_for_coloring = -1 * value
            if value_for_coloring > 0:
                return 'green'
            elif value_for_coloring < 0:
                return 'red'

        return '#000'

    def format_value(self, value):
        try:
            formatted_value = self.format_value_without_color(value)

            color = self.get_color_for_value(value)
            # if color == '#000':
            #     prefix = "'''"
            #     postfix = "'''"
            # else:
            if color in ['red', 'green']:
                prefix = f'{{{{{color}|'
            else:
                prefix = f'{{{{color|{color}|'
            postfix = '}}'
        except:
            formatted_value = value
            prefix = ''
            postfix = ''

        if self.postfix:
            postfix += self.parser.formatter.format_localization_text(self.parser.localize(self.postfix), [])
        if self.prefix:
            prefix = self.parser.formatter.format_localization_text(self.parser.localize(self.prefix), []) + prefix

        return f'{prefix}{formatted_value}{postfix}'

    def format_value_without_color(self, value):
        formatted_value = value
        postfix = ''
        prefix = ''
        if type(value) == int or type(value) == float:
            if value > 0:
                prefix = '+'
            if value < 0:
                prefix = '−'  # unicode minus
                formatted_value = abs(value)
        if self.boolean:
            if type(value) != bool:
                raise Exception('Unexpected value "{}" for modifier {}'.format(value, self.name))
            if value:
                formatted_value = 'yes'
            else:
                formatted_value = 'no'
        if self.percent:
            self.assert_number(value)
            formatted_value *= 100
            postfix += '%'

        if self.num_decimals is not None:
            try:
                self.assert_number(value)
                # test if the number has more significant digits than num_decimals
                if formatted_value * 10**self.num_decimals - int(formatted_value * 10**self.num_decimals) == 0:
                    # if it doesn't, we show num_decimals precision
                    format_string = f'{{:.{self.num_decimals}f}}'
                else:
                    # otherwise we show the full precision, but use the g formatting to remove trailing zeros
                    format_string = f'{{:g}}'

                formatted_value = format_string.format(formatted_value)
            except:
                pass

        return f'{prefix}{formatted_value}{postfix}'

    def assert_number(self, value):
        if type(value) != int and type(value) != float:
            raise Exception('Unexpected value "{}" for modifier {}'.format(value, self.name))


class Modifier(NameableEntity):
    modifier_type: ModifierType
    value: Any

    def __init__(self, name: str, modifier_type: ModifierType, value: Any):
        super().__init__(name, modifier_type.display_name, modifier_type=modifier_type, value=value)

    def format_for_wiki(self):
        value = self.modifier_type.format_value(self.value)
        if self.modifier_type.boolean:
            return f'{self.display_name}: {value}'
        else:
            return f'{value} {self.display_name}'

    def format_for_lua(self) -> list:
        """To be passed to https://vic3.paradoxwikis.com/Module:Iconify

        The output still has to be passed to a lua serializer"""
        return [self.modifier_type.get_color_for_value(self.value), self.modifier_type.format_value_without_color(self.value), {'icon': self.modifier_type.icon}]


class AdvancedEntity(IconEntity):
    """Adds various extra fields. Not all of them are used by all subclasses"""

    description: str = ''
    modifier: list[Modifier] = []

    def str_with_type(self) -> str:
        return f'{self.display_name} ({self.__class__.__name__})'

class GameConcept(AdvancedEntity):
    name: str
    display_name: str
    description: str
    icon: str
    link: str


AE = TypeVar('AE', bound=AdvancedEntity)
NE = TypeVar('NE', bound=NameableEntity)
ME = TypeVar('ME', bound=Modifier)
