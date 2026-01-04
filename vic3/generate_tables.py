import re
import os
from typing import Any

import sys
from collections.abc import Iterable, Sequence
from operator import attrgetter
# add the parent folder to the path so that imports work even if this file gets executed directly
sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from vic3.text_formatter import Vic3WikiTextFormatter
from vic3.vic3_file_generator import Vic3FileGenerator
from vic3.vic3lib import Country, Technology, ProductionMethod, StateTrait, Building, BuildingGroup, StateResource


class TableGenerator(Vic3FileGenerator):

    def generate_country_table(self):
        tier_num = {
            'city_state':1,
            'principality':2,
            'grand_principality':3,
            'kingdom':4,
            'empire':5,
            'hegemony':6
        }
        countries = [{
            'class="unsortable" style="width:5px;" |': f'id="{c.display_name}" style="background-color: {c.color.css_color_string}"|' + ("{{anchor|" + "|".join([name for name in self.parser.dynamic_country_names[c.tag]]) + "}}" if c.tag in self.parser.dynamic_country_names else ""),
            'style="width:20%;" | Name<span style="font-size:80%;margin-left:10px;">[[#Top|Return to top]]</span>': f"[[File:{c.display_name}.png|48px|border]] '''{c.display_name}'''" + (f'<br/><small>Other names: {", ".join(self.parser.dynamic_country_names[c.tag])}</small>' if c.tag in self.parser.dynamic_country_names else ""),
            'Tag': f'{c.tag}',
            'Type': self.parser.localize(c.type),
            'Tier': f'data-sort-value="{tier_num[c.tier]}" | {self.parser.localize("country_tier_" + c.tier)}'.replace("Grand Principality", "Grand Princ."), #shortened name for saving column width
            'Capital state': c.capital_state.display_name if c.capital_state is not None else '',
            'Region': c.capital_state.get_strategic_region().display_name if c.capital_state is not None else '',
            'style="width:25%;" | Cultures\n': ', '.join(self.parser.localize(culture) for culture in c.cultures) +'\n',
            '{{TextTooltip|Rel.|Religion}}': f'{{{{icon|{self.parser.localize(c.religion)}}}}}',
            '{{TextTooltip|E|Exists at&nbsp;start}}': '{{icon|yes}}' if c.exists() else '{{icon|no}}',
            '{{TextTooltip|F|Formable}}': '{{icon|yes}}' if c.is_formable() else '{{icon|no}}',
            '{{TextTooltip|R|Releasable|style=margin-left:-50px;}}': '{{icon|yes}}' if c.is_releasable() else '{{icon|no}}',
            '{{TextTooltip|S|Event formation or release|style=margin-left:-120px;}}': '{{icon|yes}}' if c.is_effect_releasable() or c.is_effect_formable() else '{{icon|no}}',
        } for c in sorted(self.parser.countries.values(), key=attrgetter("display_name"))]

        return self.get_SVersion_header() + '\n' + self.make_wiki_table(countries).replace("\n ||","\n|") #'fix' line generation

    def generate_count_countries(self):
        exists_form = 0
        exists_release = 0
        special_form = 0
        special_release = 0
        special_none = 0
        for country in self.parser.countries.values():
            if country.exists():
                if country.is_formable():
                    exists_form += 1
                if country.is_releasable():
                    exists_release += 1
            else:
                if country.is_effect_formable() and not country.is_formable():
                    special_form += 1
                if country.is_effect_releasable() and not country.is_releasable():
                    special_release += 1
                if not country.is_formable() and not country.is_releasable() and not country.is_effect_formable() and not country.is_effect_releasable():
                    special_none += 1
        return f"There are {len(self.parser.countries)} countries defined in the game: {len(self.parser.existing_tags)} of which are present at the 1836 start date. {len(self.parser.formable_tags)} countries are formable, of which {exists_form} exist at the start (+{special_form} more which can be formed only by effects); {len(self.parser.releasable_tags)} are releasable, of which {exists_release} exist at the start (+{special_release} more which can be released only by effects). Countries can also appear on the map by culture secession or be generated as part of a revolution ({special_none} can only appear in this way)."
    
    def _get_states(self, country, region = False):
        states = [{
            'state': state.display_name,
            'capital': ' [[File:state status capital.png|link=capital|20px]]' if state == country.capital_state else '',
            'split': ' [[File:state status split state.png|link=split state|20px]]' if len(state.owners) > 1 else '',
            'region': state.get_strategic_region().display_name
        } for state in self.parser.states.values() if country in state.owners]
        region_list = []
        state_list = []
        for state in states:
            if state['capital'] == '':
                state_list.append(state['state'] + state['split'])
            else:
                state_list.insert(0, state['state'] + state['capital'] + state['split'])
            if state['region'] not in region_list:
                region_list.append(state['region'])
        if region:
            return region_list
        else:
            return state_list
        
    def simple_country_table(self, country_list):
        countries = []
        for country in country_list:
            if country.exists():
                countries.append({
                    'Country': f"[[File:{country.display_name}.png|36px|border]] {country.display_name}",
                    'Primary cultures': self.create_wiki_list([self.parser.localize(culture) for culture in country.cultures], no_list_with_one_element=True),
                    'Starting states': self.create_wiki_list(self._get_states(country), no_list_with_one_element=True),
                    'Region': self.create_wiki_list(self._get_states(country, region = True), no_list_with_one_element=True),
                })
            else:
                countries.append({
                    'Country': f"[[File:{country.display_name}.png|36px|border]] {country.display_name}",
                    'Primary cultures': self.create_wiki_list([self.parser.localize(culture) for culture in country.cultures], no_list_with_one_element=True),
                    'Region': self.parser.state_to_strategic_region_map[country.capital_state.name].display_name
                })

        return self.make_wiki_table(countries, table_classes=['wikitable', 'plainlist', 'mw-collapsible'], table_style='margin-right:10px;', one_line_per_cell=True)
    
    def generate_decentralized_country_tables(self):
        section_title = "decentralized nations"
        tables = []
        countries = [country for country in sorted(self.parser.countries.values(), key=attrgetter("display_name")) if country.is_decentralized()]
        african_countries = [country for country in countries if country.exists() and 'Africa' in country.capital_state.get_geographic_regions()]
        american_countries = [country for country in countries if country.exists() and 'Americas' in country.capital_state.get_geographic_regions()]
        other_countries = [country for country in countries if country.exists() and country not in african_countries and country not in american_countries]
        revoter_countries = [country for country in countries if not country.exists()]
        tables.append(f'<div>\n=== Africa {section_title} ===')
        tables.append(self.simple_country_table(african_countries)+'</div>')
        tables.append(f'<div>\n=== Americas {section_title} ===')
        tables.append(self.simple_country_table(american_countries)+'</div>')
        tables.append(f'<div>\n=== Pacific and Asia {section_title} ===')
        tables.append(self.simple_country_table(other_countries)+'</div>')
        tables.append(f'<div>\n=== Revolter {section_title} ===')
        tables.append(self.simple_country_table(revoter_countries)+'</div>')
        return tables
    
    def write_country_table(self):
        self._write_text_file('country_table', self.generate_country_table())

    def get_unlocks(self, tech: Technology):
        unlocks = []
        pm_unlocks = {}
        for unlock in sorted(tech.get_unlocks(), key=lambda entity: entity.__class__.__name__ + entity.display_name):
            if isinstance(unlock, ProductionMethod):
                wiki_string = unlock.get_wiki_link_with_icon()
                if wiki_string not in pm_unlocks:
                    pm_unlocks[wiki_string] = []
                pm_unlocks[wiki_string].extend(building.display_name for building in unlock.buildings)
            elif isinstance(unlock, StateTrait):
                if tech in unlock.disabling_technologies:
                    unlocks.append('Disables the state trait ' + unlock.get_wiki_link_with_icon())
                if tech in unlock.required_techs_for_colonization:
                    unlocks.append('Allows colonization of provinces with the state trait ' + unlock.get_wiki_link_with_icon())
            else:
                unlocks.append(unlock.get_wiki_link_with_icon())
        for wiki_string, buildings in pm_unlocks.items():
            if len(buildings) == 1:
                unlocks.append(wiki_string + ' for ' + buildings[0])
            else:
                building_string = self.create_wiki_list(sorted(buildings), 2)
                if len(buildings) > 4:
                    unlocks.append(wiki_string + ' for {{MultiColumn|' + building_string + '\n|2}}\n')
                else:
                    unlocks.append(wiki_string + ' for' + building_string)

        return unlocks

    def generate_tech_production_table(self):
        return self.generate_tech_table('production')

    def generate_tech_military_table(self):
        return self.generate_tech_table('military')

    def generate_tech_society_table(self):
        return self.generate_tech_table('society')

    def generate_tech_table(self, category):
        techs = [
            {
                'Name': f'{{{{iconbox|{tech.display_name}|{tech.description}|image={tech.get_wiki_filename()}}}}}\n',
                'Era': tech.era,
                'Prerequisites': self.create_wiki_list([f'{pre_tech.get_wiki_file_tag()} [[#{pre_tech.display_name}|{pre_tech.display_name}]]' for pre_tech in tech.required_technologies]),
                'Modifiers': self.create_wiki_list([modifier.format_for_wiki() for modifier in tech.modifier]),
                'Unlocks': self.create_wiki_list(self.get_unlocks(tech))
            }
            for tech in self.parser.technologies.values() if tech.category == category
        ]
        column_specs = self.get_column_specs(techs)
        column_specs[0] = (' width="25%" | Name', '%(Name)s')
        column_specs[4] = (' width="25%" | Unlocks', '%(Unlocks)s')

        table = self.make_wiki_table(techs, column_specs=column_specs, table_classes=['mildtable', 'plainlist'],
                                    one_line_per_cell=True,
                                    sort_function=lambda num, tech: (tech['Era'], tech['Name']))
        return self.get_SVersion_header() + '\n' + table

    def generate_decree_table(self) -> str:
        decrees = [{
            'Name': f'id="{decree.name}" | {{{{iconbox|{decree.display_name}|{decree.description}|image={decree.get_wiki_filename()}}}}}',
            'Required technology': ' and '.join(
                [tech.get_wiki_link_with_icon() for tech in decree.required_technologies]),
            # 'Conditions': self.parser.formatter.format_conditions(decree.valid) if decree.valid else '',
            'Conditions': ('Country:' + self.parser.formatter.format_conditions(decree.country_trigger)) if decree.country_trigger else '' + (('\nState:' + self.parser.formatter.format_conditions(decree.state_trigger)) if decree.state_trigger else ''),
            'Modifiers': self.create_wiki_list([modifier.format_for_wiki() for modifier in decree.modifier]),

        } for decree in sorted(self.parser.decrees.values(), key=attrgetter('display_name'))]
        table = self.make_wiki_table(decrees, table_classes=['mildtable', 'plainlist'],
                                     one_line_per_cell=True,
                                     )

        return self.get_SVersion_header(scope='table') + '\n' + table

    def get_state_trait_notes(self, trait: StateTrait):
        notes = []
        if trait.disabling_technologies:
            for tech in trait.disabling_technologies:
                notes.append(f'Disabled by {tech.get_wiki_link_with_icon()}')
        if trait.required_techs_for_colonization:
            for tech in trait.required_techs_for_colonization:
                notes.append(f'Can only be colonized with {tech.get_wiki_link_with_icon()}')
        return self.create_wiki_list(notes)

    def generate_state_trait_table(self) -> str:
        traits = [{
            'width="75px" | Type': f'id="{trait.display_name}" data-sort-value="{trait.get_wiki_filename()}" |{trait.get_wiki_file_tag("75px")}',
            'Name': trait.display_name,
            'Modifiers': self.create_wiki_list([modifier.format_for_wiki() for modifier in trait.modifier]),
            'width="30%" | States': ', '.join([state.display_name for state in trait.states]),
            'Notes': self.get_state_trait_notes(trait),

        } for trait in sorted(self.parser.state_traits.values(), key=attrgetter('display_name'))]
        table = self.make_wiki_table(traits, table_classes=['mildtable', 'plainlist'],
                                     one_line_per_cell=True,
                                     )

        return self.get_SVersion_header('table') + '\n' + table


    def generate_state_table(self) -> str:
        arable_resource = {building.building_group.name: building.get_wiki_file_tag()
                           for building in sorted(self.parser.buildings.values(), key=attrgetter('display_name'))
                           if building.building_group.land_usage == 'rural'
                           and not building.building_group.is_subsistence}
        capped_resources = {building.building_group.name: building.get_wiki_file_tag()
                            for building in sorted(self.parser.buildings.values(), key=attrgetter('display_name'))
                            if building.building_group.capped_by_resources
                            and not building.building_group.discoverable_resource}
        dicoverable_resources = {building.building_group.name: building.get_wiki_file_tag()
                                 for building in sorted(self.parser.buildings.values(), key=attrgetter('display_name'))
                                 if building.building_group.capped_by_resources
                                 and building.building_group.discoverable_resource}
        states = []
        for state in self.parser.states.values():
            if state.is_water():
                continue
            pops = self.parser.state_population[state.name]
            table_entry = {
                'Name': f'id="{state.display_name}" | {state.display_name}',
                'Region': state.get_strategic_region().display_name,
                'State region tag': f'{state.name}',
                'Arable land': state.arable_land,
                'Pops': f'data-sort-value="{pops}"|{self.parser.formatter.format_big_number(pops)}',
                'Homelands': ', '.join([self.parser.localize(culture.removeprefix('cu:')) for culture in state.homelands]),
                'Owners': ', '.join(
                    [f'{{{{flag|{self.parser.countries[tag].display_name}}}}}' for tag in state.owners])}
            # for bg_name, building_icon in (arable_resource | capped_resources | dicoverable_resources).items():
            #     if bg_name in state.resources:
            #         amount = f'{state.resources[bg_name].get_max_amount()} {building_icon}'
            #     else:
            #         amount = ''
            #     table_entry[building_icon] = amount
            table_entry['Traits'] = self.create_wiki_list([trait.get_wiki_link_with_icon() for trait in state.traits])
            states.append(table_entry)
        table = self.make_wiki_table(states,
                                     table_classes=['wikitable', 'plainlist'],
                                     # one_line_per_cell=True,
                                     sort_function=lambda num, state: (state['Region'], state['Name'])
                                     )

        return self.get_SVersion_header('table') + '\n{{clear}}\n' + table

    def _format_resource(self, amount: int, undiscovered_amount: int):
        if undiscovered_amount > 0 and amount > 0:
            return f'{amount} ({undiscovered_amount})'
        elif undiscovered_amount > 0 and amount == 0:
            return f'({undiscovered_amount})'
        else:
            return f'{amount}'

    def _format_resource_name(self, resource: StateResource):
        name = re.sub('_.*$', '', resource.building.removeprefix("building_"))
        name = re.sub('_.*$', '', name.removesuffix("_mine"))
        name = re.sub('_.*$', '', name.removesuffix("_camp"))
        name = re.sub('_.*$', '', name.removesuffix("_wharf"))
        name = re.sub('_.*$', '', name.removesuffix("_station"))
        name = re.sub('_.*$', '', name.removesuffix("_rig"))
        name = re.sub('_.*$', '', name.removesuffix("_field"))
        return name

    def generate_state_data_lua(self):
        lua_tables = []
        for state in self.parser.states.values():
            if state.is_water():
                continue
            traits = ', '.join(f'"{trait.display_name}"' for trait in state.traits)
            homelands = ', '.join(f'"{self.parser.localize(culture.removeprefix("cu:"))}"' for culture in state.homelands)
            resource_amounts = {}
            for res in state.resources.values():
                if not res.is_arable:
                    name = self._format_resource_name(res)
                    if name not in resource_amounts:
                        resource_amounts[name] = {'amount': 0, 'undiscovered_amount': 0}
                    # this is needed for gold to add gold and gold fields together
                    resource_amounts[name]['amount'] += res.amount
                    resource_amounts[name]['undiscovered_amount'] += res.undiscovered_amount
            resources = ', '.join(f'{name} = "{self._format_resource(amounts["amount"], amounts["undiscovered_amount"])}"'
                                  for name, amounts in resource_amounts.items())
            arable_resources = ', '.join(f'"{self.parser.buildings[res.building].display_name}"' for res in state.resources.values() if res.is_arable)
            lua_tables.append(f'''p["{state.display_name}"] = {{
    arable_land = {state.arable_land},
    arable_resources = {{ {arable_resources} }},
    resources = {{ {resources} }},
    traits = {{ {traits} }},
    homelands = {{ {homelands} }},
    region = "{self.parser.state_to_strategic_region_map[state.name].display_name}"
}}''')

        return '''--[[
This module lists all states with their static data.
It's meant to be required by "Module:State"

It is autogenerated with https://github.com/grotaclas/PyHelpersForPDXWikis/blob/main/vic3/generate_tables.py (parameter state_data_lua) and automatically
updated. Please note suggestions for changes on the talk page or raise an issue on github, because manual changes will be overwritten.
]]--
local p = {};

''' + '\n\n'.join(lua_tables) + '\n\nreturn p'

    def generate_strategic_region_table(self):
        regions = [{
            'Strategic Region': f'id="{region.display_name}" |{region.display_name}',
            'Script name': region.name,
            'States': f'{{{{MultiColumn|{self.create_wiki_list(sorted(state.display_name for state in region.states))}\n|2}}}}',
            'State #': len(region.states),
            'Countries present': f'{{{{MultiColumn|{self.create_wiki_list([country.get_wiki_link_with_icon() for country in region.countries])}\n|2}}}}',
            'Country #': len(region.countries)
        } for region in sorted(self.parser.strategic_regions.values(), key=attrgetter('display_name'))
            if not region.is_water]
        table = self.make_wiki_table(regions, table_classes=['wikitable', 'plainlist'],
                                     one_line_per_cell=True,
                                         )

        return self.get_SVersion_header('table') + '\n' + table
    
    def generate_geographic_region_table(self):
        georegions = [{
            'Geographic Region': f'id="{georegion.display_name}" |{georegion.display_name}',
            'Short key': georegion.short_key,
            'Regions': f'{{{{MultiColumn|{self.create_wiki_list(sorted(region.display_name for region in georegion.regions))}\n|2}}}}' if len(georegion.regions) > 0 else '',
            'States': f'{{{{MultiColumn|{self.create_wiki_list(sorted(state.display_name for state in georegion.states))}\n|2}}}}' if len(georegion.states) > 0 else '',
            'Countries present': f'{{{{Collapse|{{{{MultiColumn|{self.create_wiki_list([country.get_wiki_link_with_icon() for country in georegion.countries])}\n|5}}}}\n}}}}',
        } for georegion in sorted(self.parser.geographic_regions.values(), key=attrgetter('display_name'))]
        table = self.make_wiki_table(georegions, table_classes=['wikitable', 'plainlist'],
                                     one_line_per_cell=True,
                                         )
        return self.get_SVersion_header('table') + '\n' + table

    def iconify(self, what: Any, iconify_param: str = None) -> str:
        if isinstance(what, list):
            return ', '.join([self.iconify(item, iconify_param) for item in what])
        if str(what).lower() == 'random':
            return '{{icon|Undecided}} ' + str(what)
        if str(what) == '':
            return ''
        if iconify_param is not None:
            return '{{iconify|' + str(what) + '|' + iconify_param + '}}'
        try:
            return what.get_wiki_link_with_icon()
        except AttributeError:
            return '{{icon|' + str(what) + '}} ' + str(what)

    def generate_character_table(self):
        characters = [{
            'Name': character.display_name,
            'Country': character.country.get_wiki_link_with_icon() if character.country else '',
            'Role': self.iconify(character.get_roles(), 'Role'),
            'Interest group': character.interest_group.get_wiki_link_with_icon() if character.interest_group is not None else '',
            'Ideology': self.iconify(character.ideology, 'Ideology leader'),
            'Traits': self.iconify(character.traits, 'Trait'),
            # 'Culture': character.culture,
            'Culture': f"''{character.culture.replace('_', ' ').title()}''" if character.culture in ['random', 'primary_culture'] else character.culture,
            'Religion': character.religion,
            'Unique Portrait': '[[File:No.png|20px|No portrait]]' if character.dna == '' else '[[File:Yes.png|20px|Unique portrait]]',
            'Female': '[[File:Yes.png|20px|Female]]' if character.female else '[[File:No.png|20px|Male]]',
            'Availability': character.availability,
            'DLC': character.dlc,
            # ignore noble, because it seems useless
            # icon for female

        } for character in self.parser.characters.values()]
        table = self.make_wiki_table(characters, table_classes=['mildtable', 'plainlist'],
                                     one_line_per_cell=True,
                                     )

        return self.get_SVersion_header() + '\n' + table

    def get_character_cargo_templates(self):
        result = [f'{{{{Character|Name={character.display_name}|Countries={character.country.tag if character.country else ""}|Roles={",".join(character.get_roles())}|Ideology={character.ideology}|Traits={",".join(character.traits)}}}}}' for character in self.parser.characters.values()]
        return '\n'.join(result)

    def generate_treaty_article_table(self):
        articles = []
        for article in self.parser.treaty_articles.values():
            table_entry = {
                'Name': f'id="{article.display_name}" | {article.display_name}',
                'Required technology': ' and '.join(
                [tech.get_wiki_link_with_icon() for tech in article.required_technologies]),
            }
            articles.append(table_entry)
        table = self.make_wiki_table(articles,
                                     table_classes=['wikitable', 'plainlist'],
                                     )

        return self.get_version_header() + '\n{{clear}}\n' + table

    def generate_movement_table(self):
        movements = []
        for movement in self.parser.movements.values():
            table_entry = {
                'Name': f'{movement.display_name}',
                'Required technology': ' and '.join(
                [tech.get_wiki_link_with_icon() for tech in movement.required_technologies]),
            }
            movements.append(table_entry)
        table = self.make_wiki_table(movements,
                            table_classes=['wikitable', 'plainlist'],
                            )
        return self.get_version_header() + '\n{{clear}}\n' + table
if __name__ == '__main__':
    TableGenerator().run(sys.argv)
