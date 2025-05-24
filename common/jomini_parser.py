import inspect
import re
from abc import ABCMeta, abstractmethod

import sys
from functools import cached_property
from typing import Iterator, Type, Callable

from common.paradox_parser import ParadoxParser, Tree, ParsingWorkaround
from common.paradox_lib import Modifier, AE, NE, ModifierType


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
                                localization_prefix: str = '') -> dict[str, NE]:
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
        class_attributes = inspect.get_annotations(entity_class)
        if entity_level == 0:
            overwrite_duplicate_toplevel_keys = True
        else:
            overwrite_duplicate_toplevel_keys = False
        entities = self._get_entities_from_level(class_attributes, entity_class, extra_data_functions,
                                                 previous_headings=[],
                                                 transform_value_functions=transform_value_functions,
                                                 tree=self.parser.parse_folder_as_one_file(folder,
                                                                                           overwrite_duplicate_toplevel_keys=overwrite_duplicate_toplevel_keys,
                                                                                           workarounds=parsing_workarounds),
                                                 entity_level=entity_level, current_level=0,
                                                 level_headings_keys=level_headings_keys)

        return entities

    def _get_entities_from_level(self, class_attributes, entity_class, extra_data_functions, previous_headings,
                                 transform_value_functions, tree, entity_level, current_level, level_headings_keys,
                                 conditions=None):
        entities = {}
        for heading, data in tree:
            if heading == 'if':
                entities.update(self._get_entities_from_level(class_attributes, entity_class, extra_data_functions,
                                                              headings, transform_value_functions,
                                                              data.filter_elements(lambda k, v: k != 'limit'),
                                                              entity_level, current_level, level_headings_keys,
                                                              conditions=data['limit']))
            elif heading == 'else':
                entities.update(self._get_entities_from_level(class_attributes, entity_class, extra_data_functions,
                                                              headings, transform_value_functions,
                                                              data,
                                                              entity_level, current_level, level_headings_keys,
                                                              conditions))
            else:
                headings = previous_headings.copy()
                headings.append(heading)
                if current_level < entity_level:
                    entities.update(self._get_entities_from_level(class_attributes, entity_class, extra_data_functions,
                                                                  headings, transform_value_functions, data, entity_level,
                                                                  current_level + 1, level_headings_keys, conditions))
                else:
                    if isinstance(data, Tree):
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
                                localization_prefix: str = ''
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
        if 'modifiers' not in extra_data_functions:
            extra_data_functions['modifiers'] = self.parse_modifier_section
        return self.parse_nameable_entities(folder, entity_class, extra_data_functions=extra_data_functions,
                                            transform_value_functions=transform_value_functions,
                                            localization_prefix=localization_prefix)

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

    def _parse_modifier_data(self, data: Tree):
        return [Modifier(mod_name, modifier_type=self.get_modifier_type_or_default(mod_name), value=mod_value)
                for mod_name, mod_value in data]

    def parse_modifier_section(self, name, data) -> list[Modifier]:
        if 'modifier' not in data:
            return []
        else:
            return self._parse_modifier_data(data['modifier'])

    @cached_property
    def modifier_types(self) -> dict[str, ModifierType]:
        return self.parse_nameable_entities('common/modifier_type_definitions', ModifierType, extra_data_functions={'parser': lambda name, data: self})

    @cached_property
    def modifier_types(self) -> dict[str, ModifierType]:
        return self.parse_nameable_entities('common/modifier_type_definitions', ModifierType, extra_data_functions={'parser': lambda name, data: self})

    @cached_property
    def modifier_types(self) -> dict[str, ModifierType]:
        return self.parse_nameable_entities('common/modifier_type_definitions', ModifierType, extra_data_functions={'parser': lambda name, data: self})