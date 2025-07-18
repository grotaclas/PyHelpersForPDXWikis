"""

Generates lua data modules

"""
import luadata
import sys

from eu5.eu5_file_generator import Eu5FileGenerator


class LuaDataGenerator(Eu5FileGenerator):
    def generate_defines_list_lua(self) -> str:
        """
        generates https://eu5.paradoxwikis.com/Module:Defines/List

        """
        result = self.parser.defines.to_dict()
        return f'''
local NDefines = {luadata.serialize(result, indent=' ')}
'''

    def generate_modifier_data_lua(self):
        result = {}
        for mod_type in self.parser.modifier_types.values():
            mod_data = {'loc': self.parser.formatter.strip_formatting(mod_type.display_name), }
            if mod_type.is_percent:
                mod_data['is_percent'] = True
            if mod_type.already_percent:
                mod_data['already_percent'] = True
            if mod_type.is_bool:
                mod_data['is_bool'] = True
            if mod_type.format != '':
                mod_data['format'] = mod_type.format
            mod_data['is_good'] = mod_type.is_good
            mod_data['num_decimals'] = mod_type.num_decimals

            if mod_type.icon_file != self.parser.default_modifier_icon:
                mod_data['icon'] = mod_type.get_wiki_filename().removesuffix('.png')
            result[mod_type.name] = mod_data

        return '''
local p = ''' + luadata.serialize(result, indent=' ')

    def generate_named_modifier_data_lua(self):
        """The format is:
            modifier_script_name = {
                 category = 'value',
                 loc = 'localized name',
                 desc = 'localized desc',
                 mods = {
                    list of modifier effects,
                },
            },
        """
        result = {}
        for named_mod in self.parser.named_modifiers.values():
            mod_data = {'category': named_mod.category,
                        'loc': named_mod.display_name,
                        'mods': { mod.modifier_type.name: mod.value.format() if hasattr(mod.value, 'format') else mod.value for mod in named_mod.modifier}}
            if named_mod.description:
                mod_data['desc'] = named_mod.description.replace('\n', '<br>')

            result[named_mod.name] = mod_data
        return '''
local p = ''' + luadata.serialize(result, indent=' ')

if __name__ == '__main__':
    LuaDataGenerator().run(sys.argv)
