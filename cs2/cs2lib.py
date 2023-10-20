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

    @cached_property
    def description(self):
        return cs2game.localizer.localize('Assets', 'DESCRIPTION',
                                          self.name)

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

    @cached_property
    def dlc(self) -> DLC:
        if hasattr(self, 'ContentPrerequisite'):
            return DLC(self.ContentPrerequisite.contentPrerequisite.DLC_Requirement.dlc['id'])
        else:
            return DLC(-1)


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

