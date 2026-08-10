import copy
import re
from operator import attrgetter
from typing import Any

from functools import cached_property
from pathlib import Path

import luadata
from lua import Lua, Table

from common.paradox_parser import Tree
from common.wiki_image import WikiImage, WikiImageFile
from smr.survivingmarslib import *


class SMRParser:

    def __init__(self, unpacked_path: Path):
        self.unpacked_path = unpacked_path
        self.lua_path = unpacked_path / 'Lua/Lua'
        self.data_path = unpacked_path / 'Data'

    @cached_property
    def full_version(self) -> str:
        """the BuildVersion from _LuaRevision.lua"""
        revision_path = self.lua_path / 'Config/_LuaRevision.lua'
        code = Lua()
        lua_code = f'{revision_path.read_text()}\nreturn BuildVersion'
        return code.run(lua_code)

    def recursive_Table_to_python_dict(self, table: Table) -> dict:
        return {k: self.recursive_Table_to_python_dict(v) if isinstance(v, Table) else v
                for k, v in table.dict().items()}

    def recursive_Table_to_tree(self, table: Table) -> Tree:
        tree_data = {}
        for k, v in table.dict().items():
            if isinstance(k, int):
                if isinstance(v, Table) and 'type' in v and v['type'] == 'PlaceObj':
                    k = v['name']

            if isinstance(v, Table):
                v = self.recursive_Table_to_tree(v)
            if k in tree_data:
                if isinstance(tree_data[k], list):
                    tree_data[k].append(v)
                else:
                    tree_data[k] = [tree_data[k], v]
            else:
                tree_data[k] = v
        return Tree(tree_data)

    def read_lua_classes(self, folder: str, base_folder = None, extra_files:list[str|Path] = None) -> Tree:
        if base_folder is None:
            base_folder = self.lua_path
        lua = Lua()
        missing_functions = [
            'DefineStoryBitTrigger', 'CreateRealTimeThread',
            'DefineStoryBitTrigger', 'DefineStoryBitTrigger', 'set', 'GetColonistSpecializationCombo',
            'ClassDescendantsCombo', 'GetColonistSpecializationCombo',
            'PresetsCombo', 'PresetsCombo', 'SponsorCombo',
            'Legacy_DefineStoryBitTrigger', 'FixupObjectNotification', 'Legacy_DefineStoryBitTrigger',
            'Legacy_DefineStoryBitTrigger', 'Legacy_DefineStoryBitTrigger', 'FixupObjectNotification',
            'FixupObjectNotification'
        ]
        missing_functions_which_return_something = [
            'TLookupTag',
        ]
        missing_objects = [
            'PFTunnel', 'CargoTransporter', 'LifeSupportGridElement', 'RecursiveCallMethods', 'g_ConsumptionType',
            'g_CargoWeightCapacityLabels', 'AvailabilityStatus', 'terrain', 'ResourceNoRoundingDecimalPart',
            'NotificationFns', 'RegolithExtractorBase', 'OpenAirBuilding', 'config',
            'g_CargoWeightCapacityLabels', 'RecursiveCallMethods', 'EntityData', 'ResourcePile', 'GridObject',
            'config', 'Dome', 'NotificationFns', 'GridObject', 'NotificationFns',
            'BreakableSupplyGridElement', 'AutoResolveMethods', 'RocketPayloadObject', 'ServiceFailure',
            'DustGridElement', 'BaseBuilding', 'Colony', 'RequiresMaintenance', 'City', 'ElectricityGridElement',
            'UnpersistedMissingClass', 'LabelContainer', 'BaseExtractor', 'BaseExtractor', 'Presets', 'Presets.ConstDef',
            'io', 'terrain'
        ]

        for func_name in missing_functions:
            lua.run(f'function {func_name}(...) end')

        for func_name in missing_functions_which_return_something:
            lua.run(f'function {func_name}(...) return "" end')

        for obj_name in missing_objects:
            lua.run(f'{obj_name} = {{}}')

        # lua.run('DefineClass = {}')
        lua.run('DefineClass = {}')
        lua.run('''setmetatable(DefineClass, {
		__newindex = function (table, key, value)
		    rawset(_G, key, value)
		    rawset(table, key, value)
			return value
		end,
		__call = function (table, key)
			rawset(_G, key, {})
		    rawset(table, key, {})
		    return {}
		end,
	})''')
        lua.run('const = { TagLookupTable = {}}')
        missing_consts = ['HexWidth', 'HexHeight', 'pfmDestlock', 'pfmDestlockSmart', 'TypeTileSize', 'efVisible',
                          'efApplyToGrids', 'efCollision', 'HeightTileSize', 'rfSupply', 'MaxHeat', 'rfStorageDepot',
                          'ResourceScale', 'rfSpecialSupplyPairing', 'rfMechanizedStorage']
        for const_name in missing_consts:
            lua.run(f'const.{const_name} = 1')
        lua.run('OnMsg = {}')
        lua.run('PersistableGlobals = {}')
        lua.run('pf = {Step = 1}')
        lua.run('CObject = { IsValidPos = function (...) end, GetEnumFlags = function (...) end}')
        lua.run('FirstLoad = true')
        lua.run('Loading = true')
        lua.run('guim = 1') # game unit meter?
        lua.run('guic = 0.01') # game unit centimeter?
        lua.run('SavegameFixups = {}')
        lua.run('AppendClass = {}')
        lua.run('Residence = {}')
        lua.run('Service = {}')
        lua.run('ChainTypes = {}')
        lua.run('NotWorkingWarning = {}')
        lua.run('Building = { Getavailable_drone_prefabs = function (...) end}')
        lua.run('UngridedObstacle = { GetModifiedBSphereRadius = 1}')
        lua.run('UngridedObstacle.GetRotatedShapePoints = function (...) end')
        lua.run('function UndefineClass(arg) end')
        # lua.run('function T(id, default_localization) return { id = id, default_localization = default_localization } end')
        lua.run('function T(id, default_localization) return default_localization end')
        lua.run('function GameVar(name, value, meta) end')
        lua.run('function GlobalGameTimeThread(...) end')
        lua.run('function EnumEngineVars(prefix) return {} end')
        lua.run('function PlaceObj(name, data) return { type = "PlaceObj", name = name, data = data } end')
        lua.run('function RGB(red, green, blue) return { red = red, green = green, blue = blue } end')
        lua.run('function RGBA(red, green, blue, alpha) return { red = red, green = green, blue = blue, alpha = alpha } end')
        lua.run('function RGBRM(...) end')
        lua.run('function Untranslated(text) return text end')
        lua.run('function NewHierarchicalGrid(width, height, patch_size, bits, def) end')
        lua.run('function range(from, to) return { from = from, to = to } end')
        lua.run('function box(minx, miny, minz, maxx, maxy, maxz) end')
        lua.run('function sizebox(...) end')
        lua.run('function point(x, y, z) end')
        lua.run('function Rotate(pt, angle) end')
        lua.run('function InvalidPos() end')
        lua.run('function procall(f, arg1, ...) end')
        lua.run('function buildUnbuildableZ() return 2^16 - 1 end')
        lua.run('function ForEachLib(path, func, ...) end')
        lua.run('io.exists = function(filename) return false end')
        lua.run('function DefineConstInt(group, name, value, ...) const[group].name = value end')

        lua.run('Platform = {cmdline = true}')
        lua.run_file(str(self.unpacked_path / 'Lua/CommonLua/Core/lib.lua'))
        lua.run_file(str(self.unpacked_path / 'Lua/CommonLua/TFormat.lua'))
        # lua.run_file(str(self.unpacked_path / 'Lua/CommonLua/Core/types.lua'))
        lua.run('Platform = {cmdline = false}')
        lua.run_file(str(self.unpacked_path / 'Lua/CommonLua/Core/const.lua'))
        lua.run_file(str(self.unpacked_path / 'Lua/Lua/HasConsumption.lua'))
        lua.run_file(str(self.unpacked_path / 'Lua/Lua/GridTunnelConnector.lua'))
        lua.run('const.Scale.h = 60')
        lua.run('const.Scale.sols = 24 * 60')
        lua.run('const.Scale.Resources = 1')
        lua.run('const.Scale.Stat = 1')
        # lua.run('function table.insert_unique(t, x) if not t.find(x) then t[#t + 1] = x return true end end')
        lua.run('function table.insert_unique(t, x) t[#t + 1] = x return true end')
        lua.run('''function table.keys(t, sorted)
	local res = {}
	if t and next(t) then
		for k in pairs(t) do
			res[#res+1] = k
		end
		if sorted then
			table.sort(res)
		end
	end
	return res
end''')
        lua.run_file(str(self.unpacked_path / 'Lua/Lua/_GameConst.lua'))
        lua.run('Platform = {cmdline = true}')
        self.run_lua_files(lua, base_folder, folder, extra_files)
        lua_classes = lua.run('return DefineClass')
        result = self.recursive_Table_to_tree(lua_classes)
        return result

    def read_place_obj(self, place_obj_type, file_or_folder: str, base_folder = None, extra_files:list[str|Path] = None) -> Tree:
        if base_folder is None:
            base_folder = self.data_path
        lua = Lua()
        # lua.rLua syntax errorun('DefineClass = {}')
        lua.run('const = {}')
        # lua.run('function UndefineClass(arg) end')
        # lua.run('function T(id, default_localization) return { id = id, default_localization = default_localization } end')
        lua.run('function T(id, default_localization) return default_localization end')
        lua.run('function range(from, to) return { from = from, to = to } end')
        lua.run('placed_objs = {}')
        lua.run(f'function PlaceObj(name, data) if name == "{place_obj_type}" then placed_objs[data["id"]] = data else return {{ type = "PlaceObj", name = name, data = data }} end end')
        self.run_lua_files(lua, base_folder, file_or_folder, extra_files)
        lua_classes = lua.run('return placed_objs')
        # return self.recursive_Table_to_python_dict(lua_classes)
        return self.recursive_Table_to_tree(lua_classes)

    def run_lua_files(self, lua: Lua, base_folder: Path | Any, file_or_folder: str,
                      extra_files: list[str | Path] | None):
        missing_functions = []
        missing_objects = []
        if extra_files is None:
            files = []
        else:
            files = [base_folder / file for file in extra_files]
        if file_or_folder.endswith('.lua'):
            files.append(base_folder / file_or_folder)
            for file in self.unpacked_path.glob(f'DLC/*/Code/{file_or_folder}'):
                if file not in files:
                    files.append(file)
        else:
            for file in (base_folder / file_or_folder).glob('*.lua'):
                if file not in files:
                    files.append(file)
            for file in self.unpacked_path.glob(f'DLC/*/Code/{file_or_folder}/*.lua'):
                if file not in files:
                    files.append(file)
        for file in files:
            # if file.name.startswith('_'):
            #     continue
            try:
                lua.run_file(str(file))
            except Exception as e:
                match = re.search(r"attempt to call a nil value \(global '([^']+)'", str(e))
                if match is not None:
                    missing_functions.append(match.group(1))
                else:
                    match = re.search(r"a nil value \(global '([^']+)'", str(e))
                    if match is not None:
                        missing_objects.append(match.group(1))
                print(f'Error in file {str(file)}')
                print(e)
        print('Missing functions:', missing_functions)
        print('Missing objects:', missing_objects)

    def _get_building_data_with_parents(self, building: str, data_sources: list[Tree], processed_classes: dict[str, Tree], parents_in_this_recursion = None) -> Tree:
        if building in processed_classes:
            return processed_classes[building]
        if parents_in_this_recursion is None:
            parents_in_this_recursion = []
        else:
            if building in parents_in_this_recursion:
                return Tree({})
        parents_in_this_recursion = parents_in_this_recursion + [building]
        data = Tree({})
        for data_source in data_sources:
            if building in data_source:
                parent_data = Tree({})
                building_data_from_one_source = Tree(data_source[building].dictionary.copy())
                if '__parents' in building_data_from_one_source:
                    for parent in list(building_data_from_one_source['__parents']):
                        if isinstance(parent, tuple):
                            parent = parent[1]
                        new_parent_data = self._get_building_data_with_parents(parent, data_sources, processed_classes, parents_in_this_recursion)
                        try:
                            parent_data.update(new_parent_data)
                        except Exception:
                            parent_data.dictionary.update(new_parent_data.dictionary)
                    try:
                        building_data_from_one_source = parent_data.update(building_data_from_one_source)
                    except Exception:
                        parent_data.dictionary.update(building_data_from_one_source.dictionary)
                        building_data_from_one_source = parent_data
                data.update(building_data_from_one_source)
        processed_classes[building] = data
        return data

    @cached_property
    def buildings(self) -> dict[str, Building]:
        buildings = {}
        building_template_data = self.read_lua_classes('BuildingTemplate', extra_files=['Passage.lua'])
        buildings_data = self.read_lua_classes('Buildings')
        processed_classes = {}
        for building in building_template_data.keys():
            data = self._get_building_data_with_parents(building, [building_template_data, buildings_data], processed_classes)

            if 'display_icon' in data:
                icon = data['display_icon']
            elif 'object_class' in data and data['object_class'] in building_template_data and 'display_icon' in building_template_data[data['object_class']]:
                icon = building_template_data[data['object_class']]['display_icon']
            else:
                icon = None
            if 'name' in data:
                del data['name']
            if 'icon' in data:
                del data['icon']
            buildings[building] = Building(building, icon=icon, **data)
        return buildings

    @cached_property
    def crops(self) -> dict[str, Crop]:
        crops = {}
        for crop, data in self.read_place_obj('CropPreset', 'CropPreset.lua'):
            if 'Desc' in data:
                data['description'] = data['Desc']
            display_name = data['DisplayName']
            crops[crop] = Crop(crop, display_name, **data)

        return crops


    @cached_property
    def laws(self) -> dict[str, Law]:
        return {
            law: Law(law, **data)
            for law, data in self.read_place_obj('PolicyDef', 'PolicyDef.lua')
            if law != 'NoPolicy'
        }

    @cached_property
    def technologies(self) -> dict[str, Technology]:
        return {
            tech: Technology(tech, **data)
            for tech, data in self.read_place_obj('TechPreset', 'TechPreset.lua')
        }

    @cached_property
    def units(self) -> dict[str, Unit]:
        units = {}
        lua_data = self.read_lua_classes('Units', extra_files=[ 'Interests.lua', 'Flight.lua', 'Buildings/BaseRover.lua', 'Units/DroneBase.lua', 'Units/Drone.lua', 'Units/Colonist.lua', 'Buildings/ShuttleHub.lua'])
        for unit, data in lua_data:
            if unit.startswith('Base') or 'display_name' not in data or not data['display_name']:
                continue

            if 'display_icon' in data:
                icon = data['display_icon']
            elif 'object_class' in data and data['object_class'] in lua_data and 'display_icon' in lua_data[
                data['object_class']]:
                icon = lua_data[data['object_class']]['display_icon']
            else:
                icon = None
            if 'name' in data:
                del data['name']
            units[unit] = Unit(unit, icon=icon, **data)
        return units

    @cached_property
    def crop_icons(self):
        crop_files = [file for prefix in ('animal_', 'crops_') for file in (self.unpacked_path / 'UI/IconsRemaster/Buildings').glob(f'{prefix}*')]
        # return [file for file]

    @cached_property
    def wiki_images(self) -> list[WikiImage]:
        image_file_references = [
            entity.get_wiki_image_file_reference()
            for entity_attribute in [
                self.buildings,
                self.crops,
                self.laws,
                self.technologies,
                self.units,
            ]
            for entity in entity_attribute.values()
        ]
        # building upgrade icons
        for building in self.buildings.values():
            for upgrade in building.upgrades:
                image_file_references.append(upgrade.get_wiki_image_file_reference())

        all_main_filenames = [
            entity.get_wiki_image_file_reference().wiki_filename.casefold()
            for entity_attribute in [
                self.buildings,
                self.laws,
                self.technologies
            ]
            for entity in entity_attribute.values()
            if entity.get_wiki_image_file_reference() is not None
        ]
        image_files:dict[str, WikiImageFile] = {}
        sorted_refs = sorted(filter(lambda x: x is not None, image_file_references), key=attrgetter('wiki_filename', 'description'))
        for ref in sorted_refs:
            if ref is None:
                continue
            ref.obsolete_filenames = list(filter(lambda x: x.casefold() not in all_main_filenames, ref.obsolete_filenames))
            if ref.image_data_hash not in image_files:
                image_files[ref.image_data_hash] = WikiImageFile([ref])
            else:
                image_files[ref.image_data_hash].references.append(ref)

        return [WikiImage([image_file]) for image_file in
                sorted(image_files.values(), key=attrgetter('main_wiki_filename'))]

    # dummy to satisfy the helper
    def find_possible_entities_by_name(self, name):
        return None

    # dummy to satisfy the helper
    @cached_property
    def modifier_types(self):
        return {}