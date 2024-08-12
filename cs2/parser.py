import json
import re
import shutil
from enum import Enum
from typing import TypeVar, Type, Set

from UnityPy.classes.Object import NodeHelper

from common.cache import disk_cache
from cs2.localization import CS2Localization
from cs2.cs2lib import *
from cs2.unity_reader import MonoBehaviourReader

CS2_ASSET = TypeVar('CS2_ASSET', bound=CS2Asset)


class CS2Parser:

    # maps CS2 classes to classes from the cs2lib package. This is only needed for top-level Assets or components in
    # which the name does not match the class
    class_map = {
    }

    @cached_property
    def localizer(self) -> CS2Localization:
        return cs2game.localizer

    @cached_property
    def mono_behaviour_reader(self) -> MonoBehaviourReader:
        return MonoBehaviourReader(cs2game.game_path / 'Cities2_Data')

    @cached_property
    def parsed_assets(self) -> Dict[str, CS2Asset]:
        """a cached version of Assets which you get when calling read_gameplay_assets with default arguments
        the key of the dict is the asset id as calculated by CS2Asset.calculate_id()"""
        return self._cached_assets_and_unparsed_classes[0]

    @cached_property
    def unparsed_classes(self) -> Set[str]:
        return self._cached_assets_and_unparsed_classes[1]

    @cached_property
    @disk_cache(game=cs2game)
    def _cached_assets_and_unparsed_classes(self):
        return self.read_gameplay_assets()

    def read_gameplay_assets(self, toplevel_classes: List[str] = [
        'Game.Prefabs.AssetCollection',         # can be used to look stuff up
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
        'Game.Prefabs.SurfacePrefab',           # surface landscaping like grass
    ]):
        """Reads assets with the type MonoBehaviour. These can then be accessed via self.parsed_assets

        Args:
            toplevel_classes:  read only assets which use one of the C# classes in this list
         """
        parsed_assets = {}
        unparsed_classes = set()

        for obj in self.mono_behaviour_reader.env.objects:
            if obj.type.name == 'MonoBehaviour':
                cls = self.mono_behaviour_reader.get_cls(obj)
                if cls in toplevel_classes:
                    nodes = self.mono_behaviour_reader.parse_monobehaviour(obj)
                    if hasattr(nodes, 'm_Name') and nodes.m_Name in ['BusDepotTutorial', 'TutorialsCollection']:
                        # cant be parsed
                        continue
                    self.mono_behaviour_reader.remove_unimportant(nodes)
                    self.mono_behaviour_reader.inline_components_recursive(nodes)
                    self.parse_asset(nodes, parsed_assets, unparsed_classes)
        return parsed_assets, unparsed_classes

    def _get_all_subclasses(self, cls):
        return set(cls.__subclasses__()).union(
            [s for c in cls.__subclasses__() for s in self._get_all_subclasses(c)])

    @cached_property
    def asset_classes(self) -> Dict[str, Type[CS2Asset]]:
        return {cls.__name__: cls for cls in self._get_all_subclasses(CS2Asset)}

    def determine_cs2lib_class(self, nodes: NodeHelper) -> Type[CS2Asset] | None:
        if nodes.cs2_class in self.class_map:
            return self.class_map[nodes.cs2_class]
        elif nodes.cs2_class.removeprefix('Game.Prefabs.') in self.asset_classes:
            return self.asset_classes[nodes.cs2_class.removeprefix('Game.Prefabs.')]
        elif nodes.cs2_class.removeprefix('Game.Prefabs.').removesuffix('Prefab') in self.asset_classes:
            return self.asset_classes[nodes.cs2_class.removeprefix('Game.Prefabs.').removesuffix('Prefab')]
        elif nodes.m_Name in self.asset_classes:
            return self.asset_classes[nodes.m_Name]
        else:
            return None

    def parse_dict(self, nodes: NodeHelper, parsed_assets: Dict[str, CS2_ASSET], unparsed_classes: Set[str]) -> Dict:
        result = {}
        for key, value in nodes.items():
            if isinstance(value, NodeHelper):
                result[key] = self.parse_asset(nodes[key], parsed_assets, unparsed_classes)
            elif isinstance(value, list):
                result[key] = [self.parse_asset(element, parsed_assets, unparsed_classes) if isinstance(element, NodeHelper)
                               else element
                               for element in value]
            elif isinstance(value, float):
                # round numbers to avoid floating point issues like 0.6000000238418579
                result[key] = round(value, 6)
            elif isinstance(value, int) or isinstance(value, str) or value is None:
                result[key] = value
            else:
                raise Exception(
                    f'attribute of type {type(value)} not implemented. Key is {key} in parse_dict')

        return result

    def parse_asset(self, nodes: NodeHelper, parsed_assets: Dict[str, CS2_ASSET], unparsed_classes: Set[str], parent: CS2_ASSET = None) -> CS2_ASSET | Dict:
        if not hasattr(nodes, 'file_name'):
            return self.parse_dict(nodes, parsed_assets, unparsed_classes)
        asset_id = CS2Asset.calculate_id(nodes.file_name, nodes.path_id)
        if asset_id in parsed_assets:
            return parsed_assets[asset_id]

        # first create a basic object so that it can be referenced in case of circular dependencies
        cls = self.determine_cs2lib_class(nodes)
        if cls is None:
            unparsed_classes.add(nodes.cs2_class)
            cls = GenericAsset
        asset = cls(nodes.cs2_class, nodes.file_name, nodes.path_id, parent)
        parsed_assets[asset_id] = asset

        if hasattr(nodes, 'm_Name'):
            asset.name = nodes.m_Name
        asset_attributes = {}
        class_attributes = cls.all_annotations()
        for key, value in nodes.items():
            if isinstance(value, str) and (value.startswith('Ignored object of class') or value.startswith('Ignored asset of type')):
                continue
            if isinstance(value, NodeHelper):
                if key.startswith('m_'):
                    key = convert_cs_member_name_to_python_attribute(key)
                asset_attributes[key] = self.parse_asset(value, parsed_assets, unparsed_classes, parent=asset)
            else:  # these are only added if there is a class attribute for them
                if isinstance(value, list):
                    value = [self.parse_asset(element, parsed_assets, unparsed_classes, parent=asset) if isinstance(element, NodeHelper)
                             else self.parse_dict(element, parsed_assets, unparsed_classes) if isinstance(element, dict)
                             else element
                             for element in value]
                elif isinstance(value, float):
                    # round numbers to avoid floating point issues like 0.6000000238418579
                    value = round(value, 6)
                elif not isinstance(value, int) and not isinstance(value, str) and value is not None:
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

    def generate_code_for_enums(self, code_folder: Path) -> List[str]:
        enum_classes = {cls.__name__: cls for cls in self._get_all_subclasses(Enum)}
        enum_re = re.compile(r'public enum (?P<name>[a-zA-Z_0-9]*).*?\{\s*\n(?P<members>[^}]*)}', flags=re.DOTALL)
        namespace_re = re.compile(r'^namespace (?P<name>[a-zA-Z_0-9.]*)', flags=re.MULTILINE)
        member_re = re.compile(r'^\s*(?P<name>[a-zA-Z_0-9]*)\s*=\s*(?P<value>-?((0x[0-9a-fA-F]+)|([0-9]+)|[a-z]+\.MaxValue))(?P<suffix>[a-zA-Z]*)\s*,?\s*')
        generated_classes = {}
        for code_file_path in (code_folder / 'Game' / 'Game').rglob('*.cs'):
            with open(code_file_path) as code_file:
                code = code_file.read()
                enum_match = enum_re.search(code)
                if enum_match:
                    name = enum_match.group('name')
                    namespace = namespace_re.search(code).group('name')
                    cs2_class = f'{namespace}.{name}'

                    if '[Flags]' in code:
                        parent_class = 'CS2BaseFlag'
                    else:
                        parent_class = 'CS2BaseEnum'
                    member_lines = []
                    for line in enum_match.group('members').split('\n'):
                        member_match = member_re.fullmatch(line)
                        if member_match:
                            value = member_match.group('value')
                            key = member_match.group('name')
                            comment = ''
                            if key == 'None':
                                key = '_None'
                                comment = " the name is None in C#, but python doesn't support this."
                            suffix = member_match.group('suffix')
                            if value == 'byte.MaxValue':
                                value = '255'
                                comment += ' the value is byte.MaxValue in C#'
                            elif value == 'uint.MaxValue':
                                value = '4294967295'
                                comment += ' the value is uint.MaxValue in C#'
                            elif value == 'ulong.MaxValue':
                                value = '18446744073709551615'
                                comment += ' the value is ulong.MaxValue in C#'
                            else:
                                pass
                            if comment:
                                comment = f'  #{comment}'
                            member_lines.append(f'    {key} = {value}{comment}')

                    if name not in generated_classes:
                        generated_classes[name] = []
                    generated_classes[name].append((cs2_class, parent_class, member_lines))
        result = ["""
###########################################################
# autogenerated with generate_code_for_enums()
# run this file with the C# code folder to regenerate it
###########################################################

import sys
from pathlib import Path

from cs2.cs2_enum import CS2BaseEnum, CS2BaseFlag

if __name__ == '__main__':
    from cs2.game import cs2game
    code = cs2game.parser.generate_code_for_enums(Path(sys.argv[1]))
    if code and len(code) > 100:
        with open(__file__, 'w') as file:
            file.write('\\n'.join(code))
    else:
        print('Error: enum generation failed. File is left unchanged')


"""]
        for name, classes in sorted(generated_classes.items()):
            use_full_name = len(classes) > 1
            for cs2_class, parent_class, member_lines in classes:
                if use_full_name:
                    class_name = cs2_class.replace('.', '')
                else:
                    class_name = name
                result.append(f'# {cs2_class}')
                result.append(f'class {class_name}({parent_class}):')
                # result.append(f'    _cs2_class = \'{cs2_class}\'')
                result.append('')
                result.append('\n'.join(member_lines))
                result.append('')
                result.append('')

        return result

    @cached_property
    def _theme_speedlimit_map(self) -> Dict[str,Dict[int, int]]:
        """taking the theme speedlimits from the localized names of the assets which have the speed limit signs
        this is very fragile"""
        speedlimit_map = {}
        for road_asset_collection in [assets for assets in self.parsed_assets.values() if assets.cs2_class == 'Game.Prefabs.AssetCollection' and assets.name.endswith('DecorationsRoad')]:
            theme_prefix = road_asset_collection.name.split('_')[0]
            speedlimit_map[theme_prefix] = {}
            for asset in road_asset_collection.prefabs:
                if hasattr(asset, 'TrafficSignObject') and TrafficSignType.SpeedLimit.value in asset.TrafficSignObject.signTypes:
                    speedlimit_map[theme_prefix][asset.TrafficSignObject.speedLimit] = int(asset.display_name.split(' ')[-1])
        return speedlimit_map

    def get_theme_speedlimit(self, theme_prefix: str, file_speedlimit: int) -> int|None:
        if file_speedlimit in self._theme_speedlimit_map[theme_prefix]:
            return self._theme_speedlimit_map[theme_prefix][file_speedlimit]
        else:
            return None

    @cached_property
    def landmarks(self) -> Dict[str, CS2_ASSET]:
        return {asset.name: asset for asset in self.parsed_assets.values() if
                hasattr(asset, 'UIObject') and
                asset.UIObject.group and
                asset.UIObject.group.name == 'SignaturesLandmarks'}

    @cached_property
    def landscaping(self) -> Dict[str, CS2_ASSET]:
        return {asset.name: asset for asset in self.parsed_assets.values() if
                hasattr(asset, 'UIObject') and
                asset.UIObject.group and
                hasattr(asset.UIObject.group, 'menu')
                and asset.UIObject.group.menu.name == 'Landscaping'
                and asset not in self.vegetations.values()}

    @cached_property
    def roads(self) -> Dict[str, CS2_ASSET]:
        return {asset.name: asset for asset in self.parsed_assets.values() if
                hasattr(asset, 'UIObject') and
                asset.UIObject.group and
                hasattr(asset.UIObject.group, 'menu')
                and asset.UIObject.group.menu.name == 'Roads'}

    @cached_property
    def service_buildings(self) -> Dict[str, CS2_ASSET]:
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
        return {asset.name: asset for asset in self.parsed_assets.values()
                if hasattr(asset, 'ServiceUpgrade')
                }

    @cached_property
    def signature_buildings(self) -> Dict[str, CS2_ASSET]:
        return {asset.name: asset for asset in self.parsed_assets.values() if hasattr(asset, 'SignatureBuilding')}

    @cached_property
    def transportation(self) -> Dict[str, CS2_ASSET]:
        return {asset.name: asset for asset in self.parsed_assets.values() if
                hasattr(asset, 'UIObject') and
                asset.UIObject.group and
                hasattr(asset.UIObject.group, 'menu')
                and asset.UIObject.group.menu.name == 'Transportation'}

    @cached_property
    def vegetations(self) -> Dict[str, CS2_ASSET]:
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

    @cached_property
    def maps(self) -> List[Map]:
        maps = []
        for path in (cs2game.game_path / 'Cities2_Data' / 'StreamingAssets' / 'Maps~').glob('*.MapMetadata'):
            with open(path, 'r', encoding='utf-8-sig') as data_file:
                data = json.load(data_file)
                # display name is actually the name
                # the real display name will be determined by add_attributes
                data['name'] = data['displayName']
                del data['displayName']
                map = Map('', path.name, 0)
                map.add_attributes(data)
                maps.append(map)
        return maps

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
        if not destination_folder.exists():
            destination_folder.mkdir()
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
