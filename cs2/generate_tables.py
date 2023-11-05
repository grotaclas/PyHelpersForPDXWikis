import os
import re
import sys
from collections.abc import Mapping
from functools import cached_property
from operator import attrgetter
from pathlib import Path
from typing import List, Dict


# add the parent folder to the path so that imports work even if this file gets executed directly
sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

from cs2.game import cs2game
from cs2.cs2lib import CS2Asset, SignatureBuilding, Building, Road, convert_cs_member_name_to_python_attribute, \
    BaseBuilding
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

    def _get_loc_and_variable_types_from_code(self, code_folder: Path = None):
        """code_folder contains the c# code. It can be extracted by assetrippers"""
        if not code_folder:
            return {}
        property_binder_file = code_folder / 'Game/Game/UI/InGame/PrefabUISystem.cs'
        if not property_binder_file.is_file():
            return {}
        result = {}
        with open(property_binder_file) as f:
            mod_re = re.compile(r'^[^"]*"(?P<loc_key1>[^"]*)\.(?P<loc_key2>[^"]*)", "(?P<var_type>[^"]*)", \((?P<cls>[a-zA-Z]*)Data data\) => (?P<code>.*data\.(?P<var_name>(m_)?[a-zA-Z]*).*)')
            for line in f:
                match = mod_re.match(line)
                if match:
                    cls = match.group("cls")
                    if cls not in result:
                        result[cls] = {}
                    attribute = convert_cs_member_name_to_python_attribute(match.group("var_name"))
                    var_type = match.group('var_type')
                    code = match.group('code')
                    if not code.startswith('data.'):
                        var_type += ' / ' + code
                    result[cls][attribute] = {
                        'loc': self.localizer.localize(match.group('loc_key1'), match.group('loc_key2')),
                        'var_type': var_type
                    }
        return result


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

    def print_possible_table_columns(self, assets: List[CS2Asset], var_name: str, code_folder: Path = None):
        """code_folder contains the c# code. It can be extracted by assetrippers"""
        extra_data = self._get_loc_and_variable_types_from_code(code_folder)
        sub_attributes = {}
        main_class = assets[0].__class__.__name__
        for attribute, loc_or_dict in self.get_possible_table_columns(assets).items():
            if isinstance(loc_or_dict, Mapping):
                # save for later to print the main attributes first
                sub_attributes[attribute] = loc_or_dict
            else:
                if main_class in extra_data and attribute in extra_data[main_class]:
                    print(f"'{extra_data[main_class][attribute]['loc']}': {var_name}.{attribute},  # {extra_data[main_class][attribute]['var_type']}")
                else:
                    print(f"'{loc_or_dict}': {var_name}.{attribute},")
        for attribute, dic in sub_attributes.items():
            for sub_attribute, loc in dic.items():
                if attribute in extra_data and sub_attribute in extra_data[attribute]:
                    print(f"'{extra_data[attribute][sub_attribute]['loc']}': {var_name}.{attribute}.{sub_attribute} if '{attribute}' in {var_name} else '',  # {extra_data[attribute][sub_attribute]['var_type']}")
                else:
                    print(f"'{loc}': {var_name}.{attribute}.{sub_attribute} if '{attribute}' in {var_name} else '',")

    ######################################
    # Table generators and their helpers #
    ######################################

    def get_all_service_buildings_tables_by_category(self) -> Dict[str, List[str]]:
        buildings_by_category = {}
        category_sorts = {}
        cats = {}
        for building in self.parser.service_buildings.values():
            category = self._format_service_category(building, building.ServiceObject.service.name, building.UIObject.group.name if 'UIObject' in building else building.ServiceObject.service.name)
            if category not in buildings_by_category:
                buildings_by_category[category] = []
            if category not in category_sorts and 'UIObject' in building:
                category_sorts[category] = (building.UIObject.group.menu.UIObject.priority, building.UIObject.group.UIObject.priority)
                cats[category] = f'== {building.UIObject.group.menu.display_name} ==\n=== {building.UIObject.group.display_name} ==='
            buildings_by_category[category].append(building)
        for upgrade in filter(lambda b: b.name != 'HydroelectricPowerPlant01_End', self.parser.service_building_upgrades.values()):
            category = self._format_service_category(upgrade, upgrade.ServiceUpgrade.buildings[0].ServiceObject.service.name, upgrade.ServiceUpgrade.buildings[0].UIObject.group.name)
            buildings_by_category[category].append(upgrade)

        result = {}
        for category, buildings in sorted(buildings_by_category.items(), key=lambda item: category_sorts[item[0]]):
            result[category] = self.generate_service_buildings_table(sorted(buildings, key=lambda b:
                (b.ServiceUpgrade.buildings[0].UIObject.group.UIObject.priority, b.ServiceUpgrade.buildings[0].UIObject.priority, b.UIObject.priority if 'UIObject' in b else 0) if 'ServiceUpgrade' in b
                else (b.UIObject.group.UIObject.priority, b.UIObject.priority, 0) if hasattr(b, 'UIObject')
                else (0, 0, 0)))

        return result

    def generate_all_service_buildings_tables(self):
        result = ''
        for category, tables in self.get_all_service_buildings_tables_by_category().items():
            result += f'== {category} ==\n'
            result += '\n'.join(tables)
            result += '\n'
        return result

    def _format_service_category(self, building: BaseBuilding, category: str, subcategory: str = None):
        split_up = {
            'communications': True,
            'education_and_research': True,
            'electricity': False,
            'fire_and_rescue': True,
            'garbage_management': False,
            'health_and_deathcare': True,
            'parks_and_recreation': lambda building: 'maintenance' if 'MaintenanceDepot' in building else 'park',
            'police_and_administration': True,
            'roads': True,
            'transportation': True,
            'water_and_sewage': False,
        }
        category = category.replace(' ', '_').replace('&', 'and').lower()
        if not split_up[category]:
            return category
        if callable(split_up[category]):
            subcategory = split_up[category](building)
        if subcategory is None:
            return category
        else:
            subcategory = subcategory.replace(' ', '_').replace('&', 'and').lower()
            return f'{category}_{subcategory}'

    def _format_electricity_production(self, building: CS2Asset):
        if 'PowerPlant' not in building and 'Battery' not in building:
            return ''
        if 'WaterPowered' in building:
            return 'varies'

        extra_text = ''
        if 'PowerPlant' in building:
            production = building.PowerPlant.electricityProduction
        else:
            production = 0
        if 'WindPowered' in building:
            production = building.WindPowered.production
        elif 'GroundWaterPowered' in building:
            production = building.GroundWaterPowered.production
        elif 'SolarPowered' in building:
            production = building.SolarPowered.production
        elif 'GarbagePowered' in building:
            production = building.GarbagePowered.capacity
        elif 'EmergencyGenerator' in building:
            production = building.EmergencyGenerator.electricityProduction

        if 'Battery' in building:
            if production == 0:
                production = building.Battery.powerOutput
            else:
                extra_text = f' ({self.formatter.power(building.Battery.powerOutput)} from batteries)'

        if production == 0:
            return ''
        else:
            return self.formatter.power(production) + extra_text

    def generate_service_buildings_table(self, buildings) -> List[str]:
        """list of main table and extra table"""
        format = self.formatter
        data = [{
            'Name': f'{{{{iconbox|{building.display_name}|{building.description}|image={building.get_wiki_filename()}}}}}',
            'Size (cells)': building.size,
            'DLC': building.dlc.icon,
            'Requirements': building.Unlockable.format() if 'Unlockable' in building and hasattr(building.Unlockable, 'format') else '',
            'Cost': format.cost(building.ServiceUpgrade.upgradeCost if 'ServiceUpgrade' in building else building.PlaceableObject.constructionCost),
            'Upkeep per month': format.cost(building.ServiceConsumption.upkeep),
            'XP': building.ServiceUpgrade.xPReward if 'ServiceUpgrade' in building else building.PlaceableObject.xPReward,
            'Attractiveness': f'{{{{icon|attractiveness}}}} {building.Attraction.attractiveness}' if hasattr(building,
                                                                                                             'Attraction') and building.Attraction.attractiveness > 0 else '',
            'Effects': format.create_wiki_list(building.get_effect_descriptions(),
                                                       no_list_with_one_element=True),
            # unused
            # 'overrideHeight': building.overrideHeight if 'overrideHeight' in building else '',
            # better to show this as a requirement in the other buildings. This formatting doesnt work anyway
            # 'unlocks': ', '.join([', '.join(unlock.format()) for unlock in building.UnlockOnBuild.unlocks]) if 'UnlockOnBuild' in building else '',
            'Goods consumption': ', '.join((building.CityServiceBuilding.format_upkeeps() if 'CityServiceBuilding' in building else []) + (building.UpkeepModifier.format() if 'UpkeepModifier' in building else [])),

            'Electricity production': self._format_electricity_production(building),
            'productionPerUnit': building.GarbagePowered.productionPerUnit if 'GarbagePowered' in building else '',
            # 'productionFactor': building.WaterPowered.productionFactor if 'WaterPowered' in building else '',
            # 'capacityFactor': building.WaterPowered.capacityFactor if 'WaterPowered' in building else '',
            'maxWind': f'{building.WindPowered.maximumWind:.1f}' if 'WindPowered' in building else '',
            'maxGroundWater': building.GroundWaterPowered.maximumGroundWater if 'GroundWaterPowered' in building else '',
            'Battery capacity': format.energy(building.Battery.capacity) if 'Battery' in building else '',  # energy
            # added to electricity production
            # 'Battery output': format.power(building.Battery.powerOutput) if 'Battery' in building else '',  # power

            'Garbage storage capacity': format.weight(building.GarbageFacility.garbageCapacity) if 'GarbageFacility' in building else '',  # weight
            'Garbage trucks': building.GarbageFacility.vehicleCapacity if 'GarbageFacility' in building else '',  # integer
            # seems to always be 1
            # 'transportCapacity': building.GarbageFacility.transportCapacity if 'GarbageFacility' in building else '',
            'Garbage processing capacity': (format.weight_per_month(building.GarbageFacility.processingSpeed) + (
                ' (only industrial waste)' if building.GarbageFacility.industrialWasteOnly else ''))
            if 'GarbageFacility' in building else '',  # weightPerMonth
            'resources': format.create_wiki_list(building.ResourceProducer.format(), no_list_with_one_element=True) if 'ResourceProducer' in building else '',

            # subway/tram/etc. should be obvious from the building name and category
            # 'transportType': building.TransportDepot.transportType if 'TransportDepot' in building else '',
            # 'energyTypes': building.TransportDepot.energyTypes if 'TransportDepot' in building else '',
            'Vehicles': building.TransportDepot.vehicleCapacity if 'TransportDepot' in building else '',  # integer
            'productionDuration': building.TransportDepot.productionDuration if 'TransportDepot' in building else '',
            'maintenanceDuration': building.TransportDepot.maintenanceDuration if 'TransportDepot' in building else '',
            'dispatchCenter': building.TransportDepot.dispatchCenter if 'TransportDepot' in building else '',
            'Maintenance types': ', '.join(typ.name for typ in building.MaintenanceDepot.maintenanceType) if 'MaintenanceDepot' in building else '',
            'Maintenance vehicles': building.MaintenanceDepot.vehicleCapacity if 'MaintenanceDepot' in building else '',  # integer
            # not sure what this is
            # 'vehicleEfficiency': building.MaintenanceDepot.vehicleEfficiency if 'MaintenanceDepot' in building else '',

            'Comfort': building.TransportStation.comfortFactor * 100 if 'TransportStation' in building else (building.ParkingFacility.comfortFactor * 100 if 'ParkingFacility' in building else ''),  # integer / (int)math.round(100f * data.m_ComfortFactor))

            'Has companies': building.CompanyObject.selectCompany if 'CompanyObject' in building else '',
            # TODO: find out how companies are stored and create a list somehow
            # 'companies': building.CompanyObject.companies if 'CompanyObject' in building else '',
            'Water output': building.WaterPumpingStation.capacity if 'WaterPumpingStation' in building else '',  # volumePerMonth
            'Decontamination rate': building.WaterPumpingStation.purification if 'WaterPumpingStation' in building else '',  # percentage / Mathf.RoundToInt(100f * data.m_Purification)),
            'Water source': ', '.join(water_type.display_name for water_type in building.WaterPumpingStation.allowedWaterTypes) if 'WaterPumpingStation' in building else '',
            'Sewage treatment': building.SewageOutlet.capacity if 'SewageOutlet' in building else '',  # volumePerMonth
            # TODO: more formatting based on how the game does it
            'Purification rate': building.SewageOutlet.purification if 'SewageOutlet' in building else '',  # percentage / Mathf.RoundToInt(100f * data.m_Purification)),
            'Student capacity': building.School.studentCapacity if 'School' in building else '',  # integer
            'Level': building.School.level.display_name if 'School' in building else '',
            'graduationModifier': building.School.graduationModifier if 'School' in building else '',
            'Post vans': building.PostFacility.postVanCapacity if 'PostFacility' in building else '',  # integer
            'Post trucks': building.PostFacility.postTruckCapacity if 'PostFacility' in building else '',  # integer
            'Mail storage capacity': building.PostFacility.mailStorageCapacity if 'PostFacility' in building else '',
            'Mailbox capacity': building.PostFacility.mailBoxCapacity if 'PostFacility' in building else '',
            'Sorting speed': f'{building.PostFacility.sortingRate} / month' if 'PostFacility' in building and building.PostFacility.sortingRate else '',  # integerPerMonth

            'Fire engines': building.FireStation.fireEngineCapacity if 'FireStation' in building else '',  # integer
            'Fire helicopters': building.FireStation.fireHelicopterCapacity if 'FireStation' in building else '',  # integer
            'disasterResponseCapacity': building.FireStation.disasterResponseCapacity if 'FireStation' in building else '',

            'Ambulances': building.Hospital.ambulanceCapacity if 'Hospital' in building else '',  # integer
            'Medical helicopters': building.Hospital.medicalHelicopterCapacity if 'Hospital' in building else '',  # integer
            'Patient capacity': building.Hospital.patientCapacity if 'Hospital' in building else '',  # integer
            'treatmentBonus': building.Hospital.treatmentBonus if 'Hospital' in building else '',
            'Min health': building.Hospital.healthRange['x'] if 'Hospital' in building else '',
            'Max health': building.Hospital.healthRange['y'] if 'Hospital' in building else '',
            'treatDiseases': building.Hospital.treatDiseases if 'Hospital' in building else '',
            'treatInjuries': building.Hospital.treatInjuries if 'Hospital' in building else '',
            'Patrol Cars': building.PoliceStation.patrolCarCapacity if 'PoliceStation' in building else '',  # integer
            'Police Helicopters': building.PoliceStation.policeHelicopterCapacity if 'PoliceStation' in building else '',  # integer
            'Jail Capacity': building.PoliceStation.jailCapacity if 'PoliceStation' in building else '',
            'Purposes':  ', '.join(purpose.name for purpose in building.PoliceStation.purposes) if 'PoliceStation' in building else '',
            'maintenancePool': building.Park.maintenancePool if 'Park' in building else '',
            # seems to always be true
            # 'allowHomeless': building.Park.allowHomeless if 'Park' in building else '',

            'Leisure': building.LeisureProvider.format() if 'LeisureProvider' in building else '',

            'Prison Vans': building.Prison.prisonVanCapacity if 'Prison' in building else '',  # integer
            'Jail capacity': building.Prison.prisonerCapacity if 'Prison' in building else '',
            'Hearses': building.DeathcareFacility.hearseCapacity if 'DeathcareFacility' in building else '',  # integer
            'Storage Capacity': building.DeathcareFacility.storageCapacity if 'DeathcareFacility' in building else '',  # integer
            'Processing Capacity': building.DeathcareFacility.processingRate if 'DeathcareFacility' in building else '',  # integerPerMonth / Mathf.CeilToInt(data.m_ProcessingRate)),
            'Traded resources': ','.join(f'{{{{icon|{r.display_name}}}}}' for r in building.CargoTransportStation.tradedResources) if 'CargoTransportStation' in building else '',
            'transports': building.CargoTransportStation.transports if 'CargoTransportStation' in building else '',
            'loadingFactor': building.CargoTransportStation.loadingFactor if 'CargoTransportStation' in building else '',
            # min/mx ticks between transports?
            # 'transportInterval': building.CargoTransportStation.transportInterval if 'CargoTransportStation' in building else '',
            'Range': format.distance(building.TelecomFacility.range) if 'TelecomFacility' in building else '',  # length / Mathf.CeilToInt(data.m_Range)),
            'Network Capacity': format.data_rate(building.TelecomFacility.networkCapacity) if 'TelecomFacility' in building else '',  # dataRate / Mathf.CeilToInt(data.m_NetworkCapacity)),
            'Penetrate Terrain': building.TelecomFacility.penetrateTerrain if 'TelecomFacility' in building else '',
            'Shelter Capacity': building.EmergencyShelter.shelterCapacity if 'EmergencyShelter' in building else '',  # integer
            'Evacuation Buses': building.EmergencyShelter.vehicleCapacity if 'EmergencyShelter' in building else '',  # integer

            # TODO: seems to be the capacity, but other parking spaces determine capacity in another way
            'garageMarkerCapacity': building.ParkingFacility.garageMarkerCapacity if 'ParkingFacility' in building else '',
            'Default policies': format.create_wiki_list(building.DefaultPolicies.format(), no_list_with_one_element=True) if 'DefaultPolicies' in building else '',
            # TODO: no idea what that probability is
            'defaultProbability': building.SubObjectDefaultProbability.defaultProbability if 'SubObjectDefaultProbability' in building else '',

            # mainly used in upgrades:
            'carRefuelTypes': building.TransportStation.carRefuelTypes.display_name if 'TransportStation' in building else '',
            'trainRefuelTypes': building.TransportStation.trainRefuelTypes.display_name if 'TransportStation' in building else '',
            'watercraftRefuelTypes': building.TransportStation.watercraftRefuelTypes.display_name if 'TransportStation' in building else '',
            'aircraftRefuelTypes': building.TransportStation.aircraftRefuelTypes.display_name if 'TransportStation' in building else '',
            'Vehicle fuel': building.TransportDepot.energyTypes.display_name if 'TransportDepot' in building else '',
            # TODO: better formatting and maybe integration into another column
            'activationThreshold': building.EmergencyGenerator.activationThreshold if 'EmergencyGenerator' in building else '',
            # TODO: not sure what these are
            'maintenance vehicleEfficiency': building.MaintenanceDepot.vehicleEfficiency if 'MaintenanceDepot' in building and building.MaintenanceDepot.vehicleEfficiency != 0 else '',
            'fire vehicleEfficiency': building.FireStation.vehicleEfficiency if 'FireStation' in building and building.FireStation.vehicleEfficiency != 0 else '',

        } for building in buildings]
        result = []
        result.append(self.get_SVersion_header(scope='table') + '\n'
                      + self.make_wiki_table(data, table_classes=['mildtable'],
                                             one_line_per_cell=True, remove_empty_columns=True))
        result.append(self.get_extra_building_data_table(buildings))

        return result

    def get_extra_building_data_table(self, buildings):
        format = self.formatter
        extra_data = [{
            'Name': f'{building.display_name}',
            # 'Category': building.ServiceObject.service.display_name,
            'Service range': building.ServiceCoverage.range if 'ServiceCoverage' in building else '',
            'Service capacity': building.ServiceCoverage.capacity if 'ServiceCoverage' in building else '',
            'Service magnitude': building.ServiceCoverage.magnitude if 'ServiceCoverage' in building else '',
            'Ground pollution': building.format_pollution('ground'),
            'Air pollution': building.format_pollution('air'),
            'Noise pollution': building.format_pollution('noise'),

            # 'scaleWithRenters': building.Pollution.scaleWithRenters,
            'Electricity consumption': building.ServiceConsumption.electricityConsumption if 'ServiceConsumption' in building else '',
            'Water consumption': building.ServiceConsumption.waterConsumption if 'ServiceConsumption' in building else '',
            'Telecommunication consumption': building.ServiceConsumption.telecomNeed if 'ServiceConsumption' in building else '',
            'Garbage accumulation': building.ServiceConsumption.garbageAccumulation if 'ServiceConsumption' in building else '',

            'Workplaces': building.Workplace.workplaces if 'Workplace' in building else '',
            'Max. needed education': building.Workplace.get_highest_needed_education().display_name if 'Workplace' in building else '',
            'Evening shifts': f'{building.Workplace.eveningShiftProbability * 100:g}%' if 'Workplace' in building else '',
            'Night shifts': f'{building.Workplace.nightShiftProbability * 100:g}%' if 'Workplace' in building else '',

            'Initial resources': format.create_wiki_list(building.InitialResources.format(),
                                                         no_list_with_one_element=True) if 'InitialResources' in building else '',
            'Storage limit': building.StorageLimit.storageLimit if 'StorageLimit' in building else '',

        } for building in buildings]
        extra_data_table = self.get_SVersion_header(scope='table') + '\n' + self.make_wiki_table(extra_data,
                                                                                                 table_classes=[
                                                                                                     'mildtable'],
                                                                                                 one_line_per_cell=True,
                                                                                                 remove_empty_columns=True)
        return extra_data_table

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
            'DLC': building.dlc.icon,
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
            'DLC': road.dlc.icon,
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

    def generate_maps_table(self):
        data = [{
            'id': m.display_name,
            'Name': f'{{{{iconbox|{m.display_name}|{m.description}|image={m.display_name} Preview.png}}}}',
            # 'Name': m.display_name,
            # 'Preview': f'[[File:{m.display_name} Preview.png|38px]]',
            'DLC': ', '.join([dlc.icon for dlc in m.contentPrerequisite]),
            'Theme': f'{{{{icon|{m.theme}}}}}',
            'Weather': f'{{{{weather|{m.cloudiness}|{m.precipitation}}}}}',
            'Temperature': f'{m.temperatureRange["min"]:0.1f}–{m.temperatureRange["max"]:0.1f}°C',
            'Cloudiness': f'{m.cloudiness:.0%}',
            'Precipitation': f'{m.precipitation:.0%}',
            'N/S': f'{{{{latitude|{"s" if m.latitude < 0 else "n"}}}}}',
            'Latitude': f'{m.latitude:.2f}',
            'Longitude': f'{m.longitude:.2f}',
            'Buildable Area': f'{m.buildableLand/m.area:.0%}',
            'Outside Connections': ' '.join(m.format_connection_icons()),
            '{{icon|fertile land}}': f'data-sort-value="{m.resources["fertile"]}" | {self.formatter.area(m.resources["fertile"])}' ,
            '{{icon|forest}}':  self.formatter.weight(m.resources['forest']),
            '{{icon|ore}}': self.formatter.weight(m.resources['ore']),
            '{{icon|oil}}': self.formatter.weight(m.resources['oil']),
        } for m in sorted(self.parser.maps, key=lambda m: (m.contentPrerequisite[0].value, m.display_name))]

        return (self.get_SVersion_header(scope='table') + '\n'
            + self.make_wiki_table(data, table_classes=['mildtable'],
                                   one_line_per_cell=True, remove_empty_columns=True, row_id_key='id'))

    def generate_landmark_tables(self):
        format = self.formatter
        landmarks = sorted(self.parser.landmarks.values(), key=attrgetter('display_name'))
        data = [{
            'Name': f'{{{{iconbox|{landmark.display_name}|{landmark.description}|image={landmark.get_wiki_filename()}}}}}',
            'Size (cells)': landmark.size,
            'DLC': landmark.dlc.icon,
            'Requirements': landmark.Unlockable.format() if 'Unlockable' in landmark and hasattr(landmark.Unlockable,
                                                                                                 'format') else '',
            'Cost': format.cost(landmark.PlaceableObject.constructionCost),
            'Upkeep per month': format.cost(landmark.ServiceConsumption.upkeep),
            'XP': landmark.ServiceUpgrade.xPReward if 'ServiceUpgrade' in landmark else landmark.PlaceableObject.xPReward,
            'Attractiveness': f'{{{{icon|attractiveness}}}} {landmark.Attraction.attractiveness}' if hasattr(landmark,
                                                                                                             'Attraction') and landmark.Attraction.attractiveness > 0 else '',
            'Effects': format.create_wiki_list(landmark.get_effect_descriptions(),
                                               no_list_with_one_element=True),
            'Leisure': landmark.LeisureProvider.format() if 'LeisureProvider' in landmark else '',
            'Has companies': landmark.CompanyObject.selectCompany if 'CompanyObject' in landmark else '',
            'maintenancePool': landmark.Park.maintenancePool if 'Park' in landmark else '',

        } for landmark in landmarks]

        return [self.get_SVersion_header(scope='table') + '\n'
                + self.make_wiki_table(data, table_classes=['mildtable'],
                                       one_line_per_cell=True, remove_empty_columns=True),
                self.get_extra_building_data_table(landmarks)]


if __name__ == '__main__':
    generator = TableGenerator()
    generator.run(sys.argv)
