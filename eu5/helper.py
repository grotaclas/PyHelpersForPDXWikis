import inspect
import re
import uuid
from collections import Counter
from functools import cached_property

import sys
from collections.abc import Set
from operator import methodcaller
from types import UnionType
from typing import get_type_hints, get_origin, get_args, Iterable, Type, Any

from common.file_generator import FileGenerator
from common.helper import OneTypeHelper, MultiTypeHelper
from common.paradox_lib import IconMixin, NE, Modifier, PdxColor, NameableEntity
from common.paradox_parser import ParsingWorkaround, Tree, QuestionmarkEqualsWorkaround
from eu5 import eu5lib
from eu5.eu5lib import Eu5AdvancedEntity, Cost, GoodsDemand, Price, Eu5Modifier, Trigger, Effect, ScriptValue
from eu5.game import eu5game
from eu5.parser import Eu5Parser


class Eu5OneTypeHelper(OneTypeHelper):
    parser: Eu5Parser
    image_filename_to_folders = None

    def __init__(self, folder, depth=0, ignored_toplevel_keys: list = None, ignored_keys: list = None, class_name_map=None):
        self.parser = eu5game.parser
        folder = folder.removeprefix('game/')
        super().__init__(folder, depth, ignored_toplevel_keys, ignored_keys, class_name_map)




    def get_data(self):
        if self.folder.endswith('.txt'):
            glob = self.folder
        else:
            glob = f'{self.folder}/*.txt'
        return self.parser.parser.parse_files(glob, [QuestionmarkEqualsWorkaround()])

        # Temporary code to include template data for files which have an include= line
        # template_data = {}
        # for file in (self.parser.parser.base_folder / 'main_menu/setup/templates').glob("*.txt"):
        #     with open(file, encoding='utf-8-sig') as fp:
        #         template_data[file.stem] = fp.read()
        # class TemplateWorkaround(ParsingWorkaround):
        #     """replaces statements like
        #         include = "filename"
        #     with the contents of the file game/main_menu/setup/templates/filename.txt
        #     """
        #     replacement_regexes = {f'\n\\s*include\\s*=\\s*"?{filename}"?\\s*(#.*)?\n': f'\n{contents}\n' for filename, contents in template_data.items()}
        # return self.parser.parser.parse_files(glob, workarounds=[TemplateWorkaround()])

    def get_entity_parent_classname(self):
        return 'Eu5AdvancedEntity'

    def guess_type_from_name(self, attribute_name: str) -> type | None:
        if attribute_name in ['enabled', 'visible', 'potential', 'allow']:
            # return 'Trigger'
            return Trigger
        if attribute_name.startswith('enabled_'):
            return Trigger
            # return 'Trigger'
        if attribute_name in ['effect', 'hidden_effect'] or attribute_name.startswith('on_'):
            # return 'Effect'
            return Effect
        if 'modifier' in  attribute_name:
            return list[Eu5Modifier]
            # return 'list[Eu5Modifier]', []
        return None

    def try_parse_value(self, key, value):
        parsed_values = []
        if isinstance(value, Tree):
            if ScriptValue.could_be_script_value(value):
                return ScriptValue(f'inline_script_value_{uuid.uuid1()}', '', **value.dictionary), value
            if Trigger.could_be_trigger(value):
                parsed_values.append(Trigger(value.dictionary))
            if Effect.could_be_effect(value):
                parsed_values.append(Effect(value.dictionary))
        if parsed_values:
            parsed_values.append(value)
            return tuple(parsed_values)
        return super().try_parse_value(key, value)

    def get_value_for_example(self, value, key):
        if isinstance(value, Tree) and Trigger.could_be_trigger(value):
            return Trigger
        # if isinstance(value, Tree) and Effect.could_be_effect(value):
        #     return Effect
        if key == 'special_status':
            pass
        example = super().get_value_for_example(value, key)
        # if key == 'special_status':
        #     print('special_status:', key, value, example)
        return example

    def get_value_type_counter(self, values):
        value_type_counter = super().get_value_type_counter(values)
        if value_type_counter[ScriptValue] > 0:
            if value_type_counter[int] > 0:
                value_type_counter[ScriptValue] += value_type_counter[int]
                del value_type_counter[int]
            if value_type_counter[float] > 0:
                value_type_counter[ScriptValue] += value_type_counter[float]
                del value_type_counter[float]
        return value_type_counter

    def _get_icon_folder_count(self):
        possible_folders = []
        for name in self.entity_names:
            if name in self.get_image_filename_to_folders():
                possible_folders.extend(self.get_image_filename_to_folders()[name])
        counter = Counter(possible_folders)
        return counter.most_common(None)

    def get_icon_folder_code(self) -> str|None:
        code = []
        found_good_folder = False
        for folder, count in self._get_icon_folder_count():
            prefix = '# '
            if count == len(self.entity_names):
                found_good_folder = True
                prefix = ''
            elif count > 4 and count > len(self.entity_names) / 5:
                # not certain that it is the right folder, but somewhat likely
                folder_name_based_on_class = self.camel_to_snake(self.get_possible_class_name())
                if not found_good_folder:
                    if folder_name_based_on_class in folder.lower():
                        found_good_folder = True
                    prefix = ''
            else:
                # too unlikely, so we skip them to avoid generating many lines for random matches
                continue

            code.append(f'    {prefix}icon_folder = \'{folder}\' # {count} / {len(self.entity_names)} icons found')
        return '\n'.join(code)

    @classmethod
    def get_image_filename_to_folders(cls) -> dict[str, list[str]]:
        if cls.image_filename_to_folders is None:
            base_folder_for_defines = eu5game.game_path / 'game/main_menu'
            folder_to_define = {folder: define for define, folder in eu5game.parser.defines['NGameIcons'].update(eu5game.parser.defines['NGameIllustrations']) if isinstance(folder, str)}
            image_filename_to_folders = {}
            for ext in ['dds', 'tga', '.png']:
                for path in eu5game.game_path.rglob(f'*.{ext}'):
                    filename = path.stem
                    if filename not in image_filename_to_folders:
                        image_filename_to_folders[filename] = []
                    folder_name = str(path.parent.relative_to(Eu5AdvancedEntity.base_icon_folder, walk_up=True))
                    # possible_defines_folder = str(path.parent.relative_to(path.parents[4]))
                    if path.is_relative_to(base_folder_for_defines):
                        possible_defines_folder = str(path.parent.relative_to(base_folder_for_defines))
                        if possible_defines_folder in folder_to_define:
                            folder_name = folder_to_define[possible_defines_folder]
                    image_filename_to_folders[filename].append(folder_name)

            cls.image_filename_to_folders = image_filename_to_folders
        return cls.image_filename_to_folders

    def get_full_class_definition(self, types_which_need_quotes: Iterable[str]=()):
        cls = super().get_full_class_definition(types_which_need_quotes)
        icon_folder = self.get_icon_folder_code()
        if icon_folder:
            cls = f'{cls}\n{icon_folder}'
        return cls

    #####################################################
    # Helper functions to generate new table generators #
    #####################################################

    @staticmethod
    def camel_to_snake(name: str) -> str:
        """Convert name from CamelCase to snake_case"""
        name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()

    def get_possible_table_columns(self, assets: list[Eu5AdvancedEntity]):
        column_types = get_type_hints(assets[0].__class__)
        if 'modifier' in column_types:
            modifier_is_filled = False
            for item in assets:
                if item.modifier and len(item.modifier) > 0:
                    modifier_is_filled = True
                    break
            if not modifier_is_filled:
                del column_types['modifier']
        return column_types

    def get_value_formatting_code(self, var_name, attribute_name, attribute_type, attribute_loc, cargo=False):
        if var_name:
            attribute_access = f'{var_name}.{attribute_name}'
        else:
            attribute_access = f'{attribute_name}'
        origin = get_origin(attribute_type)
        type_args = get_args(attribute_type)
        if origin == UnionType:
            return self.get_value_formatting_code(var_name, attribute_name, type_args[0], attribute_loc, cargo)
        elif origin == list:
            if inspect.isclass(type_args[0]) and issubclass(type_args[0], (Eu5Modifier, Modifier)):
                return f"self.format_modifier_section('{attribute_name}', {var_name})"
            else:
                if cargo:
                    return f"';'.join([{self.get_value_formatting_code(None, attribute_name, type_args[0], attribute_loc, cargo)} for {attribute_name} in {attribute_access}])"
                else:
                    return f"self.create_wiki_list([{self.get_value_formatting_code(None, attribute_name, type_args[0], attribute_loc, cargo)} for {attribute_name} in {attribute_access}])"
        elif origin == dict:
            if cargo:
                return f"';'.join([{self.get_value_formatting_code(None, attribute_name, type_args[1], attribute_loc, cargo)} for {attribute_name} in {attribute_access}])"
            else:
                return f"self.create_wiki_list([{self.get_value_formatting_code(None, attribute_name, type_args[1], attribute_loc, cargo)} for {attribute_name} in {attribute_access}.values()])"
        if attribute_type in [int, str, float]:
            return attribute_access
        elif attribute_type == bool:
            if cargo:
                return f'1 if {attribute_access} else 0'
            else:
                return f"'[[File:Yes.png|20px|{attribute_loc}]]' if {attribute_access} else '[[File:No.png|20px|Not {attribute_loc}]]'"
        elif attribute_type == Any:
            return attribute_access
        elif issubclass(attribute_type, Trigger):
            return f'self.formatter.format_trigger({attribute_access})'
        elif issubclass(attribute_type, Effect):
            return f'self.formatter.format_effect({attribute_access})'
        elif issubclass(attribute_type, Cost) or issubclass(attribute_type, Price) or issubclass(attribute_type, GoodsDemand):
            return f"{attribute_access}.format(icon_only=True) if hasattr({attribute_access}, 'format') else {attribute_access}"
        elif hasattr(attribute_type, 'format'):
            return f"{attribute_access}.format() if hasattr({attribute_access}, 'format') else {attribute_access}"
        elif issubclass(attribute_type, Eu5AdvancedEntity) and attribute_type.has_wiki_icon():
            return f"{attribute_access}.get_wiki_link_with_icon() if {attribute_access} else ''"
        elif issubclass(attribute_type, NameableEntity):
            return f"{attribute_access}.display_name if {attribute_access} else ''"
        elif issubclass(attribute_type, Tree):
            return f"self.create_wiki_list([f'{{k}}: ...' for k in {attribute_access}.keys()]) if {attribute_access} else ''"

        else:
            return "'grota must implement or delete'"

    def get_cargo_type(self, attribute_type):
        origin = get_origin(attribute_type)
        type_args = get_args(attribute_type)
        if origin == UnionType:
            return self.get_cargo_type(type_args[0])
        elif origin == list:
            if issubclass(type_args[0], Eu5Modifier):
                return 'Wikitext'
            else:
                return f'List (;) of {self.get_cargo_type(type_args[0])}'

        if attribute_type == int:
            return 'Integer'
        elif attribute_type == float:
            return 'Float'
        elif attribute_type == str:
            return 'Text'
        else:
            return 'Wikitext'

    def print_possible_table_columns_with_autogenerated_section_tags(self, parser_property_name: str, var_name: str, ignored_attributes: Set = None,
                                     cargo: bool = False, indent: int = 0):
        """separates the function which creates the table from the generate_ function which creates the text files,
        so that the generate_ function can add <section begin=autogenerated_ tags"""
        table_generator_function = f'get_{parser_property_name}_table'
        generate_function = f'generate_{parser_property_name}_table'
        function_dec_indent_str = ' ' * indent
        base_indent_str = ' ' * (indent + 4)
        print(f'{function_dec_indent_str}def {table_generator_function}(self):')
        print(f'{base_indent_str}return self.surround_with_autogenerated_section({parser_property_name}, self.{table_generator_function}(), add_version_header=True)')
        self.print_possible_table_columns(parser_property_name, var_name, ignored_attributes, cargo, indent, table_generator_function)

    def print_possible_table_columns(self, parser_property_name: str, var_name: str, ignored_attributes: Set = None,
                                     cargo: bool = False, indent: int = 0, table_generator_function: str = None):
        # extra_data = self._get_loc_and_variable_types_from_code(code_folder)
        if table_generator_function is None:
            table_generator_function = f'generate_{parser_property_name}_table'

        entities = getattr(eu5game.parser, parser_property_name)

        function_dec_indent_str = ' ' * indent
        base_indent_str = ' ' * (indent + 4)
        level1_indent_str = ' ' * (indent + 8)
        if not isinstance(entities, list):
            entities = list(entities.values())
        localizations = self.parser._localization_dict
        ignored_names = {'cs2_class', 'file_name', 'path_id', 'parent_asset', 'transform_value_functions', 'extra_data_functions', 'icon_folder', 'name', 'description', 'display_name', 'icon', 'color'}
        if ignored_attributes:
            ignored_names |= ignored_attributes

        common_locs = {'display_name': 'Name',
                       'lotWidth': 'Width',
                       'lotDepth': 'Depth',
                       'groundPollution': 'Ground pollution',
                       'airPollution': 'Air pollution',
                       'noisePollution': 'Noise pollution'
                       }
        default_values = entities[0].default_values
        main_class = entities[0].__class__.__name__
        columns = self.get_possible_table_columns(entities)

        result_var_name = f'{var_name}_table_data'


        print(f'{function_dec_indent_str}def {table_generator_function}(self):')
        source_var_name = f'{var_name}s'
        print(f'{base_indent_str}{source_var_name} = self.parser.{parser_property_name}.values()')
        if cargo:
            cargo_declare_lines = [
                '{{#cargo_declare:',
                f'_table = {self.camel_to_snake(main_class)}',
                '|name = String',
                '|display_name = String',
            ]
            cargo_preview_lines = [
                '{|class = "mildtable"',
                '|-',
                '! name || {{{name|}}}',
                '|-',
                '! display_name || {{{display_name|}}}',
            ]
            print(f"{level1_indent_str}'name': {var_name}.name,")
            print(f"{level1_indent_str}'display_name': {var_name}.display_name,")
            if 'description' in columns:
                cargo_declare_lines.append('|description = String')
                cargo_preview_lines.append('|-')
                cargo_preview_lines.append('! description || {{{description|}}}')
                print(f"{level1_indent_str}'description': {var_name}.description,")
            if 'icon' in columns:
                cargo_declare_lines.append('|icon = File')
                cargo_preview_lines.append('|-')
                cargo_preview_lines.append('! icon || {{{icon|}}}')
                print(f"{level1_indent_str}'icon': {var_name}.get_wiki_filename(),")
        else:
            print(f'{base_indent_str}{result_var_name} = [{{')
            if 'icon' in columns and entities[0].has_wiki_icon() and 'description' in columns:
                name_column = f"f'{{{{{{{{iconbox|{{{var_name}.display_name}}|{{{var_name}.description}}|w=300px|image={{{var_name}.get_wiki_filename()}}}}}}}}}}'"
            else:
                name_column = f'{var_name}.display_name'
            if 'color' in columns:
                name_column = f"f' style=\"background-color: {{{var_name}.color.get_css_color_string() if {var_name}.color else \"white\"}}\" | ' + {name_column}"
            print(f"{level1_indent_str}'Name': {name_column},")

        for attribute, typ in columns.items():
            if attribute in ignored_names:
                continue
            if attribute.startswith('_') and hasattr(entities[0], attribute.removeprefix('_')):
                attribute = attribute.removeprefix('_')
            # if isinstance(loc_or_dict, Mapping):
            #     # save for later to print the main attributes first
            #     sub_attributes[attribute] = loc_or_dict
            # else:
            if cargo:
                loc = attribute
                cargo_declare_lines.append(f'|{attribute} = {self.get_cargo_type(typ)}')
                cargo_preview_lines.append('|-')
                cargo_preview_lines.append(f'! {attribute} || {{{{{{{attribute}|}}}}}}')

            elif attribute in common_locs:
                loc = common_locs[attribute]
            elif attribute in localizations:
                loc = self.parser.localize(attribute)
            else:
                loc = attribute.replace('_', ' ').title()
            if attribute in default_values and default_values[attribute] is None and typ not in [Effect, Trigger]:
                none_check = f"'' if {var_name}.{attribute} is None else "
            else:
                none_check = ''
            print(f"{level1_indent_str}'{loc}': {none_check}{self.get_value_formatting_code(var_name, attribute, typ, loc, cargo)},  # {attribute}: {typ}")
            # else:
            #     print(f"'{types}': {var_name}.{attribute},")

        if cargo:
            print('\n ==Cargo table declaration==\n')
            cargo_declare_lines.append('}}')
            print('\n'.join(cargo_declare_lines))
            print('\n ==Cargo preview table==\n')
            cargo_preview_lines.append('|}')
            print('\n'.join(cargo_preview_lines))
        else:
            print(f'{base_indent_str}}} for {var_name} in {source_var_name}]')
            print(f"""{base_indent_str}return self.make_wiki_table({result_var_name}, table_classes=['mildtable', 'plainlist'],
                                        one_line_per_cell=True,
                                        remove_empty_columns=True,
                                        )""")
        # for attribute, dic in sub_attributes.items():
        #     for sub_attribute, loc in dic.items():
        #         if attribute in extra_data and sub_attribute in extra_data[attribute]:
        #             print(f"'{extra_data[attribute][sub_attribute]['loc']}': {var_name}.{attribute}.{sub_attribute} if '{attribute}' in {var_name} else '',  # {extra_data[attribute][sub_attribute]['var_type']}")
        #         else:
        #             print(f"'{loc}': {var_name}.{attribute}.{sub_attribute} if '{attribute}' in {var_name} else '',")


class Eu5MultiTypeHelper(MultiTypeHelper):
    def __init__(self):
        self.parser = eu5game.parser


    def create_helper(self, folder: str, **kwargs) -> OneTypeHelper:
        return Eu5OneTypeHelper(folder, **kwargs)

    def print_base_code_for_missing_types(self, glob='*/common/*',
                                          already_parsed_folders: Iterable[str] = (),
                                          ignored_folders: Iterable[str]=(),
                                          newlines_between_classes: int = 2,
                                          newlines_between_parsing: int = 1
                                          ):
        return super().print_base_code_for_missing_types(glob, already_parsed_folders, ignored_folders,
                                                  newlines_between_classes, newlines_between_parsing)


def get_basic_parsing():
    helper = Eu5MultiTypeHelper()
    parsed_folders = ['in_game/common/advances', 'in_game/common/age', 'in_game/common/building_categories',
                      'in_game/common/building_types', 'in_game/common/climates',
                      'in_game/common/country_description_categories', 'in_game/common/culture_groups',
                      'in_game/common/cultures', 'in_game/common/estate_privileges', 'in_game/common/estates',
                      'in_game/common/goods', 'in_game/common/goods_demand', 'in_game/common/government_types',
                      'in_game/common/institution', 'in_game/common/language_families', 'in_game/common/languages',
                      'in_game/common/laws', 'in_game/common/location_ranks', 'in_game/common/pop_types',
                      'in_game/common/prices', 'in_game/common/production_methods',
                      'in_game/common/religion_groups', 'in_game/common/religions',
                      'in_game/common/religious_aspects', 'in_game/common/religious_factions',
                      'in_game/common/religious_focuses', 'in_game/common/religious_schools',
                      'in_game/common/script_values', 'in_game/common/topography', 'in_game/common/vegetation',
                      'in_game/map_data/',
                      'in_game/setup/countries', 'loading_screen/common/defines',
                      'loading_screen/common/named_colors', 'main_menu/common/game_concepts',
                      'main_menu/common/modifier_icons', 'main_menu/common/modifiers',
                      'main_menu/common/modifier_types', 'main_menu/common/named_colors',
                      'main_menu/common/script_values', 'main_menu/setup/start/', 'main_menu/setup/templates/']
    # result = helper.print_base_code_for_missing_types(already_parsed_folders=parsed_folders,
    #                                                       ignored_folders=['in_game/common/tests',
    #                                                                    'in_game/common/tutorial_lesson_chains',
    #                                                                    'in_game/common/tutorial_lessons',
    #
    #                                                                        'main_menu/common/coat_of_arms'
    #                                                                    ],
    #                                                   newlines_between_classes=0,
    #                                                   newlines_between_parsing=0)
    result = helper.get_helpers_for_missing_folders(
        glob='*/common/*',
        already_parsed_folders=parsed_folders,
        ignored_folders=['in_game/common/tests',
                         'in_game/common/tutorial_lesson_chains',
                         'in_game/common/tutorial_lessons',

                         'main_menu/common/coat_of_arms'
                         ],
    )
    result = sorted(result.values(), key=methodcaller('get_possible_class_name'))
    for helper in result:
        # print(f'eu5lib.{helper.get_possible_class_name()}: \'{helper.get_parser_function_name()}\',')
        # print(f'{helper.get_possible_class_name()}: {len(helper.entity_names)}')
        # print(helper.get_possible_loc_prefixes_or_suffixes())
        print(helper.get_parsing_code())

def advanced_parsing_multiple():
    helper = Eu5MultiTypeHelper()
    parsed_folders = [
        # 'in_game/common/advances', 'in_game/common/age', 'in_game/common/building_categories',
        #               'in_game/common/building_types', 'in_game/common/climates',
        #               'in_game/common/country_description_categories', 'in_game/common/culture_groups',
        #               'in_game/common/cultures', 'in_game/common/estate_privileges', 'in_game/common/estates',
        #               'in_game/common/goods', 'in_game/common/goods_demand', 'in_game/common/government_types',
        #               'in_game/common/institution', 'in_game/common/language_families', 'in_game/common/languages',
        #               'in_game/common/laws', 'in_game/common/location_ranks', 'in_game/common/pop_types',
        #               'in_game/common/prices', 'in_game/common/production_methods',
        #               'in_game/common/religion_groups', 'in_game/common/religions',
        #               'in_game/common/religious_aspects', 'in_game/common/religious_factions',
        #               'in_game/common/religious_focuses', 'in_game/common/religious_schools',
        #               'in_game/common/topography', 'in_game/common/vegetation',
                      'in_game/common/script_values',
                      'in_game/map_data/',
                      'in_game/setup/countries', 'loading_screen/common/defines',
                      'loading_screen/common/named_colors', 'main_menu/common/game_concepts',
                      'main_menu/common/modifier_icons', 'main_menu/common/modifiers',
                      'main_menu/common/modifier_types', 'main_menu/common/named_colors',
                      'main_menu/common/script_values', 'main_menu/setup/start/', 'main_menu/setup/templates/']
    result = helper.get_helpers_for_missing_folders(
        glob='*/common/*',
        already_parsed_folders=parsed_folders,
        ignored_folders=['in_game/common/tests',
                         'in_game/common/tutorial_lesson_chains',
                         'in_game/common/tutorial_lessons',

                         'main_menu/common/coat_of_arms',
                         'in_game/common/auto_modifiers',

                         # 'in_game/common/scripted_effects',
                         # 'in_game/common/scripted_triggers',
                         ],
        class_name_map={
            'ReligiousFocuse': 'ReligiousFocus',
            'Biase': 'Bias',
            'BuildingType': 'Building',
        }
    )
    result = sorted(result.values(), key=methodcaller('get_possible_class_name'))
    result_dict = {res.get_possible_class_name(): res for res in result}
    types_which_need_quotes = [helper.get_possible_class_name() for helper in result]
    # for helper in result:

    found_classes = set(result_dict.keys())
    for class_name in ['Eu5ModifierType', 'Eu5Modifier', 'Eu5NamedModifier', 'Eu5AdvancedEntity', 'ScriptValue', 'Location', 'Province', 'Area', 'Region', 'SubContinent', 'Continent', 'Advance', 'Resource', 'HardcodedResource', 'GoodCategory', 'Good', 'ResourceValue:', 'Cost', 'Price', 'GoodsDemand', 'NoPrice', 'ProductionMethod', 'Age', 'BuildingCategory', 'Building', 'Climate', 'CountryDescriptionCategory', 'Country', 'CultureGroup', 'Culture', 'Estate', 'EstatePrivilege', 'HeirSelection', 'Eu5GameConcept', 'GovernmentType', 'Institution', 'LanguageFamily', 'Language', 'LawPolicy', 'Law', 'LocationRank', 'PopType', 'ReligiousAspect', 'ReligiousFaction', 'ReligiousFocus', 'ReligionGroup', 'ReligiousSchool', 'Religion', 'Topography', 'Vegetation', 'InternationalOrganization', 'ScriptedList', 'Achievement', 'AiDiplochance', 'ArtistType', 'ArtistWork', 'AttributeColumn', 'AutoModifier', 'Avatar', 'Bias', 'CabinetAction', 'CasusBelli', 'CharacterInteraction', 'ChildEducation', 'CoatOfArms', 'CountryInteraction', 'CountryRank', 'CustomizableLocalization', 'DeathReason', 'DesignatedHeirReason', 'DiplomaticCost', 'Disaster', 'Disease', 'EffectLocalization', 'EmploymentSystem', 'Ethnicity', 'FlagDefinition', 'FormableCountry', 'GameRule', 'Gene', 'GenericAction', 'GenericActionAiList', 'God', 'GoodsDemandCategory', 'GovernmentReform', 'Hegemon', 'HistoricalScore', 'HolySite', 'HolySiteType', 'Insult', 'InternationalOrganizationLandOwnershipRule', 'InternationalOrganizationPayment', 'InternationalOrganizationSpecialStatus', 'Levy', 'Mission', 'OnAction', 'ParliamentAgenda', 'ParliamentIssue', 'ParliamentType', 'PeaceTreaty', 'PersistentDna', 'RecruitmentMethod', 'Regency', 'ReligiousFigure', 'Resolution', 'RivalCriteria', 'RoadType', 'Scenario', 'ScriptableHint', 'ScriptedCountryName', 'ScriptedDiplomaticObjective', 'ScriptedEffect', 'ScriptedRelation', 'ScriptedTrigger', 'Situation', 'SocietalValue', 'SubjectMilitaryStance', 'SubjectType', 'TownSetup', 'Trait', 'TraitFlavor', 'TriggerLocalization', 'UnitAbility', 'UnitCategory', 'UnitType', 'Wargoal',]:
        if class_name not in result_dict:
            # print(f'skipping {class_name}')
            continue
        else:
            found_classes.remove(class_name)
        helper = result_dict[class_name]
        print(f"    ('{helper.folder}', '{helper.get_parser_function_name()}', '{helper.get_parser_function_name()}'),")
        # print(helper.get_full_class_definition(types_which_need_quotes))
        # types_which_need_quotes.remove(helper.get_possible_class_name())

    # for class_name in found_classes:
    #     print(f'missing {class_name}')

def advanced_parsing():
    Eu5OneTypeHelper(
        # 'in_game/common/casus_belli'
        # 'in_game/common/artist_work'
        # 'in_game/common/auto_modifiers',
        # 'main_menu/common/static_modifiers',
        'in_game/common/parliament_issues',
        # depth=2,
        # ignored_keys=list(eu5game.parser.modifier_types.keys())
        # ignored_toplevel_keys=['current_age', 'road_network'],

    ).print_examples_and_code()

def table_generators(table_options: list):
    options_helpers = sorted([(var_name, folder, parser_property_name, Eu5OneTypeHelper(folder)) for folder, var_name, parser_property_name in table_options])
    options_helpers = list(options_helpers)
    # print('\n\n==table generator code==\n')
    print('\n\n    # AUTOGENERATED\n')
    for var_name, folder, parser_property_name, helper in options_helpers:

        helper.print_possible_table_columns_with_autogenerated_section_tags(parser_property_name,
                                            var_name,
                                            # ignored_attributes = set(messages_for_non_default_values.keys()),
                                            # cargo=True
                                            indent=4,
                                            )
    # # this is in another project which might not be public
    # print(f'\n\n== code for update_autogenerated_tables in wikimirror/management/commands/updatepageseu5.py == ')
    # for var_name, folder, parser_property_name, helper in options_helpers:
    #     print(f"    '{parser_property_name}': generator.get_{parser_property_name}_table(),")
    print(f'\n\n== section tags for the wiki ==')
    for var_name, folder, parser_property_name, helper in options_helpers:
        print(FileGenerator(eu5game).surround_with_autogenerated_section(parser_property_name, ''))

def table_generator(folder, var_name, parser_property_name):
    building = next(iter(eu5game.parser.buildings.values()))
    messages_for_non_default_values = {
        'always_add_demands': 'Demand does not scale with workers',
        'AI_ignore_available_worker_flag': 'Build by AI even without available workers',
        'AI_optimization_flag_coastal': '',
        'allow_wrong_startup': '<tt>allow_wrong_startup</tt>',
        'can_close': 'Cannot be closed',
        'conversion_religion': f'Converts pops to {building.conversion_religion}',
        'forbidden_for_estates': 'Cannot be build by estates',
        'increase_per_level_cost': f'Cost changes by {building.increase_per_level_cost} per level',
        'in_empty': f'Can { building.in_empty} be built in empty locations',
        'is_foreign': 'Foreign building',
        'lifts_fog_of_war': 'Lifts fog of war',
        'need_good_relation': 'Needs good relations when building in foreign provinces',
        'pop_size_created': f'Creates {building.pop_size_created} pops when building(taken from the capital of the owner)',
        'stronger_power_projection': 'Requires more power projection to construct in a foreign location',
    }

    # Eu5OneTypeHelper('in_game/common/parliament_issues').print_possible_table_columns(eu5game.parser.parliament_issues,
    #                                          'issue',
    #                                                 # ignored_attributes = set(messages_for_non_default_values.keys()),
    #                                                 # cargo=True
    #                                                 )

    helper = Eu5OneTypeHelper(folder)
    print('\n\n==table generator code==\n')
    helper.print_possible_table_columns(parser_property_name,
                                        var_name,
                                        # ignored_attributes = set(messages_for_non_default_values.keys()),
                                        # cargo=True
                                        indent=4,
                                        )
    print(f'\n\n== code for update_autogenerated_tables in wikimirror/management/commands/updatepageseu5.py == ')
    print(f"    '{parser_property_name}': generator.generate_{parser_property_name}_table(),")

    print(f'\n\n== section tags for the wiki ==')
    print(FileGenerator(eu5game).surround_with_autogenerated_section(parser_property_name, ''))

def generate_tables_all():
    table_generators([
        
    
        ('in_game/common/cultures', 'cultures', 'cultures'),
    # table_generator(folder='in_game/common/parliament_issues', var_name='parliament_issues',
    #                 parser_property_name='parliament_issues')
        ('in_game/common/traits', 'trait', 'traits'),
        ('in_game/common/holy_sites', 'holy_sites', 'holy_sites'),
        ('in_game/common/religions', 'religions', 'religions'),
        ('in_game/common/unit_types', 'unit_types', 'unit_types'),
        ('in_game/common/wargoals', 'wargoals', 'wargoals'),
        ('in_game/common/casus_belli', 'casus_belli', 'casus_belli'),
        ('in_game/common/levies', 'levies', 'levies'),
        ('in_game/common/government_reforms', 'government_reforms', 'government_reforms'),
        ('in_game/common/advances', 'advances', 'advances'),
        ('in_game/common/subject_types', 'subject_types', 'subject_types'),
        ('in_game/common/cabinet_actions', 'cabinet_actions', 'cabinet_actions'),
        ('in_game/common/religious_aspects', 'religious_aspects', 'religious_aspects'),
        ('in_game/common/religious_schools', 'religious_schools', 'religious_schools'),
        ('in_game/common/peace_treaties', 'peace_treaties', 'peace_treaties'),
        ('in_game/common/parliament_agendas', 'parliament_agendas', 'parliament_agendas'),
        ('in_game/common/languages', 'languages', 'languages'),
    ])
    # missing:
    # Starting countries
    # hints
    # art
    # religious actions
    # formable countries
    # succession laws
    return
    a =[
        ('in_game/common/goods', 'goods', 'goods'),
        ('in_game/common/prices', 'prices', 'prices'),
        ('in_game/common/goods_demand', 'goods_demand', 'goods_demand'),
        ('in_game/common/production_methods', 'production_methods', 'production_methods'),
        ('in_game/common/age', 'age', 'age'),
        ('in_game/common/building_categories', 'building_categories', 'building_categories'),
        ('in_game/common/building_types', 'building_types', 'building_types'),
        ('in_game/common/climates', 'climates', 'climates'),
        ('in_game/common/country_description_categories', 'country_description_categories', 'country_description_categories'),
        ('in_game/common/culture_groups', 'culture_groups', 'culture_groups'),

        ('in_game/common/estates', 'estates', 'estates'),
        ('in_game/common/estate_privileges', 'estate_privileges', 'estate_privileges'),
        ('in_game/common/heir_selections', 'heir_selections', 'heir_selections'),
        ('in_game/common/government_types', 'government_types', 'government_types'),
        ('in_game/common/institution', 'institution', 'institution'),
        ('in_game/common/language_families', 'language_families', 'language_families'),
        ('in_game/common/languages', 'languages', 'languages'),
        ('in_game/common/laws', 'laws', 'laws'),
        ('in_game/common/location_ranks', 'location_ranks', 'location_ranks'),
        ('in_game/common/pop_types', 'pop_types', 'pop_types'),

        ('in_game/common/religious_factions', 'religious_factions', 'religious_factions'),
        ('in_game/common/religious_focuses', 'religious_focuses', 'religious_focuses'),
        ('in_game/common/religion_groups', 'religion_groups', 'religion_groups'),


        ('in_game/common/topography', 'topography', 'topography'),
        ('in_game/common/vegetation', 'vegetation', 'vegetation'),
        ('in_game/common/international_organizations', 'international_organizations', 'international_organizations'),
        ('in_game/common/scripted_lists', 'scripted_lists', 'scripted_lists'),
        ('main_menu/common/achievements', 'achievements', 'achievements'),
        ('in_game/common/ai_diplochance', 'ai_diplochance', 'ai_diplochance'),
        ('in_game/common/artist_types', 'artist_types', 'artist_types'),
        ('in_game/common/artist_work', 'artist_work', 'artist_work'),
        ('in_game/common/attribute_columns', 'attribute_columns', 'attribute_columns'),
        ('in_game/common/avatars', 'avatars', 'avatars'),
        ('in_game/common/biases', 'biases', 'biases'),


        ('in_game/common/character_interactions', 'character_interactions', 'character_interactions'),
        ('in_game/common/child_educations', 'child_educations', 'child_educations'),
        ('in_game/common/country_interactions', 'country_interactions', 'country_interactions'),
        ('in_game/common/country_ranks', 'country_ranks', 'country_ranks'),
        ('in_game/common/customizable_localization', 'customizable_localization', 'customizable_localization'),
        ('in_game/common/death_reason', 'death_reason', 'death_reason'),
        ('in_game/common/designated_heir_reason', 'designated_heir_reason', 'designated_heir_reason'),
        ('in_game/common/diplomatic_costs', 'diplomatic_costs', 'diplomatic_costs'),
        ('in_game/common/disasters', 'disasters', 'disasters'),
        ('in_game/common/diseases', 'diseases', 'diseases'),
        ('in_game/common/effect_localization', 'effect_localization', 'effect_localization'),
        ('in_game/common/employment_systems', 'employment_systems', 'employment_systems'),
        ('in_game/common/ethnicities', 'ethnicities', 'ethnicities'),
        ('main_menu/common/flag_definitions', 'flag_definitions', 'flag_definitions'),
        ('in_game/common/formable_countries', 'formable_countries', 'formable_countries'),
        ('main_menu/common/game_rules', 'game_rules', 'game_rules'),
        ('in_game/common/genes', 'genes', 'genes'),
        ('in_game/common/generic_actions', 'generic_actions', 'generic_actions'),
        ('in_game/common/generic_action_ai_lists', 'generic_action_ai_lists', 'generic_action_ai_lists'),
        ('in_game/common/gods', 'gods', 'gods'),
        ('in_game/common/goods_demand_category', 'goods_demand_category', 'goods_demand_category'),

        ('in_game/common/hegemons', 'hegemons', 'hegemons'),
        ('in_game/common/historical_scores', 'historical_scores', 'historical_scores'),

        ('in_game/common/holy_site_types', 'holy_site_types', 'holy_site_types'),
        ('in_game/common/insults', 'insults', 'insults'),
        ('in_game/common/international_organization_land_ownership_rules', 'international_organization_land_ownership_rules', 'international_organization_land_ownership_rules'),
        ('in_game/common/international_organization_payments', 'international_organization_payments', 'international_organization_payments'),

        ('in_game/common/missions', 'missions', 'missions'),
        ('in_game/common/on_action', 'on_action', 'on_action'),


        ('in_game/common/parliament_types', 'parliament_types', 'parliament_types'),

        ('in_game/common/persistent_dna', 'persistent_dna', 'persistent_dna'),
        ('in_game/common/recruitment_method', 'recruitment_method', 'recruitment_method'),
        ('in_game/common/regencies', 'regencies', 'regencies'),
        ('in_game/common/religious_figures', 'religious_figures', 'religious_figures'),
        ('in_game/common/resolutions', 'resolutions', 'resolutions'),
        ('in_game/common/rival_criteria', 'rival_criteria', 'rival_criteria'),
        ('in_game/common/road_types', 'road_types', 'road_types'),
        ('main_menu/common/scenarios', 'scenarios', 'scenarios'),
        ('in_game/common/scriptable_hints', 'scriptable_hints', 'scriptable_hints'),
        ('in_game/common/scripted_country_names', 'scripted_country_names', 'scripted_country_names'),
        ('in_game/common/scripted_diplomatic_objectives', 'scripted_diplomatic_objectives', 'scripted_diplomatic_objectives'),
        ('in_game/common/scripted_effects', 'scripted_effects', 'scripted_effects'),
        ('in_game/common/scripted_relations', 'scripted_relations', 'scripted_relations'),
        ('main_menu/common/scripted_triggers', 'scripted_triggers', 'scripted_triggers'),
        ('in_game/common/situations', 'situations', 'situations'),
        ('in_game/common/societal_values', 'societal_values', 'societal_values'),
        ('in_game/common/subject_military_stances', 'subject_military_stances', 'subject_military_stances'),

        ('in_game/common/town_setups', 'town_setups', 'town_setups'),

        ('in_game/common/trait_flavor', 'trait_flavor', 'trait_flavor'),
        ('in_game/common/trigger_localization', 'trigger_localization', 'trigger_localization'),
        ('in_game/common/unit_abilities', 'unit_abilities', 'unit_abilities'),
        ('in_game/common/unit_categories', 'unit_categories', 'unit_categories'),
    ]



if __name__ == '__main__':
    #     ('in_game/common/estate_privileges', 'privilege', 'estate_privileges'),
    generate_tables_all()
    exit()
    do_advanced = True
    if do_advanced or len(sys.argv) > 1:
        advanced_parsing_multiple()
    else:
        # advanced_parsing_multiple()
        advanced_parsing()
    # get_basic_parsing()

