import os
import re
import sys
from collections.abc import Mapping
from functools import cached_property
from operator import attrgetter
from typing import List, Dict


# add the parent folder to the path so that imports work even if this file gets executed directly
sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

from cs2.game import cs2game
from cs2.cs2lib import CS2Asset, SignatureBuilding, Building, Road
from cs2.localization import CS2Localization
from cs2.cs2_file_generator import CS2FileGenerator
from cs2.text_formatter import CS2WikiTextFormatter


class TableGenerator(CS2FileGenerator):
    @cached_property
    def formatter(self) -> CS2WikiTextFormatter:
        return CS2WikiTextFormatter()

    @cached_property
    def localizer(self) -> CS2Localization:
        return self.parser.localizer

    #####################################################
    # Helper functions to generate new table generators #
    #####################################################

    @staticmethod
    def camel_to_snake(name: str) -> str:
        """Convert name from CamelCase to snake_case"""
        name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()

    def get_possible_table_columns(self, assets: List[CS2Asset]):
        columns = {}
        ignored_names = {'cs2_class', 'file_name', 'path_id', 'parent_asset', 'name', 'transform_value_functions', 'extra_data_functions'}
        common_locs = {'display_name': 'Name',
                       'lotWidth': 'Width',
                       'lotDepth': 'Depth',
                       'groundPollution': 'Ground pollution',
                       'airPollution': 'Air pollution',
                       'noisePollution': 'Noise pollution'
                       }
        for asset in assets:
            for name, value in vars(asset).items():
                if name in ignored_names:
                    continue
                if isinstance(value, CS2Asset):
                    if name not in columns:
                        columns[name] = {}
                    for sub_name in vars(value):
                        if sub_name in ignored_names:
                            continue
                        if sub_name not in columns[name]:
                            if sub_name in common_locs:
                                loc = common_locs[sub_name]
                            else:
                                loc = self.localizer.localize('Properties',
                                                              self.camel_to_snake(sub_name).upper(),
                                                              default=sub_name)
                            columns[name][sub_name] = loc
                else:
                    if name not in columns:
                        if name in common_locs:
                            loc = common_locs[name]
                        else:
                            loc = self.localizer.localize('Properties', self.camel_to_snake(name).upper(),
                                                          default=name)
                        columns[name] = loc
        return columns

    def print_possible_table_columns(self, assets: List[CS2Asset], var_name: str):
        sub_attributes = {}
        for attribute, loc_or_dict in self.get_possible_table_columns(assets).items():
            if isinstance(loc_or_dict, Mapping):
                # save for later to print the main attributes first
                sub_attributes[attribute] = loc_or_dict
            else:
                print(f"'{loc_or_dict}': {var_name}.{attribute},")
        for attribute, dic in sub_attributes.items():
            for sub_attribute, loc in dic.items():
                print(f"'{loc}': {var_name}.{attribute}.{sub_attribute},")

    ######################################
    # Table generators and their helpers #
    ######################################

    def get_all_signature_buildings_tables_by_category(self) -> Dict[str, str]:
        buildings_by_category = {}
        for building in self.parser.signature_buildings.values():
            category = building.UIObject.group.name
            if category not in buildings_by_category:
                buildings_by_category[category] = []
            buildings_by_category[category].append(building)

        result = {}
        for category, buildings in buildings_by_category.items():
            result[category] = self.generate_signature_buildings_table(sorted(buildings, key=attrgetter('display_name')))

        return result

    def generate_all_signature_buildings_tables(self):
        result = ''
        for category, table in self.get_all_signature_buildings_tables_by_category().items():
            loc = cs2game.localizer.localize('SubServices', 'NAME', category).replace(' Signature ', ' ')
            loc = loc[0].upper() + loc[1:].lower()
            result += f'== {loc} ==\n'
            result += table
            result += '\n'
        return result

    def generate_signature_buildings_table(self, buildings: List[Building]):
        data = [{
            'width="300px" | Name': f"style=\"text-align:center;\" |\n===={building.display_name}====\n\n{building.SignatureBuilding.get_wiki_file_tag()}\n\n''{building.description}''",
            'Size (cells)': building.size,
            'Theme': building.ThemeObject.theme.get_wiki_icon() if hasattr(building, 'ThemeObject') else '',
            'DLC': building.dlc.display_name,
            'Requirements': building.Unlockable.format(),
            'XP': building.SignatureBuilding.xPReward,
            'Attractiveness': f'{{{{icon|attractiveness}}}} {building.Attraction.attractiveness}' if hasattr(building, 'Attraction') and building.Attraction.attractiveness > 0 else '',
            'Effects': self.formatter.create_wiki_list(building.get_effect_descriptions(), no_list_with_one_element=True),
            'Ground pollution': f'{{{{icon|ground pollution}}}} {building.Pollution.groundPollution}' if hasattr(building, 'Pollution') and building.Pollution.groundPollution > 0 else '',
            'Air pollution': f'{{{{icon|air pollution}}}} {building.Pollution.airPollution}' if hasattr(building, 'Pollution') and building.Pollution.airPollution > 0 else '',
            'Noise pollution': f'{{{{icon|noise pollution}}}} {building.Pollution.noisePollution}' if hasattr(building, 'Pollution') and building.Pollution.noisePollution > 0 else '',
            # 'Zone Type': building.SignatureBuilding.zoneType.get_wiki_icon(),
            # 'scaleWithRenters': building.Pollution.scaleWithRenters,
        } for building in buildings]

        return (self.get_SVersion_header(scope='table') + '\n'
                + self.make_wiki_table(data, table_classes=['mildtable'],
                                       one_line_per_cell=True, remove_empty_columns=True))

    def generate_roads_table(self):
        icon_size = '48px'
        formatter = CS2WikiTextFormatter()
        roads = [road for road in self.parser.roads.values() if isinstance(road, Road)]
        # use the same sorting as the game
        roads.sort(key=lambda road: (road.UIObject.group.UIObject.priority, road.UIObject.priority))
        data = [{
            'Name': f'{{{{iconbox|{road.display_name}|{road.description}|image=Road {road.display_name}.png}}}}',
            'Category': road.UIObject.group,
            'DLC': road.dlc.display_name,
            'XP<ref>This amount of XP is awarded for each 112m / 14 cells</ref>': road.PlaceableNet.xPReward,
            'Speed limit': road.format_speedLimit(),
            'Elevation': f'{formatter.add_minus(road.PlaceableNet.elevationRange["min"])}–{formatter.add_minus(road.PlaceableNet.elevationRange["max"])}',
            'Car lanes': road.car_lanes,
            'Traffic lights': f'[[File:Road Traffic Lights.png|Can have traffic lights|link=|{icon_size}]]' if  road.trafficLights else '',
            'Highway rules': f'[[File:Highways.png|Highway rules|link=|{icon_size}]]' if road.highwayRules else '',
            'Services': road.get_services_icons(icon_size),
            'Base cost per km': formatter.cost(road.costs['base']['construction']) if not hasattr(road, 'Bridge') else '',
            'Base upkeep per km': formatter.cost(road.costs['base']['upkeep']) if not hasattr(road, 'Bridge') else '',
            'Elevated cost per km': f"{formatter.cost(road.costs['elevated']['construction'])} + {formatter.cost(road.costs['elevated']['elevation_cost'])} per elevation level" ,
            'Elevated upkeep per km': f"{formatter.cost(road.costs['elevated']['upkeep'])}",
            'Tunnel cost per km': f"{formatter.cost(road.costs['tunnel']['construction'])}" if road.PlaceableNet.elevationRange["min"] < 0 else '',
            'Tunnel upkeep per km': f"{formatter.cost(road.costs['tunnel']['upkeep'])}" if road.PlaceableNet.elevationRange["min"] < 0 else '',

            # always true in 1.0.9
            # 'allowParallelMode': road.PlaceableNet.allowParallelMode,
            # always None in 1.0.9
            #'undergroundPrefab': road.PlaceableNet.undergroundPrefab,
            # always 40k in version 1.0.9
            # 'electricity capacity': road.ElectricityConnection.capacity,
            # TODO: too long; dont seem useful
            #'UndergroundNetSections': road.UndergroundNetSections.sections,
            'Requirements': road.Unlockable.format() if hasattr(road, 'Unlockable') else '',
            'Noise pollution factor': f'{{{{icon|noise pollution}}}} {road.NetPollution.noisePollutionFactor:g}×',
            'Air pollution factor': f'{{{{icon|air pollution}}}} {road.NetPollution.airPollutionFactor:g}×',

            # bridge stuff. I dont know if this is useful for players
            # 'segmentLength': road.Bridge.segmentLength if hasattr(road, 'Bridge') else '',
            # 'hanging': road.Bridge.hanging if hasattr(road, 'Bridge') else '',
            # 'waterFlow': road.Bridge.waterFlow if hasattr(road, 'Bridge') else '',
            # 'fixedSegments': road.Bridge.fixedSegments if hasattr(road, 'Bridge') else '',
            # 'OverheadNetSections': road.OverheadNetSections.sections if hasattr(road, 'OverheadNetSections') else '',
        } for road in roads]
        return (self.get_SVersion_header(scope='table') + '\n'
                + self.make_wiki_table(data, table_classes=['mildtable'],
                                       one_line_per_cell=True, remove_empty_columns=True))

if __name__ == '__main__':
    generator = TableGenerator()
    generator.run(sys.argv)
