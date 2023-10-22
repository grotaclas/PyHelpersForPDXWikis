import inspect
import subprocess
from collections import ChainMap
from enum import Enum
from functools import cached_property
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import List, Dict, Callable

from common.paradox_lib import IconEntity
from cs2.game import cs2game
from cs2.text_formatter import CS2WikiTextFormatter


def convert_cs_member_name_to_python_attribute(s: str):
    """ remove the prefix m_ and lowercase the first letter"""
    s = s.removeprefix('m_')
    return s[0].lower() + s[1:]


################
# Base classes #
################

class CS2Asset:
    cs2_class: str
    parent_asset: 'CS2Asset'

    # filename and path id together should be unique
    file_name: str
    path_id: int

    transform_value_functions: dict[str, Callable[[any], any]] = {}
    """ the functions in this dict are called with the value of the data which matches
           the key of this dict. If the key is not present in the data, the function won't
           be called. The function must return the new value for the data"""
    extra_data_functions: dict[str, Callable[[Dict[str, any]], any]] = {}
    """ extra_data_functions: create extra entries in the data. For each key in this dict, the corresponding function
          will be called with the name of the entity and the data dict as parameter. The return
          value will be added to the data dict under the same key"""

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

    def add_attributes(self, attributes: Dict[str, any]):
        for key, value in attributes.items():
            if key in self.transform_value_functions:
                value = self.transform_value_functions[key](value)
            setattr(self, key, value)
        for key, f in self.extra_data_functions.items():
            setattr(self, key, f(attributes))

    @classmethod
    def all_annotations(cls) -> ChainMap:
        """Returns a dictionary-like ChainMap that includes annotations for all
           attributes defined in cls or inherited from superclasses."""
        return ChainMap(*(inspect.get_annotations(c) for c in cls.mro()))


class GenericAsset(CS2Asset):
    """An asset which doesn't implement any special handling"""
    pass


class NamedAsset(CS2Asset):
    name: str
    display_name: str

    def __init__(self, cs2_class: str, file_name: str, path_id: int, parent: CS2Asset = None):
        super().__init__(cs2_class, file_name, path_id, parent)
        if 'display_name' not in self.extra_data_functions:
            self.extra_data_functions = self.extra_data_functions.copy()  # copy to not modify the class attribute of the parent
            self.extra_data_functions['display_name'] = lambda data: cs2game.parser.localizer.localize('Assets', 'NAME', data['name'])

    def __str__(self):
        return self.display_name

    @cached_property
    def description(self):
        return cs2game.localizer.localize('Assets', 'DESCRIPTION',
                                          self.name)

    @cached_property
    def dlc(self) -> 'DLC':
        if hasattr(self, 'ContentPrerequisite'):
            return DLC(self.ContentPrerequisite.contentPrerequisite.DLC_Requirement.dlc['id'])
        else:
            return DLC(-1)

################
# Enum classes #
################

class AreaType(Enum):
    _None = 0       # it is None in C#, but python doesn't support this
    Residential = 1
    Commercial = 2
    Industrial = 3


class DLC(Enum):
    BaseGame = -1  # to simplify code
    LandmarkBuildings = 0
    SanFranciscoSet = 1
    CS1TreasureHunt = 2

    def __str__(self):
        return self.name

    @cached_property
    def display_name(self):
        """Hardcoded names, because I didnt find them anywhere in the files"""
        return {'BaseGame': '',
                'LandmarkBuildings': 'Landmark Buildings',
                'SanFranciscoSet': 'San Francisco Set',
                'CS1TreasureHunt': 'Treasure Hunt'
                }[self.name]


class ModifierValueMode(Enum):
    Relative = 0
    Absolute = 1
    InverseRelative = 2


class CityModifierType(Enum):
    Attractiveness = 0
    CrimeAccumulation = 1
    DisasterWarningTime = 3
    DisasterDamageRate = 4
    DiseaseProbability = 5
    ParkEntertainment = 6
    CriminalMonitorProbability = 7
    IndustrialAirPollution = 8
    IndustrialGroundPollution = 9
    IndustrialGarbage = 10
    RecoveryFailChange = 11
    OreResourceAmount = 12
    OilResourceAmount = 13
    UniversityInterest = 14
    OfficeSoftwareDemand = 15
    IndustrialElectronicsDemand = 16
    OfficeSoftwareEfficiency = 17
    IndustrialElectronicsEfficiency = 18
    TelecomCapacity = 19
    Entertainment = 20
    HighwayTrafficSafety = 21
    PrisonTime = 22
    CrimeProbability = 23
    CollegeGraduation = 24
    UniversityGraduation = 25
    ImportCost = 26
    LoanInterest = 27
    BuildingLevelingCost = 28
    ExportCost = 29
    TaxiStartingFee = 30
    IndustrialEfficiency = 31
    OfficeEfficiency = 32
    PollutionHealthAffect = 33
    HospitalEfficiency = 34

    @cached_property
    def display_name(self) -> str:
        return cs2game.localizer.localize('Properties', 'CITY_MODIFIER', self.name)


class LocalModifierType(Enum):
    CrimeAccumulation = 0
    ForestFireResponseTime = 1
    ForestFireHazard = 2
    Wellbeing = 3
    Health = 4

    @cached_property
    def display_name(self) -> str:
        return cs2game.localizer.localize('Properties', 'LOCAL_MODIFIER', self.name)


class NetPieceLayer(Enum):
    Surface = 0
    Bottom = 1
    Top = 2
    Side = 3


class NetPieceRequirements(Enum):
    Node = 0
    Intersection = 1
    DeadEnd = 2
    Crosswalk = 3
    BusStop = 4
    Median = 5
    TrainStop = 6
    OppositeTrainStop = 7
    Inverted = 8
    TaxiStand = 9
    LevelCrossing = 10
    Elevated = 11
    Tunnel = 12
    Raised = 13
    Lowered = 14
    LowTransition = 15
    HighTransition = 16
    WideMedian = 17
    TramTrack = 18
    TramStop = 19
    OppositeTramTrack = 20
    OppositeTramStop = 21
    MedianBreak = 22
    ShipStop = 23
    Sidewalk = 24
    Edge = 25
    SubwayStop = 26
    OppositeSubwayStop = 27
    MiddlePlatform = 28
    Underground = 29
    Roundabout = 30
    OppositeSidewalk = 31
    SoundBarrier = 32
    Overhead = 33
    TrafficLights = 34
    PublicTransportLane = 35
    OppositePublicTransportLane = 36
    Spillway = 37
    MiddleGrass = 38
    MiddleTrees = 39
    WideSidewalk = 40
    SideGrass = 41
    SideTrees = 42
    OppositeGrass = 43
    OppositeTrees = 44
    Opening = 45
    Front = 46
    Back = 47
    Flipped = 48
    RemoveTrafficLights = 49
    AllWayStop = 50
    Pavement = 51
    Gravel = 52
    Tiles = 53
    ForbidLeftTurn = 54
    ForbidRightTurn = 55
    OppositeWideSidewalk = 56
    OppositeForbidLeftTurn = 57
    OppositeForbidRightTurn = 58
    OppositeSoundBarrier = 59
    SidePlatform = 60
    AddCrosswalk = 61
    RemoveCrosswalk = 62
    Lighting = 63
    OppositeBusStop = 64
    OppositeTaxiStand = 65
    OppositeRaised = 66
    OppositeLowered = 67
    OppositeLowTransition = 68
    OppositeHighTransition = 69
    OppositeShipStop = 70
    OppositePlatform = 71
    OppositeAddCrosswalk = 72
    OppositeRemoveCrosswalk = 73
    Inside = 74
    ForbidStraight = 75
    OppositeForbidStraight = 76


class ResourceInEditor(Enum):
    NoResource = 0
    Money = 1
    Grain = 2
    ConvenienceFood = 3
    Food = 4
    Vegetables = 5
    Meals = 6
    Wood = 7
    Timber = 8
    Paper = 9
    Furniture = 10
    Vehicles = 11
    Lodging = 12
    UnsortedMail = 13
    LocalMail = 14
    OutgoingMail = 15
    Oil = 16
    Petrochemicals = 17
    Ore = 18
    Plastics = 19
    Metals = 20
    Electronics = 21
    Software = 22
    Coal = 23
    Stone = 24
    Livestock = 25
    Cotton = 26
    Steel = 27
    Minerals = 28
    Concrete = 29
    Machinery = 30
    Chemicals = 31
    Pharmaceuticals = 32
    Beverages = 33
    Textiles = 34
    Telecom = 35
    Financial = 36
    Media = 37
    Entertainment = 38
    Recreation = 39
    Garbage = 40
    Count = 41

    @cached_property
    def display_name(self) -> str:
        return cs2game.localizer.localize('Resources', 'TITLE', self.name)


class TrafficSignType(Enum):
    _None = 0       # it is None in C#, but python doesn't support this
    Stop = 1
    Yield = 2
    NoTurnLeft = 3
    NoTurnRight = 4
    NoUTurnLeft = 5
    NoUTurnRight = 6
    DoNotEnter = 7
    Motorway = 8
    Oneway = 9
    SpeedLimit = 10
    Parking = 11
    Street = 12
    BusOnly = 13
    TaxiOnly = 14
    RoundaboutCounterclockwise = 15
    RoundaboutClockwise = 16
    Count = 17


class Voltage(Enum):
    Low = 0
    High = 1


#################
# Asset classes #
#################

class AssetStamp(NamedAsset):
    """used by intersections"""
    width: int
    depth: int
    constructionCost: int
    upKeepCost: int


class Building(NamedAsset):
    circular: bool
    lotWidth: int
    lotDepth: int

    @cached_property
    def size(self):
        return f'{self.lotWidth}×{self.lotDepth}'


    def get_effect_descriptions(self) -> List[str]:
        """List of formatted effect descriptions"""

        effects = []
        if hasattr(self, 'CityEffects'):
            for effect in self.CityEffects.effects:
                effects.append(effect.description)
        if hasattr(self, 'LocalEffects'):
            for effect in self.LocalEffects.effects:
                effects.append(effect.description)

        return effects



class BuildingExtension(NamedAsset):
    circular: bool
    externalLot: bool
    position: [float]
    overrideLotSize: [int]
    overrideHeight: float


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
                f' the european theme would be {int(self.speedLimit / 2)} km/h and {int(self.speedLimit / 2 / 1609344)} mph'
                f'for the north american theme</ref>')

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
        # print(f'{self.display_name} ======')
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
            # print(f"{piece['m_Piece'].name};all;{piece['m_RequireAll']};any;{piece['m_RequireAny']};layer;{piece['m_Piece'].layer};cost;{piece['m_Piece'].PlaceableNetPiece.constructionCost};upkeep;{piece['m_Piece'].PlaceableNetPiece.upkeepCost}")
            print(
                f"{piece['m_Piece'].name};{parent_section['m_RequireAll']};{parent_section['m_RequireAny']};{parent_section['m_RequireNone']};{section['m_RequireAll']};{section['m_RequireAny']};{section['m_RequireNone']};{piece['m_RequireAll']};{piece['m_RequireAny']};{piece['m_RequireNone']};{piece['m_Piece'].layer};{piece['m_Piece'].PlaceableNetPiece.constructionCost};{piece['m_Piece'].PlaceableNetPiece.upkeepCost};{piece['m_Piece'].PlaceableNetPiece.elevationCost}")

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
        filename = 'Signature building unlock ' + self.get_display_name() + '.png'
        return f'[[File:{filename}|{size}|{self.get_display_name()}]]'

    def get_name(self):
        return self.unlockEventImage.split('/')[-1].removesuffix('.png')

    def get_display_name(self):
        return cs2game.localizer.localize('Assets', 'NAME',
                                          self.get_name(), default=self.parent_asset.display_name)


class StaticObjectPrefab(NamedAsset):
    circular: bool


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
                formatted_requirements[heading].extend(req.format())

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
            svg_file = cs2game.game_path / 'Cities2_Data/StreamingAssets/~UI~/GameUI' / self.icon
            # fix filenames with wrong capitalization on case-sensitive file system
            if not svg_file.is_file():
                for file in svg_file.parent.iterdir():
                    if file.name.lower() == svg_file.name.lower():
                        svg_file = file
                        break
            subprocess.run(
                ['inkscape', svg_file,
                 '--export-type=png', f'--export-filename={filename}', f'--export-width={width}'])
            with open(filename, 'rb') as tmp_file:
                return tmp_file.read()
        else:
            return fallback_folder / (self.parent_asset.name + '.png')


class Zone(NamedAsset, IconEntity):
    areaType: AreaType
    office: bool
    # not implemented
    #color: Color
    #edge: Color

    transform_value_functions = {'areaType': lambda area_type: AreaType(area_type)}
    extra_data_functions = {'icon': lambda data: f'Zone{data["name"].replace(" ", "").removeprefix("EU")}.png'}

    def get_wiki_filename_prefix(self) -> str:
        return 'Zone'

    def get_wiki_icon(self, size: str = '') -> str:
        return self.get_wiki_file_tag(size)

    def get_wiki_page_name(self) -> str:
        return 'Zoning'


class ZoneBuiltRequirement(CS2Asset):
    requiredTheme: Theme
    requiredZone: Zone
    requiredType: AreaType
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
                           RADIUS=formatter.format_distance(self.radius))


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

    transform_value_functions = {'resourceType': lambda resourceType: ResourceInEditor(resourceType)}

    def format(self) -> List[str]:
        return [f'{self.minimumProducedAmount:,} {self.resourceType.display_name} goods produced']


class ElectricityConnection(CS2Asset):
    voltage: Voltage
    direction: int  # actually FlowDirection, but it seems to always be 3 == Both
    capacity: int
    requireAll: List[NetPieceRequirements]
    requireAny: List[NetPieceRequirements]
    requireNone: List[NetPieceRequirements]

    transform_value_functions = {'voltage': lambda voltage: Voltage(voltage),
                                 'requireAll': lambda reqs: [NetPieceRequirements(req) for req in reqs],
                                 'requireAny': lambda reqs: [NetPieceRequirements(req) for req in reqs],
                                 'requireNone': lambda reqs: [NetPieceRequirements(req) for req in reqs],
                                 }

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
