import re
import shutil
from functools import cached_property
from pathlib import Path
from typing import Callable, TypeVar, Type, Dict

from UnityPy.classes.Object import NodeHelper

from cs2.localization import CS2Localization
from cs2.cs2lib import *
from cs2.unity_reader import MonoBehaviourReader

CS2_ASSET = TypeVar('CS2_ASSET', bound=CS2Asset)


class CS2Parser:

    # maps CS2 classes to classes from the cs2lib package. This is only needed for top-level Assets or components in
    # which the name does not match the class
    class_map = {
    }

    def __init__(self):
        self.parsed_assets = {}
        self.unparsed_classes = set()

    @cached_property
    def localizer(self) -> CS2Localization:
        return cs2game.localizer

    @cached_property
    def mono_behaviour_reader(self) -> MonoBehaviourReader:
        return MonoBehaviourReader(cs2game.game_path / 'Cities2_Data')

    def read_gameplay_assets(self, toplevel_classes: List[str] = [
        'Game.Prefabs.BuildingPrefab',
        'Game.Prefabs.BuildingExtensionPrefab', # building upgrades
        'Game.Prefabs.FencePrefab',             # road signs and road upgrades
        'Game.Prefabs.PathwayPrefab',           # pathways
        'Game.Prefabs.PowerLinePrefab',
        'Game.Prefabs.RoadPrefab',              # roads
        'Game.Prefabs.TrackPrefab',             # tracks
        'Game.Prefabs.TransportLinePrefab',     # line tools
        'Game.Prefabs.StaticObjectPrefab',      # ploppable assets like vegatation and traffic stops
        'Game.Prefabs.AssetStampPrefab',        # intersections
    ]):
        """Reads assets with the type MonoBehaviour. These can then be accessed via self.parsed_assets

        Args:
            toplevel_classes:  read only assets which use one of the C# classes in this list
         """
        all_objects = []
        parsed_objs = []

        for obj in self.mono_behaviour_reader.env.objects:
            if obj.type.name == 'MonoBehaviour':
                cls = self.mono_behaviour_reader.get_cls(obj)
                if cls in toplevel_classes:
                    nodes = self.mono_behaviour_reader.parse_monobehaviour(obj)
                    self.mono_behaviour_reader.remove_unimportant(nodes)
                    self.mono_behaviour_reader.inline_components_recursive(nodes)
                    all_objects.append(nodes)
                    parsed_objs.append(self.parse_asset(nodes))

    def _get_all_subclasses(self, cls):
        return set(cls.__subclasses__()).union(
            [s for c in cls.__subclasses__() for s in self._get_all_subclasses(c)])

    @cached_property
    def asset_classes(self) -> Dict[str, Type[CS2Asset]]:
        return {cls.__name__: cls for cls in self._get_all_subclasses(CS2Asset)}

    def determine_cs2lib_class(self, nodes: NodeHelper) -> Type[CS2Asset] | None:
        if nodes.cs2_class in self.class_map:
            return self.class_map[nodes.cs2_class]
        elif nodes.m_Name in self.asset_classes:
            return self.asset_classes[nodes.m_Name]
        elif nodes.cs2_class.removeprefix('Game.Prefabs.') in self.asset_classes:
            return self.asset_classes[nodes.cs2_class.removeprefix('Game.Prefabs.')]
        elif nodes.cs2_class.removeprefix('Game.Prefabs.').removesuffix('Prefab') in self.asset_classes:
            return self.asset_classes[nodes.cs2_class.removeprefix('Game.Prefabs.').removesuffix('Prefab')]
        else:
            return None

    def parse_asset(self, nodes: NodeHelper, parent: CS2_ASSET = None) -> CS2_ASSET:
        if not hasattr(nodes, 'file_name'):
            return nodes.to_dict()
        asset_id = CS2Asset.calculate_id(nodes.file_name, nodes.path_id)
        if asset_id in self.parsed_assets:
            return self.parsed_assets[asset_id]

        # first create a basic object so that it can be referenced in case of circular dependencies
        cls = self.determine_cs2lib_class(nodes)
        if cls is None:
            self.unparsed_classes.add(nodes.cs2_class)
            cls = GenericAsset
        asset = cls(nodes.cs2_class, nodes.file_name, nodes.path_id, parent)
        self.parsed_assets[asset_id] = asset

        asset_attributes = {}
        class_attributes = cls.all_annotations()
        for key, value in nodes.items():
            if isinstance(value, str) and (value.startswith('Ignored object of class') or value.startswith('Ignored asset of type')):
                continue
            if isinstance(value, NodeHelper):
                if key.startswith('m_'):
                    key = convert_cs_member_name_to_python_attribute(key)
                asset_attributes[key] = self.parse_asset(value, parent=asset)
            else:  # these are only added if there is a class attribute for them
                if isinstance(value, list):
                    value = [self.parse_asset(element, parent=asset) if isinstance(element, NodeHelper)
                             else element
                             for element in value]
                elif not isinstance(value, int) and not isinstance(value, str) and not isinstance(value, float) and value is not None:
                    raise Exception(f'attribute of type {type(value)} not implemented. Key is {key} in object of type {cls}')

                if cls == GenericAsset:
                    asset_attributes[convert_cs_member_name_to_python_attribute(key)] = value
                else:
                    # Assets which have their own class, specify which attributes they need/support
                    for possible_name in [key, convert_cs_member_name_to_python_attribute(key)]:
                        if possible_name in class_attributes:
                            asset_attributes[possible_name] = value

        asset.add_attributes(asset_attributes)

        return asset

    def generate_code_for_unparsed_classes(self, code_folder: Path):
        """code_folder contains the c# code. It can be extracted by assetrippers"""
        type_map = {
            'string': 'str',
        }
        for cls in self.unparsed_classes:
            cls_name = cls.split('.')[-1]
            members = {}
            with open(code_folder / 'Game' / (cls.replace('.', '/') + '.cs'), 'r') as code_file:
                for match in re.finditer(r'^\s*public\s*(?P<type>[^\s]+)\s*(?P<name>m_[^\s;]+)', code_file.read(), flags=re.MULTILINE):
                    typ = match.group('type')
                    if typ in type_map:
                        typ = type_map[typ]
                    members[convert_cs_member_name_to_python_attribute(match.group('name'))] = typ
            print(f'class {cls_name}(CS2Asset):')
            for name, typ in members.items():
                print(f'    {name}: {typ}')
            print()
            print()

    @cached_property
    def landmarks(self) -> Dict[str, CS2_ASSET]:
        if len(self.parsed_assets) == 0:
            self.read_gameplay_assets()

        return {asset.name: asset for asset in self.parsed_assets.values() if
                hasattr(asset, 'UIObject') and
                asset.UIObject.group and
                asset.UIObject.group.name == 'SignaturesLandmarks'}

    @cached_property
    def landscaping(self) -> Dict[str, CS2_ASSET]:
        if len(self.parsed_assets) == 0:
            self.read_gameplay_assets()

        return {asset.name: asset for asset in self.parsed_assets.values() if
                hasattr(asset, 'UIObject') and
                asset.UIObject.group and
                hasattr(asset.UIObject.group, 'menu')
                and asset.UIObject.group.menu.name == 'Landscaping'}

    @cached_property
    def roads(self) -> Dict[str, CS2_ASSET]:
        if len(self.parsed_assets) == 0:
            self.read_gameplay_assets()

        return {asset.name: asset for asset in self.parsed_assets.values() if
                hasattr(asset, 'UIObject') and
                asset.UIObject.group and
                hasattr(asset.UIObject.group, 'menu')
                and asset.UIObject.group.menu.name == 'Roads'}

    @cached_property
    def service_buildings(self) -> Dict[str, CS2_ASSET]:
        if len(self.parsed_assets) == 0:
            self.read_gameplay_assets()
        return {asset.name: asset for asset in self.parsed_assets.values()
                if isinstance(asset, Building)
                and hasattr(asset, 'CityServiceBuilding')
                and not hasattr(asset, 'SignatureBuilding')
                and not hasattr(asset, 'ServiceUpgrade')
                # somehow HydroelectricPowerPlant01 doesnt have an UIObject
                and (not hasattr(asset, 'UIObject') or asset.UIObject.group.name != 'SignaturesLandmarks')
                }

    @cached_property
    def service_building_upgrades(self) -> Dict[str, CS2_ASSET]:
        if len(self.parsed_assets) == 0:
            self.read_gameplay_assets()
        return {asset.name: asset for asset in self.parsed_assets.values()
                if hasattr(asset, 'ServiceUpgrade')
                }

    @cached_property
    def signature_buildings(self) -> Dict[str, CS2_ASSET]:
        if len(self.parsed_assets) == 0:
            self.read_gameplay_assets()
        return {asset.name: asset for asset in self.parsed_assets.values() if hasattr(asset, 'SignatureBuilding')}

    @cached_property
    def transportation(self) -> Dict[str, CS2_ASSET]:
        if len(self.parsed_assets) == 0:
            self.read_gameplay_assets()

        return {asset.name: asset for asset in self.parsed_assets.values() if
                hasattr(asset, 'UIObject') and
                asset.UIObject.group and
                hasattr(asset.UIObject.group, 'menu')
                and asset.UIObject.group.menu.name == 'Transportation'}

    @cached_property
    def vegetations(self) -> Dict[str, CS2_ASSET]:
        if len(self.parsed_assets) == 0:
            self.read_gameplay_assets()
        return {asset.name: asset for asset in self.parsed_assets.values() if hasattr(asset, 'UIObject') and asset.UIObject.group and asset.UIObject.group.name == 'Vegetation'}

    @cached_property
    def on_build_unlocks(self) -> Dict[str, List[CS2_ASSET]]:
        on_build_unlocks = {}
        for asset in self.parsed_assets.values():
            if hasattr(asset, 'UnlockOnBuild'):
                for unlock in asset.UnlockOnBuild.unlocks:
                    if unlock.name not in on_build_unlocks:
                        on_build_unlocks[unlock.name] = []
                    on_build_unlocks[unlock.name].append(asset)
        return on_build_unlocks

    def write_icons(self, assets: List[CS2Asset], prefix: str, destination_folder: Path, fallback_folder: Path, move_fallbacks=False):
        """Helper to write icons from the streamingassests and a fallback folder to a destination folder
        the icons will be named by the display name of the asset"""
        icon_overrides = {
            'FerrisWheel01': 'LondonEye',
            'CoalPowerPlant01 Additional Turbine Building': 'CoalPowerPlant01 Additional Turbine Building',
            'EmergencyBatteryStation01 Diesel Generator': 'EmergencyBatteryStation01 Diesel Generator',
            'Prison01 Extra Wing': 'Prison01 Extra Workshops',
            'Prison01 Prison Library': 'Prison01 Maximum Security Wing',
        }
        if prefix and not prefix.endswith(' '):
            prefix += ' '
        for asset in assets:
            try:
                destination_file = destination_folder / (prefix + asset.display_name + '.png')
                if asset.name in icon_overrides:
                    icon = fallback_folder / ( icon_overrides[asset.name] + '.png')
                else:
                    icon = asset.UIObject.get_icon_png(fallback_folder)
                if isinstance(icon, Path):
                    if move_fallbacks:
                        shutil.move(icon, destination_file)
                    else:
                        shutil.copy(icon, destination_file)
                else:
                    with open(destination_file, 'wb') as f:
                        f.write(icon)
            except Exception as e:
                if not hasattr(asset, 'display_name'):
                    print(f'no display name in {asset.name} {asset.cs2_class}')
                else:
                    print(f'Error writing icon for "{asset.name}"/"{asset.display_name}:')
                print(e)
