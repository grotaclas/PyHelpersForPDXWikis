import enum
import inspect
import re
import typing
from abc import ABCMeta, abstractmethod

import sys
from functools import cached_property
from typing import Iterator, Type, Callable, get_origin, get_args

from common.paradox_parser import ParadoxParser, Tree, ParsingWorkaround
from common.paradox_lib import Modifier, AE, NE, ME, ModifierType, NameableEntity, PdxColor


class JominiParser(metaclass=ABCMeta):
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

    def parse_nameable_entities(self, folder: str, entity_class: Type[NE],
                                extra_data_functions: dict[str, Callable[[str, Tree], any]] = None,
                                transform_value_functions: dict[str, Callable[[any], any]] = None,
                                entity_level: int = 0,
                                level_headings_keys: dict[str, 0] = None,
                                parsing_workarounds: list[ParsingWorkaround] = None,
                                localization_prefix: str = '',
                                allow_empty_entities=False) -> dict[str, NE]:
        """parse a folder into objects which are subclasses of NameableEntity

        Args:
            folder: relative to the 'steamapps/common/X/game' folder
            entity_class: each entry in the files will create one of these objects. All the data will be passed as
                          keyword arguments to the constructor. If the NameableEntity constructor is not overridden, it
                          will turn these arguments into properties of the object
            extra_data_functions: create extra entries in the data. For each key in this dict, the corresponding function
                                  will be called with the name of the entity and the data dict as parameter. The return
                                  value will be added to the data dict under the same key. 'name' and 'display_name'
                                   can also be used as keys to change the name dnd display name of the entity
            transform_value_functions: the functions in this dict are called with the value of the data which matches
                                       the key of this dict. If the key is not present in the data, the function won't
                                       be called. The function must return the new value for the data
            entity_level: the level where the entities can be found. The default is 0 which means that the entities
                          are on the toplevel.
            level_headings_keys: if entity_level is bigger than 0, this map is used to add the headings of each level
                                 as additional keys into the data dictionary. Each entry in level_headings_keys has the
                                 key which will be used as the key in the data dictionary and the value which is the
                                 level of the heading which should be used. 'name' can also be a key to specify where
                                 the name comes from
            parsing_workarounds:
            localization_prefix: this prefix is added in front of the name to get the localization key for the display name
            allow_empty_entities: parse empty sections as well

        Returns:
            a dict between the name of the entity(if not specified, the top level keys in the folder is used as the
            name) and the entity_class objects which were created from them
        """
        if extra_data_functions is None:
            extra_data_functions = {}
        if transform_value_functions is None:
            transform_value_functions = {}
        if level_headings_keys is None:
            level_headings_keys = {}
        if 'display_name' not in extra_data_functions:
            extra_data_functions['display_name'] = lambda entity_name, entity_data: self.localize(localization_prefix + entity_name)
        class_attributes = entity_class.all_annotations()
        if entity_level == 0:
            overwrite_duplicate_toplevel_keys = True
        else:
            overwrite_duplicate_toplevel_keys = False
        if isinstance(folder, Tree):
            tree = folder
        elif folder.endswith('.txt'):
            tree = self.parser.parse_file(folder, workarounds=parsing_workarounds)
        else:
            tree = self.parser.parse_folder_as_one_file(folder, overwrite_duplicate_toplevel_keys=overwrite_duplicate_toplevel_keys,
                                                    workarounds=parsing_workarounds)
        entities = self._get_entities_from_level(class_attributes, entity_class, extra_data_functions,
                                                 previous_headings=[],
                                                 transform_value_functions=transform_value_functions,
                                                 tree=tree,
                                                 entity_level=entity_level, current_level=0,
                                                 level_headings_keys=level_headings_keys,
                                                 allow_empty_entities=allow_empty_entities)

        return entities

    def _get_entities_from_level(self, class_attributes, entity_class, extra_data_functions, previous_headings,
                                 transform_value_functions, tree, entity_level, current_level, level_headings_keys,
                                 conditions=None, allow_empty_entities=False):
        entities = {}
        for heading, data in tree:
            if heading == 'if':
                entities.update(self._get_entities_from_level(class_attributes, entity_class, extra_data_functions,
                                                              headings, transform_value_functions,
                                                              data.filter_elements(lambda k, v: k != 'limit'),
                                                              entity_level, current_level, level_headings_keys,
                                                              conditions=data['limit'], allow_empty_entities=allow_empty_entities))
            elif heading == 'else':
                entities.update(self._get_entities_from_level(class_attributes, entity_class, extra_data_functions,
                                                              headings, transform_value_functions,
                                                              data,
                                                              entity_level, current_level, level_headings_keys,
                                                              conditions, allow_empty_entities))
            else:
                headings = previous_headings.copy()
                headings.append(heading)
                if current_level < entity_level:
                    entities.update(self._get_entities_from_level(class_attributes, entity_class, extra_data_functions,
                                                                  headings, transform_value_functions, data, entity_level,
                                                                  current_level + 1, level_headings_keys, conditions,
                                                                  allow_empty_entities))
                else:
                    if isinstance(data, Tree) or (not data and allow_empty_entities):
                        name, entity = self._parse_entity(class_attributes, data, entity_class,
                                                          extra_data_functions, headings, level_headings_keys,
                                                          transform_value_functions, conditions)
                        entities[name] = entity
                    else:  # assume list
                        for entry in data:
                            if len(entry) > 0:
                                name, entity = self._parse_entity(class_attributes, entry, entity_class,
                                                                  extra_data_functions, headings, level_headings_keys,
                                                                  transform_value_functions, conditions)
                                entities[name] = entity
                            else:
                                print(f'Warning: ignoring empty element in "{"|".join(headings)}"', file=sys.stderr)
        return entities

    def _parse_entity(self, class_attributes, data, entity_class, extra_data_functions, headings,
                      level_headings_keys, transform_value_functions, conditions=None):
        entity_values = {}
        if 'name' in extra_data_functions:
            name = extra_data_functions['name']('', data)
        elif 'name' in level_headings_keys:
            name = headings[level_headings_keys['name']]
        else:
            name = headings[-1]
        for key, level in level_headings_keys.items():
            if key != 'name':
                entity_values[key] = headings[level_headings_keys[key]]
                if key in transform_value_functions:
                    entity_values[key] = transform_value_functions[key](entity_values[key])
        for key, func in extra_data_functions.items():
            if key != 'name':
                entity_values[key] = func(name, data)
        for k, v in data:
            if k in transform_value_functions:
                entity_values[k] = transform_value_functions[k](v)
            elif k in class_attributes and k not in entity_values:
                if inspect.isclass(class_attributes[k]) and issubclass(class_attributes[k], enum.Enum):
                    entity_values[k] = class_attributes[k](v)
                elif inspect.isclass(class_attributes[k]) and issubclass(class_attributes[k], PdxColor):
                    entity_values[k] = self.parse_color_value(v)
                elif typing.get_origin(class_attributes[k]) == list and inspect.isclass(typing.get_args(class_attributes[k])[0]) and issubclass(typing.get_args(class_attributes[k])[0], Modifier):
                    if type(v) == list and len(v) > 0:
                        print(f'Error: duplicate section "{k}" in "{name}"')
                        continue
                    entity_values[k] = self._parse_modifier_data(v, typing.get_args(class_attributes[k])[0])
                elif typing.get_origin(class_attributes[k]) == list and inspect.isclass(typing.get_args(class_attributes[k])[0]) and issubclass(
                        typing.get_args(class_attributes[k])[0], NameableEntity) and typing.get_args(class_attributes[k])[0] != entity_class:
                    if isinstance(v, str):
                        v = [v]
                    entity_values[k] = [self.resolve_entity_reference(typing.get_args(class_attributes[k])[0], entity_name) for entity_name in v]
                elif inspect.isclass(class_attributes[k]) and issubclass(class_attributes[k], NameableEntity) and class_attributes[k] != entity_class:
                    entity_values[k] = self.resolve_entity_reference(class_attributes[k], v)
                else:
                    entity_values[k] = v
        if conditions is not None:
            if 'conditions' in class_attributes:
                entity_values['conditions'] = conditions
            elif 'dlc' in class_attributes:
                entity_values['dlc'] = self.parse_dlc_from_conditions(conditions)
        return name, entity_class(name, **entity_values)

    @abstractmethod
    def parse_dlc_from_conditions(self, conditions):
        pass

    def parse_advanced_entities(self, folder: str, entity_class: Type[AE],
                                extra_data_functions: dict[str, Callable[[str, Tree], any]] = None,
                                transform_value_functions: dict[str, Callable[[any], any]] = None,
                                localization_prefix: str = '',
                                allow_empty_entities=False,
                                parsing_workarounds: list[ParsingWorkaround] = None,
                                ) -> dict[str, AE]:
        """parse a folder into objects which are subclasses of AdvancedEntity

        See parse_nameable_entities() for a description of the arguments and return value

        This method adds parsing of icon/texture, description(from the _desc localization),
        and modifiers (from the modifier section)


        """
        if extra_data_functions is None:
            extra_data_functions = {}
        if 'icon' not in extra_data_functions:
            extra_data_functions['icon'] = self.parse_icon
        if 'description' not in extra_data_functions:
            extra_data_functions['description'] = lambda name, data: self.localize(localization_prefix + name + '_desc')
        return self.parse_nameable_entities(folder, entity_class, extra_data_functions=extra_data_functions,
                                            transform_value_functions=transform_value_functions,
                                            localization_prefix=localization_prefix,
                                            allow_empty_entities=allow_empty_entities,
                                            parsing_workarounds=parsing_workarounds)

    def get_modifier_type_or_default(self, modifier_name: str) -> ModifierType:
        if modifier_name in self.modifier_types:
            return self.modifier_types[modifier_name]
        else:
            # print(f'Warning: use default for unknown modifier "{modifier_name}"', file=sys.stderr)
            modifier_type = ModifierType(modifier_name, self.localize(modifier_name), parser=self)
            if 'mortality' in modifier_name:
                modifier_type.good = False
                modifier_type.percent = True
            if modifier_name.endswith('throughput_add'):
                modifier_type.good = True
                modifier_type.percent = True
            self.modifier_types[modifier_name] = modifier_type
            return modifier_type

    def parse_icon(self, name, data, possible_icon_keys: list[str] = None):
        if possible_icon_keys is None:
            possible_icon_keys = ['icon', 'texture']
        for icon_key in possible_icon_keys:
            if icon_key in data:
                return data[icon_key]
        return ''

    def _parse_mod_value(self, mod_type: ModifierType, mod_value: any):
        """Some post-processing for modifier values. Currently only implements resolving script values"""
        if isinstance(mod_value, str) and mod_value in self.script_values:
            return self.script_values[mod_value]
        else:
            return mod_value

    def _parse_modifier_data(self, data: Tree, modifier_class: Type[ME] = Modifier) -> list[ME]:
        modifiers = []
        for mod_name, mod_value in data:
            if isinstance(mod_value, list) and mod_name != 'potential_trigger':
                mod_value = sum(mod_value)
            mod_type = self.get_modifier_type_or_default(mod_name)
            mod_value = self._parse_mod_value(mod_type, mod_value)
            modifiers.append(modifier_class(mod_name, modifier_type=mod_type, value=mod_value))
        return modifiers

    def parse_modifier_section(self, name, data, section_name='modifier', modifier_class: Type[ME] = Modifier) -> list[ME]:
        if section_name not in data:
            return []
        else:
            return self._parse_modifier_data(data[section_name], modifier_class)

    @cached_property
    def _class_property_map(self) -> dict[Type[NE]: str]:
        class_property_map = {}
        for name, member in inspect.getmembers(self.__class__, predicate=lambda m: type(m) == cached_property):
            return_type = inspect.signature(member.func).return_annotation
            if return_type == inspect.Signature.empty:
                continue
            origin = get_origin(return_type)
            type_args = get_args(return_type)
            if origin == dict and type_args[0] == str and issubclass(type_args[1], NameableEntity):
                class_property_map[type_args[1]] = name
        return class_property_map

    def resolve_entity_reference(self, entity_class: Type[NE], entity_name:str):
        if entity_class in self._class_property_map:
            data = getattr(self, self._class_property_map[entity_class])
            if entity_name in data:
                return data[entity_name]
        return entity_name

    def find_possible_entities_by_name(self, entity_name: str) -> NameableEntity|list[NameableEntity]|None:
        entities_by_name = {}
        for cls, prty in self._class_property_map.items():
            for name, entity in getattr(self, prty).items():
                if name in entities_by_name:
                    if not isinstance(entities_by_name[name], list):
                        entities_by_name[name] = [entities_by_name[name]]
                    entities_by_name[name].append(entity)
                else:
                    entities_by_name[name] = entity
        if entity_name in entities_by_name:
            return entities_by_name[entity_name]
        else:
            return None


    @cached_property
    def modifier_types(self) -> dict[str, ModifierType]:
        return self.parse_nameable_entities('common/modifier_type_definitions', ModifierType, extra_data_functions={'parser': lambda name, data: self})

    @cached_property
    def script_values(self):
        return self.parser.parse_folder_as_one_file('common/script_values').merge_duplicate_keys()

    def _parse_named_colors(self, folders: list[str]):
        named_colors = {}
        for folder in folders:
            for file, parsed_data in self.parser.parse_files(folder + '/*'):
                for color_name, color_data in parsed_data['colors']:
                    if isinstance(color_data, list) and isinstance(color_data[-1], Tree):
                        # assume that this means that the color is defined multiple times, so we take the last definition
                        color_data = color_data[-1]
                    named_colors[color_name] = PdxColor.new_from_parser_obj(color_data)
        return named_colors

    @cached_property
    def named_colors(self) -> dict[str, PdxColor]:
        named_colors = self._parse_named_colors(['../jomini/common/named_colors', 'common/named_colors'])
        return named_colors

    def parse_color_value(self, color):
        if isinstance(color, str) and color in self.named_colors:
            return self.named_colors[color]
        else:
            return PdxColor.new_from_parser_obj(color)

