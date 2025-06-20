"""

Generates lua data modules

"""
import luadata
import sys

from vic3.vic3_file_generator import Vic3FileGenerator
from vic3.vic3lib import Technology


class LuaDataGenerator(Vic3FileGenerator):
    def generate_technology_data_lua(self) -> str:
        """
        generates https://vic3.paradoxwikis.com/Module:Technology/List

        """
        result = {
            tech.name: {
                'loc': tech.display_name,
                'desc': tech.description,
                'era': tech.era,
                'category': self.parser.localize(tech.category),
                'reqs': [req.name for req in tech.required_technologies],
                'unlocks': self._get_unlock_lists(tech),
                'modifiers': [modifier.format_for_lua() for modifier in tech.modifier],
            }
            for tech in self.parser.technologies.values()
        }
        return luadata.serialize(result, indent=' ')

    def _get_unlock_lists(self, tech: Technology):
        result = {}

        building_unlocks = [building.display_name for building in self.parser.buildings.values() if tech in building.required_technologies]
        if building_unlocks:
            result['building'] = building_unlocks

        decree_unlocks = [decree.display_name for decree in self.parser.decrees.values() if tech in decree.required_technologies]
        if decree_unlocks:
            result['decree'] = decree_unlocks

        ideology_unlocks = [ideology.display_name for ideology in self.parser.ideologies.values() if tech in ideology.required_technologies]
        if ideology_unlocks:
            result['ideology'] = ideology_unlocks

        return result


    def generate_character_data_lua(self):
        """experimental unfinished"""
        lua_tables = []
        for character in self.parser.characters.values():
            roles = ', '.join(f'"{role}"' for role in character.get_roles())
            traits = ', '.join(f'"{trait}"' for trait in character.traits)
            if character.start:
                start = f' startDate = "{character.start}",\n'
            else:
                start = ''
            if character.end:
                end = f' endDate = "{character.end}",\n'
            else:
                end = ''
            if character.commander_rank:
                rank = f' rank = "{character.commander_rank}",\n'
            else:
                rank = ''
            lua_tables.append(f'''p["{character.template.name if character.template else character.name}"] = {{
 name = "{character.display_name}",
 roles = {{ {roles} }},
 ig = "{character.interest_group.display_name if character.interest_group is not None else ''}",
 ideology = "{character.ideology}",
 traits = {{ {traits} }},
 dlc = "{character.dlc}",
{start}{end}{rank}
}}''')
        return '''--[[
This module lists all characters.
It's meant to be required by "Module:Character"

It is autogenerated with https://github.com/grotaclas/PyHelpersForPDXWikis/blob/main/vic3/generate_tables.py (parameter character_data_lua) and automatically
updated. Please note suggestions for changes on the talk page or raise an issue on github, because manual changes will be overwritten.
]]--
local p = {};
''' + '\n\n'.join(lua_tables) + '\n\nreturn p'


if __name__ == '__main__':
    LuaDataGenerator().run(sys.argv)