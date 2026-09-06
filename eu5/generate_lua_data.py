"""

Generates lua data modules

"""
import luadata
import os
import sys

from typing import Any

# add the parent folder to the path so that imports work even if this file gets executed directly
sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from eu5.eu5_file_generator import Eu5FileGenerator
from eu5.eu5lib import Eu5NamedModifier, AutoModifier


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
            mod_data = {'loc': self.parser.formatter.strip_formatting(mod_type.display_name), 'desc': mod_type.description}
            if mod_type.percent:
                mod_data['percent'] = True
            if mod_type.already_percent:
                mod_data['already_percent'] = True
            if mod_type.boolean:
                mod_data['boolean'] = True
            if mod_type.format != '':
                mod_data['format'] = mod_type.format
            mod_data['color'] = mod_type.color
            mod_data['decimals'] = mod_type.decimals
            mod_data['category'] = mod_type.category

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
            result[named_mod.name] = self._get_mod_data(named_mod)
        return '''
local p = ''' + luadata.serialize(result, indent=' ')

    def _get_mod_data(self, modifier: Eu5NamedModifier|AutoModifier) -> dict[str, Any]:
        mod_data = {'category': modifier.category,
                    'loc': modifier.display_name,
                    'mods': {mod.modifier_type.name: mod.value.format() if hasattr(mod.value, 'format') else mod.value
                             for mod in modifier.modifier}}
        if modifier.description:
            mod_data['desc'] = modifier.description.replace('\n', '<br>')
        return mod_data

    def generate_auto_modifier_data_lua(self):
        result = {}
        for modifier in self.parser.auto_modifiers.values():
            mod_data = self._get_mod_data(modifier)
            mod_data['limit'] = self.formatter.format_trigger(modifier.limit)
            mod_data['potential_trigger'] = self.formatter.format_trigger(modifier.potential_trigger)
            mod_data['requires_real'] = modifier.requires_real
            mod_data['scales_with'] = modifier.scales_with.format() if modifier.scales_with else ''
            mod_data['type'] = modifier.type

            result[modifier.name] = mod_data
        return '\n'.join(f'p.{name} = {luadata.serialize(mod_data, indent=' ')}' for name, mod_data in result.items())

if __name__ == '__main__':
    LuaDataGenerator().run(sys.argv)
