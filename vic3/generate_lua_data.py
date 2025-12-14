"""

Generates lua data modules

"""
import re
import os

import luadata
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from operator import attrgetter
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
                'modifiers': self._get_modifier_list(tech.modifier),
                #'modifiers': [modifier.format_for_lua() for modifier in tech.modifier],
            }
            for tech in self.parser.technologies.values()
        }
        return luadata.serialize(result, indent=' ')

    def _get_unlock_lists(self, tech: Technology):
        result = {}

        building_unlocks = [building.name for building in self.parser.buildings.values() if tech in building.required_technologies]
        if building_unlocks:
            result['building'] = building_unlocks

        decree_unlocks = [decree.name for decree in self.parser.decrees.values() if tech in decree.required_technologies]
        if decree_unlocks:
            result['decree'] = decree_unlocks

        diplomacy_unlocks = [diplomatic_action.display_name for diplomatic_action in self.parser.diplomatic_actions.values() if tech in diplomatic_action.required_technologies]
        treaty_unlocks = [treaty_article.display_name for treaty_article in self.parser.treaty_articles.values() if tech in treaty_article.required_technologies]
        if diplomacy_unlocks or treaty_unlocks:
            result['diplomacy'] = diplomacy_unlocks + treaty_unlocks

        ideology_unlocks = [ideology.name for ideology in self.parser.ideologies.values() if tech in ideology.required_technologies]
        if ideology_unlocks:
            result['ideology'] = ideology_unlocks

        law_unlocks = [law.name for law in self.parser.laws.values() if tech in law.required_technologies]
        if law_unlocks:
            result['law'] = law_unlocks

        mobilization_unlocks = [mobilization_option.display_name for mobilization_option in self.parser.mobilization_options.values() if tech in mobilization_option.required_technologies]
        if mobilization_unlocks:
            result['mobilization'] = mobilization_unlocks

        movement_unlocks = [movement.display_name for movement in self.parser.movements.values() if tech in movement.required_technologies]
        if movement_unlocks:
            result['movement'] = movement_unlocks

        party_unlocks = [party.display_name for party in self.parser.parties.values() if tech in party.required_technologies]
        if party_unlocks:
            result['party'] = party_unlocks

        pm_unlocks = [production_method.name for production_method in self.parser.production_methods.values() if tech in production_method.required_technologies]
        if pm_unlocks:
            result['pm'] = pm_unlocks

        unit_unlocks = [unit.display_name for unit in self.parser.units.values() if tech in unit.required_technologies]
        if unit_unlocks:
            result['unit'] = unit_unlocks

        return result

    def _get_modifier_list(self, mod_list: list):
        result = {}
        if len(mod_list)>0:
            result = {
                mod.modifier_type.name: mod.value.format() if hasattr(mod.value, 'format') else mod.value for mod in mod_list
            }

        return result

    def generate_modifier_data_lua(self):
        """Desired format is:

         modifier_script_name = {
           loc = "Modifier localization",
           percent=true, --if marked as percent=yes in files
           boolean=true, --if marked as boolean=yes in files
           positive="green", negative="red", --if marked color=good in files
           positive="red", negative="green", --if marked color=bad in files
           icon = icons.<icon>, --if an icon is associated with the loc/modifier
         },"""
        result = {}
        for mod_type in sorted(self.parser.modifier_types.values(),key=attrgetter('name')):
            mod_data = { 'loc': self.parser.formatter.strip_formatting(mod_type.display_name),}
            if mod_type.script_only:
                mod_data['script_only'] = True
            if mod_type.percent:
                mod_data['percent'] = True
            if mod_type.boolean:
                mod_data['boolean'] = True
            if mod_type.good:
                mod_data['positive'] = 'green'
                mod_data['negative'] = 'red'
            elif not mod_type.good and not mod_type.neutral:
                mod_data['positive'] = 'red'
                mod_data['negative'] = 'green'
            match = re.match(r'\{\{icon\|([^|}]+)[|}]', mod_type.display_name)
            if match:
                mod_data['icon'] = match.group(1)

            result[mod_type.name] = mod_data

        return 'local p = ' + luadata.serialize(result, indent=' ')

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

It is autogenerated with https://github.com/grotaclas/PyHelpersForPDXWikis/blob/main/vic3/generate_lua_data.py (parameter character_data_lua) and automatically
updated. Please note suggestions for changes on the talk page or raise an issue on github, because manual changes will be overwritten.
]]--
local p = {};
''' + '\n\n'.join(lua_tables) + '\n\nreturn p'

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
        for named_mod in sorted(self.parser.named_modifiers.values(),key=attrgetter('name')):
            if re.search(r'cultural_acceptance_modifier|fervor_target_modifier|standard_of_living_modifier',named_mod.name):
                continue

            mod_data = {'loc': named_mod.display_name,
                        'mods': { mod.modifier_type.name: mod.value.format() if hasattr(mod.value, 'format') else mod.value for mod in named_mod.modifier}}
            if named_mod.description:
                mod_data['desc'] = named_mod.description.replace('\n', '<br>')

            result[named_mod.name] = mod_data
            
        return '''
local p = ''' + luadata.serialize(result, indent=' ')

    def _get_unit_upgrades(self, upgrade_list, name):
        result = {
            'from': [],
            'to': [],
        }
        result['to'] = [unit for unit in upgrade_list]
        result['from'] = [unit.name for unit in self.parser.units.values() if name in unit.upgrades]
        return result
    
    def generate_unit_data_lua(self):
        """The format is:
            ['irregular infantry'] = {
                icon = "Battalion irregular infantry.png",
                link = "Irregular Infantry",
                type = "Infantry",
                tech = foo
                stats = {
                    { 'green', '10', 'Offense', icons.offense },
                    { 'green', '10', 'Defense', icons.defense },
                    { 'red', '15', 'Morale loss', icons.morale },
                },
                upkeep = {
                },
                upgrade = {
                    from = { },
                    to = { "Line Infantry", "Skirmish Infantry", "Trench Infantry", "Squad Infantry", "Mechanized Infantry" }
                }
            },
        """
        result = {}
        for unit in self.parser.units.values():
            unit_data = {
                'icon': f'{unit.group.get_type_icon().capitalize()} {unit.display_name.lower()}.png',
                'link': unit.display_name,
                'type': unit.group.display_name,
                'tech': [tech.name for tech in unit.required_technologies],
                'stats': self._get_modifier_list(unit.battle_modifier),
                'formation_stats': self._get_modifier_list(unit.formation_modifier),
                'upkeep': self._get_modifier_list(unit.upkeep_modifier),
                'upgrade': self._get_unit_upgrades(unit.upgrades, unit.name),
            }
            result[unit.name] = unit_data
        return  '''
local p = ''' + luadata.serialize(result, indent=' ')
    
    def _get_law_reqs_blockers(self, req_blocker_dict: dict):
        result = {}
        req_law = None
        #print(isinstance(req_blocker_dict['law'],list))
        if isinstance(req_blocker_dict['law'],list) and len(req_blocker_dict['law']) > 0:
            req_law = req_blocker_dict['law']
            print(req_blocker_dict['law'])
        #for req in req_blocker_dict:
            #if req:
            #    print(req)
            #tech = [tech for tech in req.required_technologies]
        #req_law = [law.name for law in self.parser.laws.values() if law in req_blocker_dict['law']]
        if req_law:
            result['law'] = req_law

        return result
    
    def generate_law_data_lua(self):
        result = {}
        for law in self.parser.laws.values():
            law_data = {
                'loc': law.display_name,
                'desc': law.description,
                'group': law.group.display_name,
                'category': law.get_wiki_page_name(),
                'reqs': self._get_law_reqs_blockers({'tech': law.required_technologies, 'law': law.unlocking_laws, 'can': law.can_enact, 'visible': law.is_visible}),
                'blockers': self._get_law_reqs_blockers({'law': law.disallowing_laws, 'can': law.can_enact, 'visible': law.is_visible}),
            }
            result[law.name] = law_data
        return  '''
local p = ''' + luadata.serialize(result, indent=' ')
    
    def generate_defines_list_lua(self) -> str:
        """
        generates https://vic3.paradoxwikis.com/Module:Defines/List

        """
        result = self.parser.defines.to_dict()
        return f'''
local NDefines = {luadata.serialize(result, indent=' ')}
'''

    def generate_defines_comments_lua(self) -> str:
        """
        generates https://vic3.paradoxwikis.com/Module:Defines/Comments

        """
        result = self.parser.define_commments.to_dict()
        return f"""
local NDefines = {luadata.serialize(result, indent=' ')}
"""
if __name__ == '__main__':
    LuaDataGenerator().run(sys.argv)