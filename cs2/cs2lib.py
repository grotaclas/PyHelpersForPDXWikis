import subprocess

from functools import cached_property
from tempfile import NamedTemporaryFile
from typing import List, Dict, Any

from common.paradox_lib import IconEntity, AttributeEntity
from cs2.cs2_enum import DLC
from cs2.cs2_enum_auto_generated import *
from cs2.game import cs2game
from cs2.text_formatter import CS2WikiTextFormatter


def convert_cs_member_name_to_python_attribute(s: str):
    """ remove the prefix m_ and lowercase the first letter"""
    s = s.removeprefix('m_')
    return s[0].lower() + s[1:]


def convert_svg_to_png(svg_file: Path, destination_file: Path | str, width: int = 256):
    subprocess.run(
        ['inkscape', svg_file,
         '--export-type=png', f'--export-filename={destination_file}', f'--export-width={width}'])


################
# Base classes #
################


class CS2Asset(AttributeEntity):
    cs2_class: str
    parent_asset: 'CS2Asset'

    # filename and path id together should be unique
    file_name: str
    path_id: int

    def __init__(self, cs2_class: str, file_name: str, path_id: int, parent: 'CS2Asset' = None):
        self.cs2_class = cs2_class
        self.file_name = file_name
        self.path_id = path_id
        self.parent_asset = parent

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        if isinstance(other, CS2Asset):
            return self.file_name == other.file_name and self.path_id == other.path_id
        else:
            return False

    @staticmethod
    def calculate_id(file_name: str, path_id: int) -> str:
        """Unique id based on the filename of the asset file and the path id"""
        return f'{file_name}:{path_id}'

    @cached_property
    def id(self) -> str:
        """Unique id based on the filename of the asset file and the path id"""
        return self.calculate_id(self.file_name, self.path_id)


class GenericAsset(CS2Asset):
    """An asset which doesn't implement any special handling"""
    pass


class NamedAsset(CS2Asset):
    name: str
    display_name: str

    localization_category = 'Assets'
    localization_sub_category_display_name = 'NAME'
    localization_sub_category_description = 'DESCRIPTION'

    def __init__(self, cs2_class: str, file_name: str, path_id: int, parent: CS2Asset = None):
        super().__init__(cs2_class, file_name, path_id, parent)
        if 'display_name' not in self.extra_data_functions:
            self.extra_data_functions = self.extra_data_functions.copy()  # copy to not modify the class attribute of the parent
            self.extra_data_functions['display_name'] = self._get_display_name

    def __str__(self):
        return self.display_name

    def _get_display_name(self, data):
        return cs2game.parser.localizer.localize(
            self.localization_category, self.localization_sub_category_display_name, data['name']
        )


    @cached_property
    def description(self):
        return cs2game.localizer.localize(self.localization_category, self.localization_sub_category_description, self.name).replace('\n', '').replace('\r', '')

    @cached_property
    def dlc(self) -> 'DLC':
        if hasattr(self, 'ContentPrerequisite'):
            if 'DLC_Requirement' in self.ContentPrerequisite.contentPrerequisite:
                return DLC(self.ContentPrerequisite.contentPrerequisite.DLC_Requirement.dlc['id'])
            elif 'PdxLoginRequirement' in self.ContentPrerequisite.contentPrerequisite:
                return DLC.PdxLoginRequirement
            else:
                raise NotImplementedError(f'Unknown content requiremnet in {self.name}/{self.display_name}')
        else:
            return DLC.BaseGame


#################
# Asset classes #
#################

class AdjustHappiness(CS2Asset):
    wellbeingEffect: int
    healthEffect: int
    # targets: List[AdjustHappinessTarget]

    def _format_effect(self, value, effect_name):
        formatter = CS2WikiTextFormatter()
        targets = ', '.join(target.display_name for target in self.targets)
        return f'{{{{icon|{effect_name}}}}} {{{{green|{formatter.add_plus_minus(value)}%}}}} {effect_name} for {targets}'

    def format_wellbeing_effect(self):
        if self.wellbeingEffect > 0:
            return self._format_effect(self.wellbeingEffect, 'Well-Being')
        else:
            return ''

    def format_health_effect(self):
        if self.healthEffect > 0:
            return self._format_effect(self.healthEffect, 'Health')
        else:
            return ''



class AssetStamp(NamedAsset):
    """used by intersections"""
    width: int
    depth: int
    constructionCost: int
    upKeepCost: int


class BaseBuilding(NamedAsset):
    """For Buildings and Building upgrades which sometimes use the BuildingExtension class
     and sometimes use the Building class"""

    def add_attributes(self, attributes: Dict[str, any]):
        super().add_attributes(attributes)
        if 'ServiceUpgrade' in attributes:
            self.localization_sub_category_description = 'UPGRADE_DESCRIPTION'

    def get_wiki_filename(self) -> str:
        # landmarks are also service buildings, so this check has to be first
        if 'UIObject' in self and self.UIObject.group and self.UIObject.group.name == 'SignaturesLandmarks':
            return f'Landmark {self.display_name}.png'
        if 'ServiceUpgrade' in self:
            return f'Service building upgrade {self.display_name}.png'
        if 'CityServiceBuilding' in self:
            return f'Service building {self.display_name}.png'


    def get_effect_descriptions(self) -> List[str]:
        """List of formatted effect descriptions"""

        effects = []
        if hasattr(self, 'CityEffects'):
            for effect in self.CityEffects.effects:
                effects.append(effect.description)
        if hasattr(self, 'LocalEffects'):
            for effect in self.LocalEffects.effects:
                effects.append(effect.description)

        if hasattr(self, 'AdjustHappiness'):
            wellbeing_effect = self.AdjustHappiness.format_wellbeing_effect()
            if wellbeing_effect:
                effects.append(wellbeing_effect)
            health_effect = self.AdjustHappiness.format_health_effect()
            if health_effect:
                effects.append(health_effect)
        return effects

    def format_pollution(self, pollution_type: str):
        # should only be one type, but as a failsafe, we support multiple lines and merge them at the end
        pollution_lines = []
        formatter = CS2WikiTextFormatter()
        if 'Pollution' in self:
            pollution = getattr(self.Pollution, f'{pollution_type}Pollution')
            if pollution != 0:
                pollution_lines.append(f'{{{{icon|{pollution_type} pollution}}}} {pollution}')
        if 'PollutionModifier' in self:
            pollution = getattr(self.PollutionModifier, f'{pollution_type}PollutionMultiplier')
            if pollution != 0:
                pollution_lines.append(f'{{{{icon|{pollution_type} pollution}}}} {formatter.format_percent(pollution)}')
        return formatter.create_wiki_list(pollution_lines, no_list_with_one_element=True)


class Building(BaseBuilding):
    circular: bool
    lotWidth: int
    lotDepth: int

    @cached_property
    def size(self):
        return f'{self.lotWidth}×{self.lotDepth}'


class BuildingExtension(BaseBuilding):
    circular: bool
    externalLot: bool
    position: Dict[str, float]
    overrideLotSize: Dict[str, int]
    overrideHeight: float

    # localization_sub_category_display_name = 'UPGRADE_NAME'


    @cached_property
    def size(self):
        result = ''
        if sum(self.overrideLotSize.values()) > 0:
            result = f'{self.overrideLotSize["x"]}×{self.overrideLotSize["y"]}'
        if sum(self.position.values()) > 0:  # seems to be currently unused
            result += f'(Position: {self.position["x"]}, {self.position["y"]}, {self.position["z"]}'
        return result


class Fence(NamedAsset):
    """Road signs and road upgrades"""
    pass


class Pathway(NamedAsset):
    speedLimit: float


class Pollution(CS2Asset):
    groundPollution: int
    airPollution: int
    noisePollution: int
    scaleWithRenters: bool


class Requirement(CS2Asset):
    def format(self) -> List[str]:
        return [f'requirements formatting of {self.cs2_class}not implemented']


class DevTreeNode(Requirement, NamedAsset):
    service: 'Service'
    requirements: list  # list['DevTreeNodePrefab']
    cost: int
    horizontalPosition: int
    verticalPosition: float
    iconPath: str

    localization_category = 'progression'
    localization_sub_category_display_name = 'node_name'
    localization_sub_category_description = 'node_description'

    def format(self) -> List[str]:
        return [f'{{{{icon|development points}}}} [[Development Tree#{self.display_name}|{self.display_name}]]']


class Road(NamedAsset):
    roadType: int
    speedLimit: float
    # zoneBlock: ZoneBlockPrefab
    trafficLights: bool
    highwayRules: bool
    sections: List[Dict]

    def format_speedLimit(self):
        eu_limit = cs2game.parser.get_theme_speedlimit('EU', int(self.speedLimit))
        na_limit = cs2game.parser.get_theme_speedlimit('NA', int(self.speedLimit))
        if eu_limit is not None:
            return (
                f'{eu_limit} km/h<ref name=speedlimit{self.speedLimit}>The internal speedlimit is {self.speedLimit}.'
                f' This is displayed as {eu_limit} in the european theme and as {na_limit} in the north american theme</ref>')
        else:
            return (
                f'{int(self.speedLimit / 2)} km/h<ref name=speedlimit{self.speedLimit}>The internal speedlimit is {self.speedLimit}.'
                f' There are no speed limit signs for this limit in the themes, but the estimated speedlimit for'
                f' the european theme would be {int(self.speedLimit / 2)} km/h and {int(self.speedLimit / 2 / 1.609344)} mph'
                f' for the north american theme</ref>')

    def _format_icon(self, icon_name: str, icon_description: str, icon_size: str = '48px',
                     annotation_name: str = '', annotation: str = ''):
        if annotation:
            if annotation_name:
                annotation_name_code = f' name={annotation_name}'
            else:
                annotation_name_code = ''
            annotation_code = f'<ref{annotation_name_code}>{annotation}</ref>'
        else:
            annotation_code = ''
        return f'[[File:{icon_name}.png|{icon_description}|link=|{icon_size}]]{annotation_code}'

    def get_services_icons(self, icon_size: str = '48px') -> str:
        icons = []
        if hasattr(self, 'WaterPipeConnection'):
            if self.WaterPipeConnection.has_combined_pipe():
                icons.append(self._format_icon('Combined Pipe', 'Water & Sewage pipes', icon_size))
            elif self.WaterPipeConnection.has_water_pipe():
                icons.append(self._format_icon('Water Pipe', 'Water pipe', icon_size))
            elif self.WaterPipeConnection.has_sewage_pipe():
                icons.append(self._format_icon('Sewage Pipe', 'Sewage pipe', icon_size))
        if hasattr(self, 'ElectricityConnection'):
            formatter = CS2WikiTextFormatter()
            if self.ElectricityConnection.capacity > 0:
                electricity_icon = self._format_icon('Electricity',
                                                     f'{self.ElectricityConnection.voltage.name} voltage power line with {self.ElectricityConnection.format_capacity()}',
                                                     icon_size)
                if len(self.ElectricityConnection.requireAll) > 0:
                    reqs = [req.name for req in self.ElectricityConnection.requireAll]
                    electricity_icon = f'({electricity_icon})<ref name=electricity_reqs_{"_".join(reqs)}>Electricity connection requires the road properties {" and ".join(reqs)}</ref>'
                if len(self.ElectricityConnection.requireAny) > 0:
                    raise NotImplementedError('ElectricityConnection.requireAny is not implemented')
                if len(self.ElectricityConnection.requireNone) > 0:
                    raise NotImplementedError('ElectricityConnection.requireNone is not implemented')
                icons.append(electricity_icon)
        return '&nbsp;'.join(icons)

    @cached_property
    def costs(self):
        result = {
            'base': {'construction': 0, 'upkeep': 0, 'elevation_cost': 0},
            'tunnel': {'construction': 0, 'upkeep': 0, 'elevation_cost': 0},
            'elevated': {'construction': 0, 'upkeep': 0, 'elevation_cost': 0},
        }
        for section in self.sections + self.UndergroundNetSections.sections:
            self._add_costs_from_section(section, result)
            for subsection in section['m_Section'].subSections:
                self._add_costs_from_section(subsection, result, section)

        cost_multiplier = 125

        return {category: {cost: value * cost_multiplier
                           for cost, value in costs.items()}
                for category, costs in result.items()}

    def _fulfills_req_type(self, req_type: NetPieceRequirements|None, req_list) -> bool:
        for reqs in req_list:
            if req_type is None:
                if reqs['m_RequireAll'] or reqs['m_RequireAny']:
                    return False
            else:
                if len(reqs['m_RequireAll']) > 1:
                    return False  # checking against multiple requirements is not implemented
                if len(reqs['m_RequireAll']) == 1 and reqs['m_RequireAll'] != [req_type.value]:
                    return False
                if reqs['m_RequireAny'] and req_type.value not in reqs['m_RequireAny']:
                    return False
                if reqs['m_RequireNone'] and req_type.value in reqs['m_RequireNone']:
                    return False
        return True

    def _add_costs_from_section(self, section, result, parent_section: Dict = None):
        if parent_section is None:
            parent_section = {'m_RequireAll': [], 'm_RequireAny': [], 'm_RequireNone': []}
        supported_types = {'base': None, 'elevated': NetPieceRequirements.Elevated, 'tunnel': NetPieceRequirements.Tunnel}
        for piece in section['m_Section'].pieces:
            if not hasattr(piece['m_Piece'], 'PlaceableNetPiece'):
                continue

            for section_type, req_type in supported_types.items():
                if self._fulfills_req_type(req_type, [parent_section, section, piece]):
                    result[section_type]['construction'] += piece['m_Piece'].PlaceableNetPiece.constructionCost
                    result[section_type]['upkeep'] += piece['m_Piece'].PlaceableNetPiece.upkeepCost
                    if section_type == 'elevated':
                        result[section_type]['elevation_cost'] += piece['m_Piece'].PlaceableNetPiece.elevationCost

    def _get_car_lanes_from_section(self, section) -> int:
        lanes = 0
        for piece in section['m_Section'].pieces:
            if hasattr(piece['m_Piece'], 'NetPieceLanes') and self._fulfills_req_type(None, [section, piece]):
                for lane in piece['m_Piece'].NetPieceLanes.lanes:
                    if hasattr(lane['m_Lane'], 'CarLane') and not lane['m_Lane'].CarLane.startingLane and not lane['m_Lane'].CarLane.endingLane:
                        lanes += 1
        return lanes

    @cached_property
    def car_lanes(self) -> int:
        lanes = 0
        for section in self.sections:
            if self._fulfills_req_type(None, [section]):
                lanes += self._get_car_lanes_from_section(section)
                for subsection in section['m_Section'].subSections:
                    lanes += self._get_car_lanes_from_section(subsection)
        return lanes


class SignatureBuilding(CS2Asset):
    zoneType: 'Zone'
    xPReward: int
    unlockEventImage: str

    def get_wiki_file_tag(self, size: str = '300px') -> str:
        filename = self.get_wiki_filename()
        return f'[[File:{filename}|{size}|{self.get_display_name()}]]'

    def get_wiki_filename(self):
        return 'Signature building unlock ' + self.get_display_name() + '.png'

    def get_name(self):
        return self.unlockEventImage.split('/')[-1].removesuffix('.png')

    def get_display_name(self):
        return cs2game.localizer.localize('Assets', 'NAME',
                                          self.get_name(), default=self.parent_asset.display_name)

    def get_unlock_image(self) -> Path:
        return cs2game.game_path / 'Cities2_Data/StreamingAssets/~UI~/GameUI'


class StaticObjectPrefab(NamedAsset):
    circular: bool


class Surface(NamedAsset):
    pass


class Track(NamedAsset):
    trackType: int  # TrackTypes
    speedLimit: float


class TransportLine(NamedAsset):
    # accessConnectionType: RouteConnectionType
    # routeConnectionType: RouteConnectionType
    # accessTrackType: TrackTypes
    # routeTrackType: TrackTypes
    # accessRoadType: RoadTypes
    # routeRoadType: RoadTypes
    # transportType: TransportType
    defaultVehicleInterval: float
    defaultUnbunchingFactor: float
    stopDuration: float
    passengerTransport: bool
    cargoTransport: bool
    # pathfindPrefab: PathfindPrefab
    # vehicleNotification: NotificationIconPrefab


class Unlockable(CS2Asset):
    requireAll: List[Requirement]
    requireAny: List[Requirement]
    ignoreDependencies: bool

    def format(self) -> str:
        formatter = CS2WikiTextFormatter()
        result = []
        formatted_requirements = {}
        for heading, requirements in {'All of:': self.requireAll, 'One of:': self.requireAny}.items():
            formatted_requirements[heading] = []
            for req in requirements:
                if isinstance(req, Requirement):
                    formatted_requirements[heading].extend(req.format())
                elif isinstance(req, NamedAsset):
                    formatted_requirements[heading].append(req.display_name)
                elif req.cs2_class.startswith('Game.Prefabs.Tutorial'):
                    pass  # ignore tutorial requirements
                else:
                    error_msg = f'formatting of requirement type {type(req)} is not supported'
                    print(error_msg)
                    formatted_requirements[heading].append(req.name)
                    # raise NotImplementedError(error_msg)

        if sum([len(reqs) for reqs in formatted_requirements.values()]) > 1:
            for heading, requirements in formatted_requirements.items():
                if len(requirements) > 0:
                    result.append(heading)
                    result.append(formatter.create_wiki_list(requirements))
        else:
            for heading, requirements in formatted_requirements.items():
                # the previous if makes sure that there is only one entry in one of the lists
                result.extend(requirements)
        return '\n'.join(result)


class Theme(NamedAsset):
    name: str
    display_name = str
    assetPrefix: str

    extra_data_functions = {
        'display_name': lambda data: cs2game.parser.localizer.localize('Assets', 'THEME', data['name'])
    }

    def get_wiki_icon(self, size: str = '') -> str:
        """assumes that it is in the icon template. Subclasses have to override this function if that's not the case"""
        if size:
            size = '|' + size
        return f'{{{{icon|{self.display_name}{size}}}}}'


class ThemeObject(CS2Asset):
    theme: Theme


class UIAssetCategory(NamedAsset):
    menu: 'UIAssetMenu'
    extra_data_functions = {
        'display_name': lambda data: cs2game.parser.localizer.localize('SubServices', 'NAME', data['name'])
    }


class UIAssetMenu(NamedAsset):
    extra_data_functions = {
        'display_name': lambda data: cs2game.parser.localizer.localize('Services', 'NAME', data['name'])
    }


class UIObject(CS2Asset):
    group: UIAssetCategory
    priority: int
    icon: str
    largeIcon: str
    isDebugObject: bool

    # fix wrong capitalization in some folder names
    transform_value_functions = {'icon': lambda icon: icon.replace('Media/game/Icons', 'Media/Game/Icons')}

    def get_icon_png(self, fallback_folder: Path, width=256) -> bytes | Path:
        """get the svg icon from the game files and convert it to png with inkscape.
        If there is no icon, return the Path to the file in the fallback_folder"""
        if self.icon:
            tmp_file = NamedTemporaryFile(delete=False, prefix='PyHelpersForPDXWiki_cs2', suffix='.png')
            filename = tmp_file.name
            tmp_file.close()
            folder = cs2game.game_path / 'Cities2_Data/StreamingAssets/~UI~/GameUI'
            svg_file = folder / self.icon
            if not svg_file.parent.exists():
                # 1.2 and later
                svg_file = cs2game.game_path / 'Cities2_Data/Content/Game/~UI~' / self.icon
            # fix filenames with wrong capitalization on case-sensitive file system
            if not svg_file.is_file():
                for file in svg_file.parent.iterdir():
                    if file.name.lower() == svg_file.name.lower():
                        svg_file = file
                        break
            convert_svg_to_png(svg_file, filename, width)
            with open(filename, 'rb') as tmp_file:
                return tmp_file.read()
        else:
            return fallback_folder / (self.parent_asset.name + '.png')


class Zone(NamedAsset, IconEntity):
    areaType: GameZonesAreaType
    office: bool
    # not implemented
    #color: Color
    #edge: Color

    @cached_property
    def icon(self):
        return f'Zone{self.name.replace(" ", "").removeprefix("EU")}.png'

    def get_wiki_filename_prefix(self) -> str:
        return 'Zone'

    def get_wiki_icon(self, size: str = '') -> str:
        return self.get_wiki_file_tag(size)

    def get_wiki_page_name(self) -> str:
        return 'Zoning'


class ZoneBuiltRequirement(Requirement):
    requiredTheme: Theme
    requiredZone: Zone
    requiredType: GameZonesAreaType
    minimumSquares: int
    minimumCount: int
    minimumLevel: int

    def format(self) -> List[str]:
        if self.requiredType:
            raise NotImplementedError('requiredType not implemented')
        if self.requiredTheme:
            raise NotImplementedError('requiredTheme not implemented')
        if self.minimumLevel > 1:
            level_str = f' Level {self.minimumLevel}:'
        else:
            level_str = ''
        results = []
        if self.minimumSquares > 0:
            results.append(f'{self.requiredZone.get_wiki_icon("40px")}{level_str} {self.minimumSquares:,} cells')
        if self.minimumCount > 0:
            results.append(f'{self.requiredZone.get_wiki_icon("40px")}{level_str} {self.minimumCount:,} buildings')
        return results


################################################
# Classes for attributes with special handling #
################################################

class Effect:
    type: CityModifierType | LocalModifierType
    mode: ModifierValueMode
    delta: int

    def __init__(self, attributes):
        for key, value in attributes.items():
            setattr(self, convert_cs_member_name_to_python_attribute(key), value)
        self.mode = ModifierValueMode(self.mode)

    def get_formatted_delta(self):
        formatter = CS2WikiTextFormatter()
        if self.mode == ModifierValueMode.Relative:
            result = f'{{{{green|{formatter.format_percent(self.delta, add_plus_minus=True)}}}}}'
        elif self.type in [CityModifierType.CrimeAccumulation, CityModifierType.LoanInterest]:
            # for some reason they get a percentage, but the value is not multiplied by 100
            result = f'{{{{green|{formatter.add_plus_minus(self.delta)}%}}}}'
        elif self.mode == ModifierValueMode.Absolute:
            result = f'{{{{green|{formatter.add_plus_minus(self.delta)}}}}}'
        elif self.mode == ModifierValueMode.InverseRelative:
            raise NotImplemented('InverseRelative not supported')
        return f'{{{{icon|{self.type.display_name}}}}} {result}'


class CityEffect(Effect):

    def __init__(self, attributes):
        super().__init__(attributes)
        self.type = CityModifierType(self.type)

    @cached_property
    def description(self):
        desc = cs2game.localizer.localize('Properties', 'CITY_MODIFIER_EFFECT')
        return desc.format(DELTA=self.get_formatted_delta(), TYPE=self.type.display_name)


class LocalEffect(Effect):
    radiusCombineMode: int
    radius: int

    def __init__(self, attributes):
        super().__init__(attributes)
        self.type = LocalModifierType(self.type)

    @cached_property
    def description(self):
        formatter = CS2WikiTextFormatter()
        desc = cs2game.localizer.localize('Properties', 'LOCAL_MODIFIER_EFFECT')
        return desc.format(DELTA=self.get_formatted_delta(),
                           TYPE=self.type.display_name,
                           RADIUS=formatter.distance(self.radius))


class CityEffects(CS2Asset):
    effects: List[CityEffect]

    def __init__(self, cs2_class: str, file_name: str, path_id: int, parent: CS2Asset = None):
        self.transform_value_functions = {'effects': self.create_effect_objects}
        super().__init__(cs2_class, file_name, path_id, parent)

    @staticmethod
    def create_effect_objects(effects):
        return [CityEffect(attributes) for attributes in effects]


class LocalEffects(CS2Asset):
    effects: List[LocalEffect]

    def __init__(self, cs2_class: str, file_name: str, path_id: int, parent: CS2Asset = None):
        self.transform_value_functions = {'effects': self.create_effect_objects}
        super().__init__(cs2_class, file_name, path_id, parent)

    @staticmethod
    def create_effect_objects(effects):
        return [LocalEffect(attributes) for attributes in effects]


class CitizenRequirement(Requirement):
    minimumPopulation: int
    minimumHappiness: int

    def format(self) -> List[str]:
        results = []
        if self.minimumPopulation > 0:
            results.append(f'{{{{icon|population}}}} {self.minimumPopulation:,}')
        if self.minimumHappiness > 0:
            results.append(f'{{{{icon|happiness}}}} {self.minimumHappiness}%')
        return results


class CargoTransportStation(CS2Asset):
    tradedResources: List[ResourceInEditor]
    # fuels. seem to always be 1
    # carRefuelTypes: EnergyTypes
    # trainRefuelTypes: EnergyTypes
    # watercraftRefuelTypes: EnergyTypes
    # aircraftRefuelTypes: EnergyTypes
    loadingFactor: float
    # min/mx ticks between transports?
    # transportInterval: int2
    transports: int


class CityServiceBuilding(CS2Asset):
    upkeeps: List['ResourceUpkeep']

    transform_value_functions = {'upkeeps': lambda upkeeps: [ResourceUpkeep(
        ResourceInEditor(upkeep['m_Resources']['m_Resource']),
        upkeep['m_Resources']['m_Amount'],
        upkeep['m_ScaleWithUsage'])
        for upkeep in upkeeps]}

    def format_upkeeps(self) -> List[str]:
        return [upkeep.format() for upkeep in self.upkeeps]


class DefaultPolicies(CS2Asset):
    policies: List[Dict[str, Any]]

    def format(self):
        return [f"{cs2game.localizer.localize('Policy', 'TITLE', p['m_Policy'].name)}: {p['m_Policy'].sliderDefault}" for p in self.policies]


class ResourceStackInEditor:
    def __init__(self, resource: ResourceInEditor, amount: int):
        self.resource = resource
        self.amount = amount

    def format(self) -> str:
        if self.resource == ResourceInEditor.NoResource:
            return ''
        else:
            return f'{self.resource.display_name}: {self.amount}'


class InitialResources(CS2Asset):
    initialResources: List[ResourceStackInEditor]

    transform_value_functions = {'initialResources': lambda initialResources: [
        ResourceStackInEditor(ResourceInEditor(res['m_Value']['m_Resource']), res['m_Value']['m_Amount']) for res in
        initialResources]}

    def format(self) -> List[str]:
        return [resource.format() for resource in self.initialResources]


class LeisureProvider(CS2Asset):
    efficiency: int
    resources: ResourceInEditor
    leisureType: LeisureType

    def format(self):
        formatter = CS2WikiTextFormatter()
        return f'{formatter.add_red_green(self.efficiency, add_plus=True)} {self.leisureType.display_name}'

class MaintenanceDepot(CS2Asset):
    maintenanceType: List[MaintenanceType]
    vehicleCapacity: int
    vehicleEfficiency: float


class Feature(Requirement):
    """ can explicitly be unlocked by milestones
    not really relevant for signature buildings, because they are unlocked by early milestones which are never
    higher than their zoning requirements"""

    name: str

    def format(self) -> List[str]:
        return []


class ObjectBuiltRequirement(Requirement):
    name: str
    minimumCount: int

    def format(self) -> List[str]:
        buildings = [building.display_name for building in cs2game.parser.on_build_unlocks[self.name]]
        return [f'{self.minimumCount} {" / ".join(buildings)}']


class ProcessingRequirement(Requirement):
    resourceType: ResourceInEditor
    minimumProducedAmount: int

    def format(self) -> List[str]:
        return [f'{self.minimumProducedAmount:,} {self.resourceType.display_name} goods produced']


class PoliceStation(CS2Asset):
    patrolCarCapacity: int
    policeHelicopterCapacity: int
    jailCapacity: int
    bla: List[Dict[str, Any]]
    purposes: List[PolicePurpose]


class ResourceProductionInfo:
    def __init__(self, resource: ResourceInEditor, productionRate: int, storageCapacity: int):
        self.resource = resource
        self.productionRate = productionRate
        self.storageCapacity = storageCapacity

    def format(self):
        return f'{self.resource.display_name} (Rate: {self.productionRate}, Storage: {self.storageCapacity}'


class ResourceProducer(CS2Asset):
    resources: List[ResourceProductionInfo]

    transform_value_functions = {'resources': lambda resources: [
        ResourceProductionInfo(ResourceInEditor(resource['m_Resource']), resource['m_ProductionRate'], resource['m_StorageCapacity']) for
        resource in resources]}

    def format(self):
        return [resource.format() for resource in self.resources]


class ResourceUpkeep:

    def __init__(self, resource: ResourceInEditor, amount: int, scaleWithUsage: bool):
        self.resource = resource
        self.amount = amount
        self.scaleWithUsage = scaleWithUsage

    def format(self) -> str:
        if self.scaleWithUsage:
            refs = '<ref name=scaleswithusage>Scales with usage</ref>'
        else:
            refs = ''
        return f'{{{{icon|{self.resource.display_name}}}}} {self.amount} {self.resource.display_name}{refs}'


class School(CS2Asset):
    studentCapacity: int
    level: SchoolLevel
    graduationModifier: float


class Service(NamedAsset):
    cityResources: List[PlayerResource]
    service: CityService

    localization_category = 'Services'


class TransportDepot(CS2Asset):
    transportType: TransportType
    energyTypes: EnergyTypes
    vehicleCapacity: int
    productionDuration: float
    maintenanceDuration: float
    dispatchCenter: bool


class TransportStation(CS2Asset):
    carRefuelTypes: EnergyTypes
    trainRefuelTypes: EnergyTypes
    watercraftRefuelTypes: EnergyTypes
    aircraftRefuelTypes: EnergyTypes
    comfortFactor: float


class UpkeepModifierInfo:
    def __init__(self, resource: ResourceInEditor, multiplier: float):
        self.resource = resource
        self.multiplier = multiplier

    def format(self) -> str:
        if self.resource == ResourceInEditor.NoResource:
            return ''
        else:
            formatter = CS2WikiTextFormatter()
            return f'{{{{icon|{self.resource.display_name}}}}} {self.resource.display_name}: ×{formatter.format_percent(self.multiplier)}'


class UpkeepModifier(CS2Asset):
    modifiers: List[UpkeepModifierInfo]

    transform_value_functions = {'modifiers': lambda modifiers: [
        UpkeepModifierInfo(ResourceInEditor(modifier['m_Resource']), modifier['m_Multiplier']) for modifier in
        modifiers]}

    def format(self) -> List[str]:
        return [modifier.format() for modifier in self.modifiers]


class ElectricityConnection(CS2Asset):
    voltage: Voltage
    direction: int  # actually FlowDirection, but it seems to always be 3 == Both
    capacity: int
    requireAll: List[NetPieceRequirements]
    requireAny: List[NetPieceRequirements]
    requireNone: List[NetPieceRequirements]


    def format_capacity(self):
        formatter = CS2WikiTextFormatter()
        return formatter.format_big_number(self.capacity * 100, ["KW", "MW", "GW"])


class WaterPipeConnection(CS2Asset):
    freshCapacity: int
    sewageCapacity: int
    stormCapacity: int

    def has_water_pipe(self) -> bool:
        return self.freshCapacity > 0

    def has_sewage_pipe(self) -> bool:
        return self.sewageCapacity > 0

    def has_combined_pipe(self) -> bool:
        return self.has_water_pipe() and self.has_sewage_pipe()


class WaterPumpingStation(CS2Asset):
    capacity: int
    purification: float
    allowedWaterTypes: List[AllowedWaterTypes]


class Workplace(CS2Asset):
    workplaces: int
    complexity: WorkplaceComplexity
    eveningShiftProbability: float
    nightShiftProbability: float


    def get_highest_needed_education(self) -> CitizenEducationLevel:
        return CitizenEducationLevel(self.complexity.value + 1)


#####################
# Non-Asset classes #
#####################

class Map(NamedAsset):
    localization_category = 'Maps'
    localization_sub_category_display_name = 'MAP_TITLE'
    localization_sub_category_description = 'MAP_DESCRIPTION'

    displayName: str
    thumbnail: str  # seems to be a hash which identifies the file
    preview: str  # seems to be a hash which identifies the file
    theme: str
    temperatureRange: Dict[str, float]
    cloudiness: float
    precipitation: float
    latitude: float
    longitude: float
    buildableLand: int
    area: int
    waterAvailability: int  # seems to always be 0
    resources: Dict[str, int]
    connections: Dict[str, bool]
    contentPrerequisite: List[DLC]
    nameAsCityName: bool  # always False
    startingYear: int   # always -1
    mapData: str  # hash which points to .cdm file
    sessionGuid: str  # seems to always be a bunch of 0's

    transform_value_functions = {'contentPrerequisite': lambda reqs: [DLC[req] for req in reqs if req] if reqs else [DLC.BaseGame]}

    def format_connection_icons(self) -> List[str]:
        icon_map = {
            "road": 'highway connections',
            "train": 'rail connections',
            "air": 'airplane connections',
            "ship": 'ship connections',
            "electricity": 'electricity connections',
            "water": 'water connections',
        }
        return [f'{{{{icon|{icon_map[connection]}}}}}' for connection, active in self.connections.items() if active]
