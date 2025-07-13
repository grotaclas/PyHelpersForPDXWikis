import re
from collections.abc import Set
from types import UnionType
from typing import get_type_hints, get_origin, get_args

from common.helper import Helper
from common.paradox_lib import IconMixin
from common.paradox_parser import ParsingWorkaround
from eu5.eu5lib import Eu5AdvancedEntity, Cost, GoodsDemand, Price, Eu5Modifier, Trigger, Effect
from eu5.game import eu5game
from eu5.parser import Eu5Parser


class Eu5Helper(Helper):
    parser: Eu5Parser

    def __init__(self):
        super().__init__()
        self.parser = eu5game.parser

    def find_all_keys_in_folder(self, folder, depth=0, ignored_toplevel_keys: list = None, ignored_keys: list = None):
        folder = folder.removeprefix('game/')
        return super().find_all_keys_in_folder(folder, depth, ignored_toplevel_keys, ignored_keys)

    def get_data(self, folder: str):
        if folder.endswith('.txt'):
            glob = folder
        else:
            glob = f'{folder}/*.txt'
        return self.parser.parser.parse_files(glob)

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

    def guess_type(self, attribute_name: str) -> str | None:
        if attribute_name in ['enabled', 'visible', 'potential', 'allow']:
            return 'Trigger'
        if attribute_name.startswith('enabled_'):
            return 'Trigger'
        if attribute_name in ['effect', 'hidden_effect'] or attribute_name.startswith('on_'):
            return 'Effect'
        if 'modifier' in  attribute_name:
            return 'list[Eu5Modifier]', []
        return None


    #####################################################
    # Helper functions to generate new table generators #
    #####################################################

    @staticmethod
    def camel_to_snake(name: str) -> str:
        """Convert name from CamelCase to snake_case"""
        name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()

    def get_possible_table_columns(self, assets: list[Eu5AdvancedEntity]):
        return get_type_hints(assets[0].__class__)

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
            if issubclass(type_args[0], Eu5Modifier):
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
        elif attribute_type == any:
            return attribute_access
        elif issubclass(attribute_type, Trigger):
            return f'self.formatter.format_trigger({attribute_access})'
        elif issubclass(attribute_type, Effect):
            return f'self.formatter.format_effect({attribute_access})'
        elif issubclass(attribute_type, Cost) or issubclass(attribute_type, Price) or issubclass(attribute_type, GoodsDemand):
            return f"{attribute_access}.format(icon_only=True) if hasattr({attribute_access}, 'format') else {attribute_access}"
        elif hasattr(attribute_type, 'format'):
            return f"{attribute_access}.format() if hasattr({attribute_access}, 'format') else {attribute_access}"
        elif issubclass(attribute_type, IconMixin):
            return f"{attribute_access}.get_wiki_link_with_icon() if {attribute_access} else ''"
        else:
            return 'bla'

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

    def print_possible_table_columns(self, entities: list[Eu5AdvancedEntity] | dict[str, Eu5AdvancedEntity], var_name: str, ignored_attributes: Set = None,
                                     cargo: bool = False):
        # extra_data = self._get_loc_and_variable_types_from_code(code_folder)
        if not isinstance(entities, list):
            entities = list(entities.values())
        localizations = self.parser._localization_dict
        ignored_names = {'cs2_class', 'file_name', 'path_id', 'parent_asset', 'transform_value_functions', 'extra_data_functions', 'icon_folder', 'name', 'description', 'display_name', 'icon'}
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
        print('==table generator code==')
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
            print(f"'name': {var_name}.name,")
            print(f"'display_name': {var_name}.display_name,")
            if 'description' in columns:
                cargo_declare_lines.append('|description = String')
                cargo_preview_lines.append('|-')
                cargo_preview_lines.append('! description || {{{description|}}}')
                print(f"'description': {var_name}.description,")
            if 'icon' in columns:
                cargo_declare_lines.append('|icon = File')
                cargo_preview_lines.append('|-')
                cargo_preview_lines.append('! icon || {{{icon|}}}')
                print(f"'icon': {var_name}.get_wiki_filename(),")
        else:
            print(f'{result_var_name} = [{{')
            if 'icon' in columns and 'description' in columns:
                print(f"'Name': f'{{{{{{{{iconbox|{{{var_name}.display_name}}|{{{var_name}.description}}|w=300px|image={{{var_name}.get_wiki_filename()}}}}}}}}}}',")
            else:
                print(f"'Name': f'{{{var_name}.display_name}}',")

        for attribute, typ in columns.items():
            if attribute in ignored_names:
                continue
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
            print(f"'{loc}': {none_check}{self.get_value_formatting_code(var_name, attribute, typ, loc, cargo)},  # {attribute}: {typ}")
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
            source_var_name = f'{var_name}s'
            print(f'}} for {var_name} in {source_var_name}]')
            print(f"""return self.make_wiki_table({result_var_name}, table_classes=['mildtable', 'plainlist'],
                                        one_line_per_cell=True,
                                        remove_empty_columns=True,
                                        )""")
        # for attribute, dic in sub_attributes.items():
        #     for sub_attribute, loc in dic.items():
        #         if attribute in extra_data and sub_attribute in extra_data[attribute]:
        #             print(f"'{extra_data[attribute][sub_attribute]['loc']}': {var_name}.{attribute}.{sub_attribute} if '{attribute}' in {var_name} else '',  # {extra_data[attribute][sub_attribute]['var_type']}")
        #         else:
        #             print(f"'{loc}': {var_name}.{attribute}.{sub_attribute} if '{attribute}' in {var_name} else '',")

if __name__ == '__main__':
    # Eu5Helper().find_all_keys_in_folder('in_game/common/laws',
    #                                     depth=1,
    #                                     ignored_toplevel_keys=[
    #                                         'allow',
    #                                         'law_category',
    #                                         'law_country_group',
    #                                         'law_gov_group',
    #                                         'law_religion_group',
    #                                         'locked',
    #                                         'potential',
    #                                         'requires_vote',
    #                                         'type',
    #                                         'unique',
    #                                     ]
    #                                     # , ignored_keys=list(eu5game.parser.goods.keys())
    #                                     )
    # exit()
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

    Eu5Helper().print_possible_table_columns(list(eu5game.parser.laws.values())[0].policies,
                                             'policy',
                                             # ignored_attributes = set(messages_for_non_default_values.keys()),
                                             # cargo=True
                                             )