from functools import cached_property
from pathlib import Path
from types import NoneType

from UnityPy.classes import PPtr
from UnityPy.classes.Object import NodeHelper
from UnityPy.files import ObjectReader

from common.unity_reader import UnityReader
from cs2.game import cs2game


class MonoBehaviourReader(UnityReader):

    # 30 is a failsafe which has not been reached
    # A value of 10 or lower can speed up parsing, especially if inefficient algorithms are used on the results
    MAX_RECURSION_DEPTH = 30


    IGNORED_CLASSES = ['Game.Prefabs.ObjectSubObjects',  # e.g. gates
                       'Game.Prefabs.ObjectSubAreas',  # e.g. pavement
                       'Game.Prefabs.ObjectSubNets',  # pathways
                       'Game.Prefabs.ObjectSubLanes',  # fences?
                       'Game.Prefabs.EffectSource',  # seems to be visual effects
                       'Game.Prefabs.BuildingTerraformOverride',
                       # seems to specify how much terraforming will be done to construct it
                       'Game.Prefabs.ObsoleteIdentifiers',  # I guess they are obsolete
                       'Game.Prefabs.ActivityLocation',  # benches and parking spots
                       'Game.Prefabs.RenderPrefab',
                       # meshes. reading it sometimes throws an exception in read_typetree
                       'Game.Prefabs.CharacterStyle',  # read errors
                       'Game.UI.UIEconomyConfigurationPrefab',  # read errors
                       'Game.Prefabs.EmissiveProperties',  # read errors
                       'Game.Prefabs.TaxableResource',  # read errors
                       'UnityEngine.*',  # this line is just a reminder that typetrees for unity stuff
                                         # is not implemented. The classes have to be ignored in other ways
                       ]

    def __init__(self, data_folder: Path):
        super().__init__(data_folder, cs2game, 'Game.dll')

    @cached_property
    # @disk_cache(game=cs2game)
    def _path_id_cls_maps(self) -> (dict[str, dict[int, str]], dict[str, dict[int, str]]):
        obj_path_id_cls_map = {}
        script_path_id_cls_map = {}
        for obj in self.env.objects:
            if obj.type.name == 'MonoScript':
                if obj.assets_file.name not in script_path_id_cls_map:
                    script_path_id_cls_map[obj.assets_file.name] = {}
                if obj.path_id not in script_path_id_cls_map[obj.assets_file.name]:
                    script = obj.read()
                    script_path_id_cls_map[obj.assets_file.name][obj.path_id] = f"{script.m_Namespace}.{script.m_ClassName}"

            if obj.type.name == 'MonoBehaviour':
                data = obj.read()
                if data.m_Script.path_id == 0:
                    continue  # skip objects without classes
                if data.m_Script.assets_file.name not in script_path_id_cls_map:
                    script_path_id_cls_map[data.m_Script.assets_file.name] = {}
                if data.m_Script.path_id not in script_path_id_cls_map[data.m_Script.assets_file.name]:
                    script = data.m_Script.read()
                    script_path_id_cls_map[data.m_Script.assets_file.name][data.m_Script.path_id] = f"{script.m_Namespace}.{script.m_ClassName}"
                if obj.assets_file.name not in obj_path_id_cls_map:
                    obj_path_id_cls_map[obj.assets_file.name] = {}
                obj_path_id_cls_map[obj.assets_file.name][obj.path_id] = script_path_id_cls_map[data.m_Script.assets_file.name][data.m_Script.path_id]
        return script_path_id_cls_map, obj_path_id_cls_map

    def get_cls(self, obj: ObjectReader):
        try:
            return self._path_id_cls_maps[1][obj.assets_file.name][obj.path_id]
        except KeyError:
            return None

    def parse_monobehaviour(self, obj: ObjectReader, depth=0, ignored_classes=None):
        if depth > self.MAX_RECURSION_DEPTH:
            print(f'Warning: reached MAX_RECURSION_DEPTH of {self.MAX_RECURSION_DEPTH}')
            return f'Error reached MAX_RECURSION_DEPTH of {self.MAX_RECURSION_DEPTH}'
        if obj.assets_file.name not in self.object_cache:
            self.object_cache[obj.assets_file.name] = {}
        if obj.path_id in self.object_cache[obj.assets_file.name]:
            return self.object_cache[obj.assets_file.name][obj.path_id]
        if ignored_classes is None:
            ignored_classes = self.IGNORED_CLASSES
        if obj.type.name == 'MonoBehaviour':
            cls = self.get_cls(obj)
            if cls:
                if cls in ignored_classes or (not cls.startswith('Game.') and not cls.startswith('CPrompt.')):
                    return f'Ignored object of class "{cls}" (path id "{obj.path_id}", file "{obj.assets_file}")'
            # try:
            if cls:
                type_template = self.type_trees[cls]
                tree = obj.read_typetree(type_template, wrap=True)
            else:
                tree = obj.read_typetree(wrap=True)
            tree.cs2_class = cls                    # to determine the object type later
            tree.file_name = obj.assets_file.name   # as unique keys
            tree.path_id = obj.path_id              # as unique keys
            # except Exception as e:
            #     print(f'Cant read object "{obj}" with class {cls}')
            #     return f'Error reading object of class "{cls}"'
        else:
            tree = obj.read()
        self.object_cache[obj.assets_file.name][obj.path_id] = tree
        self.read_node_helper(tree, depth, ignored_classes)
        return tree

    def read_node_helper(self, tree: NodeHelper, depth, ignored_classes):
        for key, val in tree.__dict__.items():
            # if isinstance(val, PPtr) and val.path_id != 0 and val.type.name in ['MonoBehaviour', 'Transform', 'GameObject', 'MonoScript', 'TextAsset']:
            if isinstance(val, PPtr) and val.path_id != 0 and val.type.name == 'MonoBehaviour':
                setattr(tree, key, self.parse_monobehaviour(val, depth + 1, ignored_classes=ignored_classes))
            elif isinstance(val, PPtr) and val.path_id == 0:
                setattr(tree, key, None)
            elif isinstance(val, PPtr):
                setattr(tree, key,  f'Ignored asset of type "{val.type.name}"')
            elif isinstance(val, list):
                for i, item in enumerate(val):
                    # if isinstance(item, PPtr) and item.path_id != 0 and item.type.name in ['MonoBehaviour', 'Transform', 'GameObject', 'MonoScript']:
                    if isinstance(item, PPtr) and item.path_id != 0 and item.type.name == 'MonoBehaviour':
                        val[i] = self.parse_monobehaviour(item, depth + 1, ignored_classes=ignored_classes)
                    elif isinstance(item, PPtr) and item.path_id == 0:
                        val[i] = None
                    elif isinstance(item, NodeHelper):
                        val[i] = self.read_node_helper(item, depth + 1, ignored_classes)
                    elif not isinstance(item, PPtr) and type(item) not in [int, str, bool, float, NoneType]:
                        print(f'Cant read type {type(item)}')
                        pass
            elif isinstance(val, NodeHelper):
                setattr(tree, key, self.read_node_helper(val, depth + 1, ignored_classes))
            elif not isinstance(val, PPtr) and type(val) not in [int, str, bool, float, NoneType]:
                print(f'Cant read type {type(val)}')
                pass
        return tree

    def remove_unimportant(self, nodes: NodeHelper,
                           attributes=['m_GameObject', 'm_Enabled', 'm_Script', 'active', 'm_NameOverride', 'm_Meshes'],
                           visited=None):
        # from collections import Mapping
        if visited is None:
            visited = set()

        if isinstance(nodes, NodeHelper):
            if nodes in visited:
                return
            else:
                visited.add(nodes)
            for key in list(nodes.keys()):
                self._remove_unimportant_one_element(nodes,key, attributes, visited)
        elif isinstance(nodes, list):
            for key, item in enumerate(nodes):
                self._remove_unimportant_one_element(nodes, key, attributes, visited)

    def _remove_unimportant_one_element(self, nodes, key, attributes, visited):
        if key in attributes:
            delattr(nodes, key)
        elif isinstance(nodes[key], NodeHelper) or isinstance(nodes[key], list):
            self.remove_unimportant(nodes[key], attributes, visited=visited)

    def inline_components(self, nodes: NodeHelper) -> NodeHelper:
        """turn the entries of the components list into top level attributes with the name of the component

        This way they can be addressed without iterating through all components"""
        if hasattr(nodes, 'components'):
            for component in nodes.components:
                if isinstance(component, str) and component.startswith('Ignored object of class'):
                    continue
                elif component is None:
                    continue
                if hasattr(nodes, component.m_Name):
                    raise Exception(f'entry "{component.m_Name}" already exists')
                setattr(nodes, component.m_Name, component)
            delattr(nodes, 'components')
        return nodes

    def inline_components_recursive(self, nodes: NodeHelper, visited = None):
        if visited is None:
            visited = set()

        if nodes in visited:
            return
        else:
            visited.add(nodes)

        self.inline_components(nodes)

        for key, value in nodes.items():
            if isinstance(value, NodeHelper):
                self.inline_components_recursive(value, visited)
            elif isinstance(value, list):
                for element in value:
                    if isinstance(element, NodeHelper):
                        self.inline_components_recursive(element, visited)

    def flatten_node_tree(self, nodes: NodeHelper, prefix='', max_depth=10) -> dict[str, any]:
        """Can be used to generate a csv-like export, but is slow if used on many objects and has huge amounts of duplicated data"""
        if max_depth < 0:
            return {'max_depth': 'Max depth reached'}
        result = {}
        if prefix == '':
            result['name'] = nodes.m_Name
        for key, value in nodes.items():
            if isinstance(value, str) and value.startswith('Ignored object of class'):
                continue
            if key in ['m_Name', 'components']:
                continue
            if isinstance(value, NodeHelper):
                if hasattr(value, 'm_Name'):
                    result[f'{prefix}{key}.name'] = value.m_Name
                result.update(self.flatten_node_tree(value, f'{prefix}{key}.', max_depth=max_depth-1))
            elif isinstance(value, list):
                for i, element in enumerate(value):
                    if isinstance(element, NodeHelper):
                        result.update(self.flatten_node_tree(element, f'{prefix}{key}.{i}.', max_depth=max_depth-1))
                    else:
                        result[f'{prefix}{key}.{i}'] = element
            else:
                if isinstance(value, PPtr) and value.path_id == 0:
                    value = None
                result[f'{prefix}{key}'] = value
        if hasattr(nodes, 'components'):
            for component in nodes.components:
                if isinstance(component, str) and component.startswith('Ignored object of class'):
                    continue
                elif component is None:
                    continue
                result.update(self.flatten_node_tree(component, f'{prefix}{component.m_Name}.', max_depth=max_depth-1))

        return result

    def transform_nodes_to_dict(self, nodes: NodeHelper, is_component=False, transform_cache=None):
        if transform_cache is None:
            transform_cache = set()
        if nodes in transform_cache:
            return f'Already seen {nodes}'
        else:
            transform_cache.add(nodes)
        result = {}
        if hasattr(nodes, 'm_Name') and not is_component:
            result['name'] = nodes.m_Name
        elif is_component:
            pass
        for key, value in nodes.items():
            if isinstance(value, str) and value.startswith('Ignored object of class'):
                continue
            if key in ['m_Name', 'components']:
                continue
            if isinstance(value, NodeHelper):
                result[key] = self.transform_nodes_to_dict(value, transform_cache=transform_cache)
            elif isinstance(value, list):
                result[key] = [
                    self.transform_nodes_to_dict(element, transform_cache=transform_cache) if isinstance(element, NodeHelper)
                    else str(element) if isinstance(element, PPtr)
                    else element
                    for element in value]
            elif isinstance(value, PPtr) and value.path_id == 0:
                result[key] = None
            elif isinstance(value, PPtr):
                result[key] = str(value)
            else:
                result[key] = value

        return result
