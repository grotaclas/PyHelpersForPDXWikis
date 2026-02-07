import collections.abc
import importlib
import pprint
import re
from collections import Counter
from collections.abc import Sized
from functools import cached_property
from inspect import isclass
from operator import methodcaller, itemgetter
from types import GenericAlias
from typing import get_origin, get_args, Iterable, Any

from common.jomini_parser import JominiParser
from common.paradox_lib import NameableEntity, PdxColor
from common.paradox_parser import Tree


def to_camel_case(text):
    s = text.replace("-", " ").replace("_", " ")
    s = s.split()
    if len(text) == 0:
        return text
    return ''.join(i.capitalize() for i in s)


class OneTypeHelper:
    parser:JominiParser = None
    low_priority_types = str, Tree, Any
    class_name_map: dict[str, str]

    def __init__(self, folder, depth=0, ignored_toplevel_keys: list=None, ignored_keys: list=None, class_name_map=None, ignore_based_on_data=None):
        self.ignored_keys = ignored_keys
        self.ignored_toplevel_keys = ignored_toplevel_keys
        self.ignore_based_on_data = ignore_based_on_data
        self.depth = depth
        self.folder = folder
        self.element_counter = 0
        self.key_counter = {}
        self.has_empty_elements = False
        if self.parser:
            # initialize the cache, because this can possibly print a lot of debug output
            self.parser.find_possible_entities_by_name('')
        if self.ignored_toplevel_keys is None:
            self.ignored_toplevel_keys = []
        if self.ignored_keys is None:
            self.ignored_keys = []
        if class_name_map:
            self.class_name_map = class_name_map
        else:
            self.class_name_map = dict()
        if self.ignore_based_on_data is None:
            self.ignore_based_on_data = lambda key, data, depth: False

    def get_data(self):
        raise NotImplementedError('Subclasses must implement this function')

    def get_entity_parent_classname(self):
        return 'AdvancedEntity'

    def print_examples_and_code(self):
        print('==Examples==')
        print(self.get_examples())
        print('\n==Definitions==')
        print(self.get_full_class_definition())
        print('\n==Parsing==')
        print(self.get_parsing_code())

    def get_full_class_definition(self, types_which_need_quotes: Iterable[str]=()):
        class_output = [self.get_class_definition()]
        for key, values in sorted(self.keys_with_parsed_values.items()):
            value_type_counter = self.get_value_type_counter(values)

            value_type = Any
            default = 'undetermined'
            guessed_type = self.guess_type_from_name(key)
            if values:
                most_common_type, most_common_count = value_type_counter.most_common(1)[0]
                if most_common_count == len(values):
                    value_type = most_common_type

            if guessed_type is not None and value_type in self.low_priority_types:
                value_type = guessed_type

            if default == 'undetermined':
                default = self.get_default(value_type, values)

            value_type_str = self.get_type_str(value_type, types_which_need_quotes)
            if value_type in self.low_priority_types and  len(value_type_counter.keys()) > 1:
                comment = ' # possible types(out of {}): {}'.format(len(values), ', '.join(f'{t}({count})' for t, count in value_type_counter.most_common()))
            else:
                comment = ''
            # if values:
            #     first_example = list(values)[0]
            # else:
            #     first_example = None
            # is_color = False
            # try:
            #     color = self.parser.parse_color_value(first_example)
            #     if isinstance(color, PdxColor):
            #         is_color = True
            # except:
            #     pass
            # value_type_str = None
            # default = None
            # if value_types == {float, int}:
            #     value_types = {float}`
            # if len(value_types) == 1 or is_color:
            #     value_type_str, default = self.determine_type(values, value_types, first_example, guessed_type,
            #                                                   is_color)
            # elif guessed_type is not None:
            #     if isinstance(guessed_type, tuple):
            #         value_type_str, default = guessed_type
            #     else:
            #         value_type_str = guessed_type
            if self.element_counter == self.key_counter[key]:
                # no default, because all elements have that key
                class_output.append('    {}: {}{}'.format(key, value_type_str, comment))
            else:
                class_output.append('    {}: {} = {}{}'.format(key, value_type_str, pprint.pformat(default), comment))
        cls = '\n'.join(class_output)
        return cls

    def get_value_type_counter(self, values):
        value_types_list = []
        for value in values:
            if isinstance(value, tuple):
                for v2 in value:
                    value_types_list.append(self.get_type(v2))
            else:
                value_types_list.append(self.get_type(value))
        # value_types = set(value_types_list)
        value_type_counter = Counter(value_types_list)
        for low_prio_type in self.low_priority_types:
            if value_type_counter[low_prio_type] > 0:
                low_prio_type_count = value_type_counter[low_prio_type]
                low_prio_type_more_common_than_others = True
                for typ, count in value_type_counter.most_common(2):
                    if typ != low_prio_type and count >= low_prio_type_count:
                        low_prio_type_more_common_than_others = False
                if not low_prio_type_more_common_than_others:
                    del value_type_counter[low_prio_type]
                    # value_types.remove(low_prio_type)
        if value_type_counter[int] > 0 and value_type_counter[float] > 0:
            value_type_counter[float] += value_type_counter[int]
            del value_type_counter[int]
        return value_type_counter

    def get_type(self, value):
        if isinstance(value, type) or isinstance(value, GenericAlias):
            return value
        elif isinstance(value, list):
            element_type = type(value[0])
            if all(type(n) == element_type for n in value):
                return GenericAlias(list, (element_type,))
        return type(value)

    def get_examples(self):
        example_output = []
        for key, values in sorted(self.keys.items()):
            example_output.append('{}: {}'.format(key, list(values)[:4]))
        example = '\n'.join(example_output)
        return example

    @cached_property
    def analyze_folder(self):
        keys = {}
        entity_names = []
        file_counter = 0
        for filename, filedata in self.get_data():
            file_counter += 1
            self._do_analyze(filedata, entity_names, keys, 0)
        if file_counter == 0:
            raise Exception(f'Error: No files found when getting data from {self.folder}')

        return entity_names, keys

    def _do_analyze(self, data: Tree, entity_names: list, keys: dict,  depth=0):
        for key, d2 in data:
            if key in self.ignored_toplevel_keys or not isinstance(d2, Tree) or self.ignore_based_on_data(key, d2, depth):
                continue
            if self.depth == depth:
                entity_names.append(key)
                # self._update_keys_from_data(data['game_data'], keys, self.ignored_keys)
                self._update_keys_from_data(d2, keys, self.ignored_keys)
            else:
                self._do_analyze(d2, entity_names, keys, depth + 1)

    @cached_property
    def entity_names(self) -> list[str]:
        return self.analyze_folder[0]

    @cached_property
    def keys(self) -> dict[str, list]:
        return self.analyze_folder[1]

    @cached_property
    def keys_with_parsed_values(self) -> dict[str, list]:
        return {key:
            [
                self.try_parse_value(key, value)
                for value in values
            ]
            for key, values in self.analyze_folder[1].items()
        }

    def get_possible_loc_prefixes_or_suffixes(self) -> list[tuple[str, str, int, list[str]]]:
        loc_keys = set(self.parser._localization_dict.keys())
        first_name = list(self.entity_names)[0]
        name_re = re.compile(r'(^|.*_)' + first_name + r'($|_.*)')
        possible_pre_suffix = []
        possible_pre_suffix_count = []
        for key in loc_keys:
            match = name_re.fullmatch(key)
            if match:
                possible_pre_suffix.append((match.group(1), match.group(2)))
        for prefix, suffix in possible_pre_suffix:
            possible_loc_keys_with_prefix_suffix = {prefix + name + suffix for name in self.entity_names}
            existing_locs = loc_keys & possible_loc_keys_with_prefix_suffix
            examples = {k: self.parser.localize(k) for k in list(existing_locs)[:2]}
            possible_pre_suffix_count.append((prefix, suffix, len(existing_locs), examples))
        return list(sorted(
            possible_pre_suffix_count,
            key=lambda result_tuple: (
                result_tuple[2],
                # higher priority if there is no prefix and/or suffix
                (1 if (result_tuple[0] == '') else 0) +
                (1 if (result_tuple[1] == '') else 0)
            ),
            reverse=True))

    def get_loc_parameter_lines(self) -> list[str]:
        result = []
        main_name_loc_found = False
        main_name_loc_count = 0
        main_desc_loc_found = False
        main_desc_loc_count = 0
        entity_count = len(self.entity_names)
        for prefix, suffix, count, examples in self.get_possible_loc_prefixes_or_suffixes():
            if 'desc' in prefix.lower() or 'desc' in suffix.lower():
                if main_desc_loc_found:
                    line_prefix = '# '
                else:
                    main_desc_loc_found = True
                    main_desc_loc_count = count
                    line_prefix = ''
                line = f"{line_prefix}description_localization_prefix='{prefix}', description_localization_suffix='{suffix}', # Used in {count}/{entity_count} Examples: {examples}"
                if count / main_desc_loc_count < 0.1 or (count == 1 and entity_count > 1):
                    pass
                    # print(f'Skipping: {line}')
                else:
                    result.append(line)
            else:
                prefix_param = f"localization_prefix='{prefix}', "
                suffix_param = f"localization_suffix='{suffix}', "
                if main_name_loc_found:
                    line_prefix = '# '
                else:
                    main_name_loc_found = True
                    main_name_loc_count = count
                    if prefix == suffix == '':  # default doesn't need parameters
                        line_prefix = '# '
                    else:
                        line_prefix = ''
                        if prefix == '':
                            prefix_param = ''
                        elif suffix == '':
                            suffix_param = ''
                line = f"{line_prefix}{prefix_param}{suffix_param}# Used in {count}/{entity_count} Examples: {examples}"
                if count / main_name_loc_count < 0.1 or (count == 1 and entity_count > 1):
                    pass
                    # print(f'Skipping: {line}')
                else:
                    result.append(line)
        return result


    def get_possible_class_name(self):
        folder_name = self.folder.split('/')[-1]
        possible_class_name = to_camel_case(folder_name)
        if possible_class_name.endswith('ies'):
            possible_class_name = possible_class_name.removesuffix('ies') + 'y'
        elif possible_class_name.endswith('s'):
            possible_class_name = possible_class_name.removesuffix('s')
        if possible_class_name in self.class_name_map:
            return self.class_name_map[possible_class_name]
        else:
            return possible_class_name

    def get_parsing_code(self):
        _ = self.analyze_folder  # just to initialize data
        other_params = ''
        indented_param_line = '\n' + ' ' * 44
        if self.has_empty_elements:
            other_params += f',{indented_param_line}allow_empty_entities=True'

        loc_param_lines = self.get_loc_parameter_lines()
        if len(loc_param_lines) > 0:
            other_params += ',' + indented_param_line.join([''] + loc_param_lines + [''])

        return f"""    @cached_property
    def {self.get_parser_function_name()}(self) -> dict[str, {self.get_possible_class_name()}]:
        return self.parse_advanced_entities('{self.folder}', {self.get_possible_class_name()}{other_params})"""

    def get_parser_function_name(self):
        return self.folder.split('/')[-1]

    def get_class_definition(self):
        return f'class {self.get_possible_class_name()}({self.get_entity_parent_classname()}):'

    def guess_type_from_name(self, attribute_name: str) -> type | None:
        return None

    def try_parse_value(self, key, value):
        """Returns a tuple of possible parsed values (e.g. looking up objects, parsing modifiers or colors)"""
        try:
            return self.parser.parse_color_value(value)
        except:
            pass
        if isinstance(value, str):
            example_entity = self.parser.find_possible_entities_by_name(value)
            if isinstance(example_entity, NameableEntity):
                return example_entity, value
            elif isinstance(example_entity, list):
                return tuple(example_entity)
            else:
                return value
        elif isinstance(value, list):
            types_in_list = {type(v) for v in value}
            if len(types_in_list) == 1:
                if list(types_in_list)[0] == str:
                    example = []
                    for element in value:
                        example_entity = self.parser.find_possible_entities_by_name(element)
                        if isinstance(example_entity, NameableEntity):
                            example.append(example_entity)
                        elif isinstance(example_entity, list):
                            example.append(tuple(example_entity))
                        else:
                            example.append(element)
                    return example
            elif len(types_in_list) == 0:
                return None
        elif isinstance(value, Tree):
            keys = set(value.keys())
            if keys.issubset(set(self.parser.modifier_types.keys())):
                return self.parser._parse_modifier_data(value, self.get_modiifier_class())
        return value

    def get_modiifier_class(self):
        modifier_type_class = list(self.parser.modifier_types.values())[0].__class__
        modifier_classname = modifier_type_class.__name__.removesuffix('Type')
        modifier_type_module_name = modifier_type_class.__module__
        modifier_type_module = importlib.import_module(modifier_type_module_name)
        modifier_class = getattr(modifier_type_module, modifier_classname)
        return modifier_class

    def get_default(self, value_type, values: list):
        if value_type in [int, float]:
            default = 0  # 0 is a reasonable default for numbers if there are no examples with 0
            for value in values:
                if value == 0 or value == 0.0:
                    default = None
            return default
        elif value_type == str:
            return ''
        elif value_type == bool and len(set(values)) == 1:
            return not values[0]
        elif isclass(value_type) and issubclass(value_type, (NameableEntity, PdxColor)):
            return None
        elif isinstance(value_type, GenericAlias) and get_origin(value_type) == list:
            return []

        return None

    def get_type_str(self, value_type, types_which_need_quotes):
        if isinstance(value_type, GenericAlias):
            if get_origin(value_type) == list:
                return f'list[{self.get_type_str(get_args(value_type)[0], types_which_need_quotes)}]'
            else:
                return str(value_type)
        else:
            type_str = value_type.__name__
            if type_str in types_which_need_quotes:
                type_str = f"'{type_str}'"
            return type_str

    def determine_type(self, values: set, value_types: set, first_example: Any, guessed_type: str|None, is_color: bool):
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
        elif value_type == bool and len(set(values)) == 1:
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
        return value_type_str, default

    def get_value_for_example(self, value, key):
        try:
            return self.parser.parse_color_value(value)
        except:
            pass
        if isinstance(value, str):
            example_entity = self.parser.find_possible_entities_by_name(value)
            if isinstance(example_entity, NameableEntity):
                return example_entity, value
            elif isinstance(example_entity, list):
                return tuple(example_entity)
            else:
                return value
        elif isinstance(value, list):
                types_in_list = {type(v) for v in value}
                if len(types_in_list) == 1:
                    if list(types_in_list)[0] == str:
                        example = []
                        for element in value:
                            example_entity = self.parser.find_possible_entities_by_name(element)
                            if isinstance(example_entity, NameableEntity):
                                example.append(example_entity)
                            elif isinstance(example_entity, list):
                                example.append(tuple(example_entity))
                            else:
                                example.append(element)
                        return example
                elif len(types_in_list) == 0:
                    return None
        elif isinstance(value, Tree):
            keys = set(value.keys())
            if keys.issubset(set(self.parser.modifier_types.keys())):
                modifier_type_class = self.parser.modifier_types[keys.pop()].__class__
                modifier_classname = modifier_type_class.__name__.removesuffix('Type')
                modifier_type_module_name = modifier_type_class.__module__
                modifier_type_module = importlib.import_module(modifier_type_module_name)

                modifier_class = getattr(modifier_type_module, modifier_classname)
                return list[modifier_class]
        return value

    def _update_keys_from_data(self, data, keys, ignored_keys: list):
        if isinstance(data, list):
            if len(data) == 0:
                self.has_empty_elements = True
            for item in data:
                self._update_keys_from_data(item, keys, ignored_keys)
        elif isinstance(data, (int, float, str)):
            self.element_counter += 1
            self._really_update_keys_from_data(keys, '_no_key', data)
        else:
            self.element_counter += 1
            for k, v in data:
                if k in ignored_keys:
                    continue
                self._really_update_keys_from_data(keys, k, v)

    def _really_update_keys_from_data(self, keys, k, v):
        if k not in keys:
            keys[k] = []
            self.key_counter[k] = 0
        self.key_counter[k] += 1

        if isinstance(v, Sized) and len(v) == 0:
            # ignore empty lists, dicts or strings, because we cant determine their type
            return
        keys[k].append(v)

        # example = self.get_value_for_example(v, k)
        # if example is not None:
        #     keys[k].append(example)


class MultiTypeHelper:
    parser: JominiParser = None

    def create_helper(self, folder: str, **kwargs) -> OneTypeHelper:
        """Subclasses can override this to create more specific types"""
        return OneTypeHelper(folder, **kwargs)

    def print_base_code_for_missing_types(self, glob='common/*',
                                          already_parsed_folders: Iterable[str] = (),
                                          ignored_folders: Iterable[str] = (),
                                          newlines_between_classes: int = 2,
                                          newlines_between_parsing: int = 1):
        helpers = self.get_helpers_for_missing_folders(glob, already_parsed_folders, ignored_folders)
        sorted_helpers = sorted(helpers.values(), key=methodcaller('get_possible_class_name'))
        print('\n==Definitions==')
        for helper in sorted_helpers:
            print(helper.get_class_definition())
            print('    pass' + ('\n' * newlines_between_classes))
        print('\n==Parsing==')
        for helper in sorted_helpers:
            print(helper.get_parsing_code() + ('\n' * newlines_between_parsing))
        return sorted_helpers

    def get_helpers_for_missing_folders(self, glob: str, already_parsed_folders: Iterable[str], ignored_folders: Iterable[str], class_name_map: dict[str, str] = None) -> dict[str, OneTypeHelper]:
        helpers = {}
        base_folder = self.parser.parser.base_folder
        for folder in base_folder.glob(glob):
            if folder.is_dir():
                if len(list(folder.glob('**/*.txt'))) == 0:
                    print(f'Ignoring folder without txt files {folder}')
                    continue
                relative_folder = str(folder.relative_to(base_folder))
                if relative_folder not in already_parsed_folders and relative_folder not in ignored_folders:
                    helpers[relative_folder] = self.create_helper(relative_folder, class_name_map=class_name_map)
        return helpers