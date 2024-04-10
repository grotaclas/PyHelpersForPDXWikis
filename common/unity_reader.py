import json
import subprocess
from functools import cached_property
from pathlib import Path

import UnityPy
from UnityPy import Environment

from PyHelpersForPDXWikis.localsettings import TYPE_TREE_GENERATOR
from common.paradox_lib import Game


class UnityReader:

    def __init__(self, data_folder: Path, game: Game, game_dll: str):
        """

        Args:
            data_folder: subfolder of the game folder which contains the unity asset files
            game: the game is used to determine game and cache folders
            game_dll: the name of the main dll file for the game. it is used to generate type trees
        """
        self.data_folder = data_folder
        self.game = game
        # name of the dll file in the Managed folder which contains the game classes to parse MonoBehavior assets
        self.game_dll = game_dll
        self.object_cache = {}
        self.nodes_with_flattened_components = set()  # to avoid duplicated work and infinite recursion

    @cached_property
    def env(self) -> Environment:
        # all asset bundles files seem to be directly in the data folder. But some of the subfolders have many files
        # which breaks unitypy, so we have to supply it with the files which it should read
        possible_ressource_files = [str(f) for f in self.data_folder.glob('*') if f.is_file()]
        return UnityPy.load(*possible_ressource_files)

    @cached_property
    def unity_version(self):
        return self.env.assets[0].unity_version

    @cached_property
    def type_trees(self):
        type_tree_file = self.game.cachepath / (self.game_dll + '.json')
        if not type_tree_file.exists():
            subprocess.run(
                ['dotnet', TYPE_TREE_GENERATOR, '-p', self.data_folder / 'Managed', '-a', self.game_dll, '-v', self.unity_version,
                 '-d', 'json', '-o', type_tree_file])
        return json.load(open(type_tree_file, "rt", encoding="utf8"))
