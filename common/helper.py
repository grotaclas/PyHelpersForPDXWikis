import collections.abc
import pprint
from types import GenericAlias
from typing import get_origin, get_args

from common.jomini_parser import JominiParser
from common.paradox_lib import NameableEntity, PdxColor


def to_camel_case(text):
    s = text.replace("-", " ").replace("_", " ")
    s = s.split()
    if len(text) == 0:
        return text
    return ''.join(i.capitalize() for i in s)


class Helper:
    parser:JominiParser = None

    def __init__(self):
        self.element_counter = 0
        self.key_counter = {}

    def get_data(self, folder):
        raise NotImplementedError('Subclasses must implement this function')

    def get_entity_parent_classname(self):
        return 'AdvancedEntity'

    def find_all_keys_in_folder(self, folder, depth=0, ignored_toplevel_keys: list=None, ignored_keys: list=None):
        if self.parser:
            # initialize the cache, because this can possibly print a lot of debug output
            self.parser.find_possible_entities_by_name('')
        keys = {}
        if ignored_toplevel_keys is None:
            ignored_toplevel_keys = []
        if ignored_keys is None:
            ignored_keys = []
        for filename, filedata in self.get_data(folder):
            for toplevelkey, data in filedata:
                if toplevelkey in ignored_toplevel_keys:
                    continue
                if depth == 0:
                    self._update_keys_from_data(data, keys, ignored_keys)
                else:
                    for n2, d2 in data:
                        if depth == 1:
                            if n2 in ignored_toplevel_keys:
                                continue
                            self._update_keys_from_data(d2, keys, ignored_keys)
                        else:
                            for n3, d3 in d2:
                                if depth == 2:
                                    if n3 in ignored_toplevel_keys:
                                        continue
                                    self._update_keys_from_data(d3, keys, ignored_keys)
                                else:
                                    for n4, d4 in d3:
                                        if n4 in ignored_toplevel_keys:
                                            continue
                                        self._update_keys_from_data(d4, keys, ignored_keys)
        print('==Examples==')
        for key, values in sorted(keys.items()):
            print('{}: {}'.format(key, list(values)[:4]))
        print('\n==Definitions==')
        folder_name = folder.split('/')[-1]
        possible_class_name = to_camel_case(folder_name)
        if possible_class_name.endswith('ies'):
            possible_class_name = possible_class_name.removesuffix('ies') + 'y'
        elif possible_class_name.endswith('s'):
            possible_class_name = possible_class_name.removesuffix('s')
        print(f'class {possible_class_name}({self.get_entity_parent_classname()}):')
        for key, values in sorted(keys.items()):
            value_types = {v if isinstance(v, type) or isinstance(v, GenericAlias) else type(v) for v in values}
            if values:
                first_example = list(values)[0]
            else:
                first_example = None
            is_color = False
            try:
                color = self.parser.parse_color_value(first_example)
                if isinstance(color, PdxColor):
                    is_color = True
            except:
                pass
            guessed_type = self.guess_type(key)
            value_type_str = None
            default = None
            if len(value_types) == 1 or is_color:
                value_type = value_types.pop()
                default = None
                if guessed_type is None:
                    value_type_str = value_type.__name__
                elif isinstance(guessed_type, tuple):
                    value_type_str, default = guessed_type
                else:
                    value_type_str = guessed_type
                if is_color:
                    value_type_str = 'PdxColor'
                    default = None
                elif len(values) == 1 and value_type == bool:
                    default = not first_example  # if all entries are true, the default must be false and vice versa
                elif value_type in [int, float]:
                    default = 0  # 0 is a reasonable default for numbers if there are no examples with 0
                    for value in values:
                        if value == 0 or value == 0.0:
                            default = None
                elif value_type == str:
                    default = ''
                    if self.parser:
                        example_entity = self.parser.find_possible_entities_by_name(first_example)
                        if isinstance(example_entity, NameableEntity):
                            value_type_str = type(example_entity).__name__
                            default = None
                        else:
                            try:
                                color = self.parser.parse_color_value(first_example)
                                if isinstance(color, PdxColor):
                                    value_type_str = 'PdxColor'
                                    default = None
                            except:
                                pass

                elif isinstance(value_type, GenericAlias):
                    if get_origin(value_type) == list:
                        value_type_str = f'list[{get_args(value_type)[0].__name__}]'
                        default = []
                    else:
                        value_type_str = pprint.pformat(value_type)
            elif guessed_type is not None:
                if isinstance(guessed_type, tuple):
                    value_type_str, default = guessed_type
                else:
                    value_type_str = guessed_type
            if value_type_str is None:
                print('    {}: any  # possible types: {}'.format(key, value_types))
            elif self.element_counter == self.key_counter[key]:
                # no default, because all elements have that key
                print('    {}: {}'.format(key, value_type_str))
            else:
                print('    {}: {} = {}'.format(key, value_type_str, pprint.pformat(default)))
        print('\n==Parsing==')
        print(f"""    @cached_property
    def {folder_name}(self) -> dict[str, {possible_class_name}]:
        return self.parse_advanced_entities('{folder}', {possible_class_name})""")
        return keys

    def guess_type(self, attribute_name: str) -> str|None:
        return None

    def get_value_for_example(self, value, key):
        if isinstance(value, collections.abc.Hashable):
            return value
        else:
            if isinstance(value, list):
                types_in_list = {type(v) for v in value}
                if len(types_in_list) == 1:
                    if list(types_in_list)[0] == str:
                        example_entity = self.parser.find_possible_entities_by_name(value[0])
                        if isinstance(example_entity, NameableEntity):
                            return list[type(example_entity)]
                    return list[types_in_list.pop()]
                elif len(types_in_list) == 0:
                    return None
            return type(value)
    def _update_keys_from_data(self, data, keys, ignored_keys: list):
        if isinstance(data, list):
            for item in data:
                self._update_keys_from_data(item, keys, ignored_keys)
        else:
            self.element_counter += 1
            for k, v in data:
                if k in ignored_keys:
                    continue
                if k not in keys:
                    keys[k] = set()
                    self.key_counter[k] = 0
                self.key_counter[k] += 1
                example = self.get_value_for_example(v, k)
                if example is not None:
                    keys[k].add(example)
