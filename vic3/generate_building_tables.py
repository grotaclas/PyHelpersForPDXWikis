from operator import attrgetter
import re
import os
import sys
# add the parent folder to the path so that imports work even if this file gets executed directly
sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from vic3.vic3_file_generator import Vic3FileGenerator
from vic3.vic3lib import ProductionMethod, NamedModifier, Building, Modifier, BuildingGroup


class BuildingTableGenerator(Vic3FileGenerator):
    def generate_all_buildings(self):
        sections = {}
        for category in ['development', 'rural', 'urban']:
            sections[f'{category}_buildings_list'] = self.generate_building_table(category=category)
        sections['monument_buildings_list'] = self.generate_building_table(group='bg_monuments')

        return sections

    def get_building_notes(self, building: Building):
        notes = []
        # if building.required_technologies:
        #     notes.append('Unlocked via ' + ' and '.join([tech.display_name for tech in building.required_technologies]))
        if building.unique:
            notes.append('Is unique')
        if building.enable_air_connection:
            notes.append('Enables an air connection')
        if not building.expandable:
            notes.append('Can\'t be expanded')
        if not building.downsizeable:
            notes.append('Can\'t be downsized')
        if building.location is not None:
            notes.append('Can only be constructed in the state {}'.format(building.location.display_name))

        if building.building_group.land_usage == 'rural':
            notes.append('Uses arable land')

        notes_for_building_groups = {
            'economy_of_scale': 'Has economy of scale',
            'is_subsistence': 'Is a subsistence building',
            'auto_place_buildings': 'Gets built automatically',
            'capped_by_resources': 'Building level is limited by state resources',
            'discoverable_resource': 'Resources can be discovered',
            'depletable_resource': 'Resources can deplete',
            'can_use_slaves': 'Can use slaves',
            'fired_pops_become_radical': 'Fired pops don\'t become radical',
            'pays_taxes': 'Pays no taxes',
            'is_government_funded': 'Is government-funded',
            'created_by_trade_routes': 'Gets created by trade routes',
            'always_self_owning': 'Always workforce-owned',
        }
        for attribute, message in notes_for_building_groups.items():
            if hasattr(building.building_group, attribute) and getattr(building.building_group, attribute) != \
                    building.building_group.default_values[attribute]:
                notes.append(message)
        return self.parser.formatter.create_wiki_list(notes)

    def _get_topmost_bg(self, building: Building) -> BuildingGroup:
        bg = building.building_group
        while bg.parent_group is not None:
            bg = bg.parent_group
        return bg

    def generate_building_table(self, category: str = None, group: str = None, excluded_groups: list[str] = None):
        buildings_to_display = self.parser.buildings.values()
        if category is not None:
            buildings_to_display = [building for building in buildings_to_display if
                                    building.building_group.category == category]
        if group is not None:
            buildings_to_display = [building for building in buildings_to_display if
                                    building.building_group.name == group]
        if excluded_groups is not None:
            buildings_to_display = [building for building in buildings_to_display if
                                    building.building_group.name not in excluded_groups]
        buildings = [{
            'Name': f'{{{{iconbox|{building.display_name}||image={building.get_wiki_filename()}}}}}\n',
            'Category': self.parser.localize(building.building_group.category.upper() + '_BUILDINGS'),
            'Group': self._get_topmost_bg(building).display_name,
            'Required technology': ' and '.join(
                [tech.get_wiki_link_with_icon() for tech in building.required_technologies]),
            'Cost': building.required_construction,
            'Urbanization': building.building_group.urbanization,
            'Infrastructure': building.building_group.infrastructure_usage_per_level,
            # cash reserves are all 25k ATM, so it is not really useful in the table
            # 'Max. cash reserves': building.building_group.cash_reserves_max,
            'Production methods': self.parser.formatter.create_wiki_list(
                [pm.get_wiki_link_with_icon() for pm in building.production_methods]),
            'Notes': self.get_building_notes(building)
        } for building in buildings_to_display]

        column_specs = self.get_column_specs(buildings)

        new_header = '! rowspan="2" width=250px | Name '
        # we don't need a catgeory/group column if there is only one
        if category is None:
            new_header += '!! rowspan="2" width=100px | Category '
        else:
            column_specs = [column for column in column_specs if column[0] != 'Category']
        if group is None:
            new_header += '!! rowspan="2" width=100px | Group '
        else:
            column_specs = [column for column in column_specs if column[0] != 'Group']
        new_header += '''!! rowspan="2" width=150px | Required technology !! colspan="3" style="text-align: center;" | Per Level !! rowspan="2" | Production methods !! rowspan="2" style="max-width:400px;" | Notes
|-
! {{icon|construction}} Cost !! {{hover box|Urbanization|Urb.}} !! {{icon|infrastructure}} Cost'''

        table = self.make_wiki_table(buildings, column_specs=column_specs, table_classes=['mildtable', 'plainlist'],
                                     one_line_per_cell=True,
                                     sort_function=lambda num, building: (
                                     building['Category'], building['Group'], building['Name']))

        table = re.sub(r'^! Name.*', new_header, table, flags=re.MULTILINE)
        return self.get_SVersion_header() + '\n' + table

    def _group_pm_building_modifiers(self, pm: ProductionMethod, convert_to_wiki_list=True,
                                     include_timed_modifiers=True):
        result = {'input': [], 'output': [], 'workforce': [], 'other': []}
        profession_per_level = re.compile('(' + '|'.join(
            [pop_type.display_name_without_icon for pop_type in self.parser.pop_types.values()]) + ') per level',
                                          re.IGNORECASE)
        for scaling_type in ['workforce_scaled', 'level_scaled', 'throughput_scaled', 'unscaled']:
            if scaling_type in pm.building_modifiers:
                for modifier in pm.building_modifiers[scaling_type]:
                    wiki_text = modifier.format_for_wiki()
                    if wiki_text.endswith(' input per level') or wiki_text.endswith(' input'):
                        wiki_text = re.sub(r'(?<=}}) [-a-zA-Z ]* input( per level)?', '', wiki_text)
                        wiki_text += self.get_scaling_type_reference(scaling_type, 'workforce_scaled')
                        result['input'].append(wiki_text)
                    elif wiki_text.endswith(' output per level') or wiki_text.endswith(' output'):
                        wiki_text = re.sub(r'(?<=}}) [-a-zA-Z ]* output( per level)?', '', wiki_text)
                        wiki_text += self.get_scaling_type_reference(scaling_type, 'workforce_scaled')
                        result['output'].append(wiki_text)
                    elif profession_per_level.search(wiki_text):
                        wiki_text = profession_per_level.sub('', wiki_text)
                        wiki_text += self.get_scaling_type_reference(scaling_type, 'level_scaled')
                        result['workforce'].append(wiki_text)
                    else:
                        # shorten icon + text to just the icon
                        wiki_text = re.sub(r'\{\{icon\|([^}]+)}} \1', r'{{icon|\1}}', wiki_text, flags=re.IGNORECASE)
                        wiki_text += self.get_scaling_type_reference(scaling_type, 'unscaled')
                        result['other'].append(wiki_text)
        if include_timed_modifiers:
            for timed_modifier in pm.timed_modifiers:
                result['other'].append(self._get_text_for_timed_modifier_for_pms(timed_modifier))
        if convert_to_wiki_list:
            return {group: self.parser.formatter.create_wiki_list(mod_texts) for group, mod_texts in result.items()}
        else:
            return result

    def _get_text_for_timed_modifier_for_pms(self, timed_modifier: NamedModifier):
        return 'Changing to this production method applies the ' + timed_modifier.format_for_wiki(
            self.parser.defines['NEconomy']['BUILDING_TIMED_MODIFIER_WEEKS'])

    def get_scaling_type_reference(self, scaling_type, default_scaling_type=None):
        if scaling_type == default_scaling_type:
            return ''
        else:
            return '<ref name="{}" />'.format(scaling_type)

    def _get_modifier_list(self, modifier_data: dict[str, list[Modifier]], default_scaling_type='unscaled', convert_to_wiki_list=True):
        result = []
        for scaling_type, modifiers in modifier_data.items():
            # result.append('{}:{}'.format(scaling_type, self.create_wiki_list([modifier.format_for_wiki() for modifier in modifiers], 2)))
            result.extend([modifier.format_for_wiki() + self.get_scaling_type_reference(scaling_type, default_scaling_type=default_scaling_type) for modifier in modifiers])
        if convert_to_wiki_list:
            return self.parser.formatter.create_wiki_list(result)
        else:
            return result

    def _split_up_modifiers(self, pm: ProductionMethod, include_timed_modifiers=True):
        modifiers = self._group_pm_building_modifiers(pm, convert_to_wiki_list=False,
                                                      include_timed_modifiers=include_timed_modifiers)['other']
        for mod_list in (pm.country_modifiers, pm.state_modifiers):
            for modifier in self._get_modifier_list(mod_list, default_scaling_type='unscaled',
                                                    convert_to_wiki_list=False):
                modifiers.append(modifier)
        result = {}
        for modifier in modifiers:
            # shorten icon + text to just the icon
            modifier = re.sub(r'\{\{icon\|([^}]+)}} \1', r'{{icon|\1}}', modifier, flags=re.IGNORECASE)
            # move mortality to the end
            modifier = re.sub(r'(.+) (\[\[[^|]+\|Mortality]]) of (.+)', r'\3 \1 \2', modifier, flags=re.IGNORECASE)
            icon_re = r'\{\{icon\|[^}]+}}'
            match = re.match(
                r'(?P<value>(' + icon_re + r' )?(\{\{(green|red)\||\'\'\')[+−0-9.%]+(}}|\'\'\')( ' + icon_re + r')?) (?P<name>.*)',
                modifier)
            if match:
                name = match.group('name')
                if name not in result:
                    result[name] = []
                    # raise Exception(f'Duplicate modifier "{name}"')
                result[name].append(match.group('value'))
            else:
                if 'other' not in result:
                    result['other'] = []
                result['other'].append(modifier)
        for key in result:
            if len(result[key]) == 1:
                result[key] = result[key][0]
            else:
                result[key] = self.parser.formatter.create_wiki_list(result[key])
        return result

    def generate_building_pms(self, buildings_to_display: list[Building], split_up_modifiers=False,
                              one_table_per_pm_group=False, excluded_pms: list[str] = None):
        # def generate_building_pms(self, building_category: str = None, building_group: str = None, ignored_buildings: list[str] = None):
        # buildings_to_display = self.parser.buildings.values()
        # if ignored_buildings is not None:
        #     buildings_to_display = [building for building in buildings_to_display if building.name not in ignored_buildings]
        # if building_category is not None:
        #     buildings_to_display = [building for building in buildings_to_display if building.building_group.category == building_category]
        # if building_group is not None:
        #     buildings_to_display = [building for building in buildings_to_display if building_group in building.building_groups_names_with_parents]
        if excluded_pms is None:
            excluded_pms = []
        pms_to_display = {pm.name: pm for building in buildings_to_display for pm in building.production_methods if
                          pm.name not in excluded_pms}
        pmgs_to_display = {}
        for pm in pms_to_display.values():
            for pmg in pm.groups:
                display_name = self.parser.formatter.format_localization_text(pmg.display_name, [])
                if display_name not in pmgs_to_display:
                    pmgs_to_display[display_name] = []
                if pmg not in pmgs_to_display[display_name]:
                    pmgs_to_display[display_name].append(pmg)
        ordered_pms_to_display = []
        result = ''
        for building in buildings_to_display:
            for pmg_name in building.production_method_groups:
                # handle all production method groups with the same name together
                pmg_display_name = self.parser.formatter.format_localization_text(
                    self.parser.production_method_groups[pmg_name].display_name, [])
                for pmg in pmgs_to_display[pmg_display_name]:
                    for pm_name in pmg.production_methods:
                        if pm_name in pms_to_display:
                            pm = pms_to_display[pm_name]
                            pms_with_same_name = [same_name_pm for same_name_pm in pms_to_display.values() if
                                                  same_name_pm.display_name == pm.display_name]
                            for same_name_pm in pms_with_same_name:
                                ordered_pms_to_display.append(same_name_pm)
                                del pms_to_display[same_name_pm.name]
                if one_table_per_pm_group and len(ordered_pms_to_display) > 0:
                    result += f'==={pmg_display_name}===\n{self.generate_building_pms_for_specific_pms(buildings_to_display, ordered_pms_to_display, split_up_modifiers)}'
                    ordered_pms_to_display = []

            if not one_table_per_pm_group:
                result = self.generate_building_pms_for_specific_pms(buildings_to_display, ordered_pms_to_display,
                                                                     split_up_modifiers)

        return self.get_SVersion_header(scope='table') + '\n' + result

    def generate_building_pms_for_specific_pms(self, buildings_to_display: list[Building],
                                               ordered_pms_to_display: list[ProductionMethod],
                                               split_up_modifiers=False):
        timed_modifiers = set()
        for pm in ordered_pms_to_display:
            if len(pm.timed_modifiers) > 0:
                timed_mod_strs = []
                for timed_modifier in pm.timed_modifiers:
                    timed_mod_strs.append(self._get_text_for_timed_modifier_for_pms(timed_modifier))
                timed_modifiers.add('\n'.join(timed_mod_strs))
        if len(timed_modifiers) == 1:
            include_timed_modifiers = False
            timed_modifiers_text = timed_modifiers.pop().replace('this production method',
                                                                 'one of these production methods')
        else:
            include_timed_modifiers = True
        if split_up_modifiers:
            split_up_modifiers_keys = []
            for pm in ordered_pms_to_display:
                for key in self._split_up_modifiers(pm, include_timed_modifiers=include_timed_modifiers).keys():
                    if key not in split_up_modifiers_keys:
                        split_up_modifiers_keys.append(key)
        pms = []
        for pm in ordered_pms_to_display:
            pm_dict = {
                'id': pm.name,
                'Name': f'{{{{iconbox|{pm.display_name}||image={pm.get_wiki_filename()}}}}}',
                'Requirements': self._get_pm_requirements_list(pm),
                'Workforce<ref name="level_scaled" />':
                    self._group_pm_building_modifiers(pm, include_timed_modifiers=include_timed_modifiers)['workforce'],
                'Input<ref name="workforce_scaled" />':
                    self._group_pm_building_modifiers(pm, include_timed_modifiers=include_timed_modifiers)['input'],
                'Output<ref name="workforce_scaled" />':
                    self._group_pm_building_modifiers(pm, include_timed_modifiers=include_timed_modifiers)['output'],
            }
            if split_up_modifiers:
                modifiers = self._split_up_modifiers(pm, include_timed_modifiers=include_timed_modifiers)
                for key in split_up_modifiers_keys:
                    pm_dict[key] = modifiers[key] if key in modifiers else ''
            else:
                pm_dict['Building modifiers'] = \
                self._group_pm_building_modifiers(pm, include_timed_modifiers=include_timed_modifiers)['other']
                pm_dict['Country modifiers<ref name="workforce_scaled" />'] = self._get_modifier_list(
                    pm.country_modifiers, default_scaling_type='workforce_scaled')
                pm_dict['State modifiers<ref name="workforce_scaled" />'] = self._get_modifier_list(pm.state_modifiers,
                                                                                                    default_scaling_type='workforce_scaled')
            if len(buildings_to_display) > 1:
                pm_dict['Buildings'] = self.parser.formatter.create_wiki_list(
                    [b.get_wiki_link_with_icon() for b in sorted(pm.buildings, key=attrgetter('display_name')) if
                     b in buildings_to_display])
            pms.append(pm_dict)
            # sorted(pms_to_display,
            #                key=lambda pm: (pm.groups[0].name, pm.display_name)
            #                # key=lambda pm:ProductionMethod(pm.buildings[0].building_group.category,
            #                #                                                                         self._get_topmost_bg(pm.buildings[0]).display_name,
            #                #                                                                         pm.buildings[0].display_name,
            #                #                                                                         pm.display_name)
            #                )]

        result = self.make_wiki_table(pms, table_classes=['wikitable', 'plainlist'],
                                      one_line_per_cell=True,
                                      merge_identical_cells_in_column=True,
                                      remove_empty_columns=True,
                                      row_id_key='id',
                                      # sort_function=lambda num, building: (building['Category'], building['Group'], building['Name'])
                                      )
        if not include_timed_modifiers:
            result = timed_modifiers_text + '\n' + result
        return result

    # '''<references>
    # <ref name="workforce_scaled">Scaled by employment percentage and building level</ref>
    # <ref name="level_scaled">Scaled by building level</ref>
    # <ref name="throughput_scaled">Scaled by throughput</ref>
    # <ref name="unscaled">Unscaled</ref>
    # </references>'''

    def _get_pm_requirements_list(self, pm):
        requirements = [tech.get_wiki_link_with_icon() for tech in pm.required_technologies]
        if len(pm.unlocking_laws) == 1:
            requirements.append(pm.unlocking_laws[0].get_wiki_link_with_icon())
        if len(pm.unlocking_laws) > 1:
            requirements.append('One of the following laws:\n' + self.parser.formatter.create_wiki_list(
                [law.get_wiki_link_with_icon() for law in pm.unlocking_laws], 2))
        if len(pm.disallowing_laws) == 1:
            requirements.append("''Does not have the law ''" + pm.disallowing_laws[0].get_wiki_link_with_icon())
        if len(pm.disallowing_laws) > 1:
            requirements.append("Has ''none'' of the following laws:\n" + self.parser.formatter.create_wiki_list(
                [law.get_wiki_link_with_icon() for law in pm.disallowing_laws], 2))
        if len(pm.unlocking_production_methods) > 1:
            requirements.append('The building also has one of the following production methods:\n' +
                                self.parser.formatter.create_wiki_list([unlocking_pm.get_wiki_link_with_icon()
                                                       for unlocking_pm in pm.unlocking_production_methods]))
        if len(pm.unlocking_production_methods) == 1:
            requirements.append('The building also has the production methods ' + pm.unlocking_production_methods[
                0].get_wiki_link_with_icon())
        for religion in pm.unlocking_religions:
            requirements.append('State religion is ' + religion)
        return self.parser.formatter.create_wiki_list(requirements)

    def generate_all_production_methods(self):
        parser = self.parser
        sections = {}
        sections['production_methods_manufacturing'] = self.generate_building_pms_helper('bg_manufacturing', one_table_per_building=True)
        sections['production_methods_farms'] = self.generate_building_pms_helper(buildings=[b for b in parser.buildings.values() if
                   'bg_agriculture' in b.building_groups_names_with_parents and 'bg_subsistence_agriculture' not in b.building_groups_names_with_parents])
        sections['production_methods_ranching'] = self.generate_building_pms_helper(buildings=[b for b in parser.buildings.values() if
                   'bg_ranching' in b.building_groups_names_with_parents and 'bg_subsistence_ranching' not in b.building_groups_names_with_parents])
        sections['production_methods_subsistence'] = self.generate_building_pms_helper(buildings=[b for b in parser.buildings.values() if
                   'bg_subsistence_agriculture' in b.building_groups_names_with_parents or 'bg_subsistence_ranching' in b.building_groups_names_with_parents])
        sections['production_methods_plantations'] = self.generate_building_pms_helper(buildings=[b for b in parser.buildings.values() if 'bg_plantations' in b.building_groups_names_with_parents or b.name == 'building_rubber_plantation'])
        sections['production_methods_mining'] = self.generate_building_pms_helper(buildings=[b for b in parser.buildings.values() if
                   'bg_mining' in b.building_groups_names_with_parents and 'building_gold_fields' not in b.name])
        sections['production_methods_gold_fields'] = self.generate_building_pms_helper('bg_gold_fields', one_table_per_building=True)
        sections['production_methods_oil_extraction'] = self.generate_building_pms_helper('bg_oil_extraction', one_table_per_building=True)
        sections['production_methods_logging'] = self.generate_building_pms_helper('bg_logging', one_table_per_building=True)
        sections['production_methods_whaling'] = self.generate_building_pms_helper('bg_whaling', one_table_per_building=True)
        sections['production_methods_fishing'] = self.generate_building_pms_helper('bg_fishing', one_table_per_building=True)

        sections['production_methods_service'] = self.generate_building_pms_helper('bg_service', one_table_per_building=True)
        sections['production_methods_arts'] = self.generate_building_pms_helper('bg_arts', one_table_per_building=True)
        sections['production_methods_power'] = self.generate_building_pms_helper('bg_power', one_table_per_building=True)
        sections['production_methods_government'] = self.generate_building_pms_helper(buildings=[b for b in parser.buildings.values() if
                   'bg_government' in b.building_groups_names_with_parents and 'bg_monuments' not in b.building_groups_names_with_parents], one_table_per_building=True)
        sections['production_methods_trade'] = self.generate_building_pms_helper('bg_trade', one_table_per_building=True)
        sections['production_methods_infrastructure'] = self.generate_building_pms_helper('bg_infrastructure', one_table_per_building=True)
        sections['production_methods_barracks'] = self.generate_building_pms_helper(buildings=['building_barracks'])
        sections['production_methods_conscription_center'] = self.generate_building_pms_helper(buildings=['building_conscription_center'])
        sections['production_methods_naval_base'] = self.generate_building_pms_helper(buildings=['building_naval_base'])
        sections['production_methods_monuments_basic'] = self.generate_building_pms_for_specific_pms(
            [b for b in parser.buildings.values() if 'bg_monuments' in b.building_groups_names_with_parents],
            [parser.production_methods['pm_monument_prestige_only'], parser.production_methods['pm_monument_no_effects']]) + '\n'
        sections['production_methods_monuments_normal'] = self.generate_building_pms([b for b in sorted(parser.buildings.values(), key=attrgetter('display_name')) if 'bg_monuments' in b.building_groups_names_with_parents], excluded_pms=['pm_monument_prestige_only', 'pm_monument_no_effects'])
        return sections

    def generate_building_pms_helper(self, building_group: str = None, buildings: list = None, one_table_per_building=False):
        if building_group:
            buildings = [b for b in self.parser.buildings.values() if
                         building_group in b.building_groups_names_with_parents]
        if isinstance(buildings[0], str):
            buildings = [self.parser.buildings[b] for b in buildings]
        buildings = sorted(buildings, key=attrgetter('display_name'))
        if one_table_per_building:
            result = ''
            for building in buildings:
                if len(buildings) > 1:
                    result += f'=== {building.display_name} ===\n'
                result += self.generate_building_pms([building], split_up_modifiers=True) + '\n'
        else:
            result = self.generate_building_pms(buildings, split_up_modifiers=True, one_table_per_pm_group=True) + '\n'
        return result


if __name__ == '__main__':
    BuildingTableGenerator().run(sys.argv)
