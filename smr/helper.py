from functools import cached_property
from pathlib import Path

from common.helper import OneTypeHelper
from smr.parser import SMRParser

smr_path = Path('~/Downloads/SMROldVersions/1.0.6/Unpacks').expanduser()

class SMROneTypeHelper(OneTypeHelper):

    parser: SMRParser

    def __init__(self, folder, depth=0, ignored_toplevel_keys: list = None, ignored_keys: list = None,
                 class_name_map=None, ignore_based_on_data=None,
                 place_obj_type: str=None):
        super().__init__(folder, depth, ignored_toplevel_keys, ignored_keys, class_name_map, ignore_based_on_data)
        self.parser = SMRParser(smr_path)
        self.place_obj_type = place_obj_type


    def get_data(self):
        if self.place_obj_type:
            data = self.parser.read_place_obj(self.place_obj_type, self.folder)
        else:
            data = self.parser.read_lua_classes(self.folder)
        return [('allfilesinone', data)]

    @cached_property
    def keys(self) -> dict[str, list]:
        keys = super().keys
        # threshold = len(keys) / 5
        # threshold = 10
        threshold = 0
        return {k: v for k, v in keys.items() if len(v) > threshold}


    def get_possible_loc_prefixes_or_suffixes(self) -> list[tuple[str, str, int, list[str]]]:
        return []


SMROneTypeHelper(
    # 'BuildingTemplate',
    'CropPreset.lua',
    # depth=1,
    # ignored_keys=list(),
    # ignored_toplevel_keys=['scripted_effect', 'scripted_trigger', 'namespace',]
    # ignore_based_on_data=lambda key, data, depth: (depth == 1 and key != 'dynamic_historical_event') or ':' in key,
    place_obj_type='CropPreset',

).print_examples_and_code()