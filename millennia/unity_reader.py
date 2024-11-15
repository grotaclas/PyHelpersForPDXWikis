import base64
import json
import re
import xml.etree.ElementTree as ET
from functools import cached_property
from pathlib import Path

from PIL import Image
import UnityPy
from UnityPy.classes import PPtr, Texture2D, GUID
from UnityPy.export import SpriteHelper
from UnityPy import Environment
from UnityPy.files import File

from common.cache import disk_cache
from common.unity_reader import UnityReader
from millennia.catalog import Catalog
from millennia.game import millenniagame


class UnityReaderMillennia(UnityReader):
    def __init__(self):
        super().__init__(millenniagame.game_path / 'Millennia_Data', millenniagame, 'Assembly-CSharp.dll')

    @cached_property
    def env(self) -> Environment:
        # all asset bundles files seem to be directly in the data folder. But some of the subfolders have many files
        # which breaks unitypy, so we have to supply it with the files which it should read
        possible_ressource_files = [str(f) for f in self.data_folder.glob('*') if f.is_file()]
        for f in (self.data_folder / 'StreamingAssets').rglob('*'):
            if f.is_file():
                possible_ressource_files.append(str(f))
        return UnityPy.load(*possible_ressource_files)

    @cached_property
    def resource_manager(self):
        for obj in self.env.objects:
            if obj.type.name == 'ResourceManager':
                return obj.read()

    @cached_property
    def assets_by_key(self) -> dict[str, PPtr]:
        """Gets assets by their addressable key

        Several fallbacks are used for assets which are not found, but there are still some which are missing. It might be broken data or they
        are stored differently. It seems to only affect unit textures which are not used for the wiki"""
        container = self.env.container
        assets_by_file = {
            f.name: f.container
            for f in self.env.files.values()
            if isinstance(f, File) and not f.is_dependency
        }

        # collect data for fallbacks
        extra_map = {}
        for i, bucket in enumerate(self.catalog.buckets):
            locs = []
            for entry in bucket['entries']:
                locs.append(self.catalog.entries[entry])
            extra_map[self.catalog.keys[i]] = locs
        # collect names for error messages
        name_map = {}
        for obj in self.env.objects:
            if obj.type.name in ['TextAsset', 'Texture2D']:
                data = obj.read()
                if data.m_Name not in name_map:
                    name_map[data.m_Name] = []
                name_map[data.m_Name].append(data.assets_file.name)
                if data.assets_file.parent and hasattr(data.assets_file.parent, 'name'):
                    name_map[data.m_Name].append(data.assets_file.parent.name)

        assets = {}
        for entry in self.catalog_entries:
            if entry['dependencyKey']:
                if entry['dependencyKey'] in assets_by_file:
                    if str(entry['internalId']) in assets_by_file[entry['dependencyKey']]:
                        # this is how it should work
                        assets[entry['primaryKey']] = assets_by_file[entry['dependencyKey']][str(entry['internalId'])]
                    else:
                        # old fallbacks which dont happen anymore
                        if str(entry['internalId']) in container:
                            print(f'Found primary key "{entry["primaryKey"]}" by using old fallback with the container. This should not happen anymore')
                            assets[entry['primaryKey']] = container[str(entry['internalId'])]
                        else:
                            print(f'Old fallback when looking for primary key "{entry["primaryKey"]}" did not work. This should not happen anymore')
                else:
                    # fallback via the extra map
                    possible_name = entry['primaryKey'].split('/')[-1]
                    possible_sources = extra_map[entry['dependencyKey']]
                    other_assets = []
                    for source in possible_sources:
                        if source['primaryKey'] in assets_by_file:
                            if str(entry['internalId']) in assets_by_file[source['primaryKey']]:
                                asset = assets_by_file[source['primaryKey']][str(entry['internalId'])]
                                other_assets.append(asset)

                    if len(other_assets) == 1:
                        obj = other_assets[0].read()
                        # comparing the name was originally implemented to make sure that the addressable found the correct asset
                        # but many millennia assets have slightly different names than the addressables. And there don't seem to be cases in which
                        # the asset is wrong if there is only one asset
                        ignore_name_mismatch = True
                        if ignore_name_mismatch or obj.m_Name.lower() == possible_name.lower():
                            assets[entry['primaryKey']] = other_assets[0]
                        else:
                            print(f'Name mismatch. Expected "{possible_name}", actual "{obj.m_Name}" in Dependency key "{entry["dependencyKey"]}" when looking for key "{entry["primaryKey"]}"')
                    elif len(other_assets) > 1:
                        # fallback by matching the keys of the entry to the m_RenderDataKey of an asset
                        names = []
                        asset_with_matching_names = []
                        good_asset = None
                        for asset in other_assets:
                            if not asset:
                                continue
                            obj = asset.read()
                            names.append(obj.m_Name)
                            if hasattr(obj, 'm_RenderDataKey'):
                                render_data_key_hex = self._guid_to_hex(obj.m_RenderDataKey[0])
                                if render_data_key_hex in entry['keys']:
                                    # definitely the correct object
                                    good_asset = asset
                                    break
                            if obj.m_Name.lower() == possible_name.lower():
                                asset_with_matching_names.append(asset)
                                if good_asset is None:
                                    good_asset = asset
                                else:
                                    good_asset = None
                                    break
                        if good_asset is None and len(asset_with_matching_names) == 1:
                            # fallback by looking for an asset which has the same name, but only use it if there is just one
                            good_asset = asset_with_matching_names[0]
                        if good_asset is not None:
                            assets[entry['primaryKey']] = good_asset
                        else:
                            # print(f'Multiple entries for Dependency key "{entry["dependencyKey"]}". Primary key "{entry["primaryKey"]}". Other names: {",".join(names)}')
                            pass
                    else:
                        print(f'Dependency key "{entry["dependencyKey"]}" not found for "{entry["primaryKey"]}"|{name_map[possible_name] if possible_name in name_map else ""}')

            else:
                if entry['provider'] == 'UnityEngine.ResourceManagement.ResourceProviders.AssetBundleProvider':
                    pass  # asset bundles don't have a dependency key
                else:
                    print(f'No dependency key for: {entry["primaryKey"]}')

        return assets

    @staticmethod
    def _guid_to_hex(guid: GUID):
        """convert the data fields of the GUID to hex and concatenate them"""
        render_key_str = ''
        for i in range(4):
            int_data = getattr(guid, f'data_{i}_')
            hex_data = f'{int_data:0{8}x}'  # length 8 to not lose 0's in the middle
            # for some reason the value is reversed
            render_key_str += hex_data[::-1]
        return render_key_str

    @cached_property
    def assets_by_key_lowercase(self) -> dict[str, PPtr]:
        return {key.lower(): asset for key, asset in self.assets_by_key.items()}

    @cached_property
    def catalog_entries(self):
        return self.catalog.entries

    @cached_property
    def catalog(self):
        with open(self.data_folder / 'StreamingAssets/aa/catalog.json') as file:
            catalog = Catalog(file)
        return catalog

    @cached_property
    def resources(self) -> dict[str, PPtr]:
        """deprecated. For the old resource system before update 5"""
        return {key: ptr for key, ptr in self.resource_manager.m_Container.items()}

    def get_resource_ptrs_by_prefix(self, prefix: str) -> dict[str, PPtr]:
        return {key: ptr for key, ptr in self.assets_by_key.items() if key.lower().startswith(prefix.lower())}

    @cached_property
    @disk_cache(game=millenniagame)
    def text_asset_resources(self) -> dict[str, dict[str, str]]:
        """return a dict of folders -> dict of filenames -> file contents"""
        text_by_path = {}
        for key, ptr in self.get_resource_ptrs_by_prefix('text/').items():
            data = ptr.read()
            key_parts = key.split('/')
            resource_name = key_parts[-1]
            path = '/'.join(key_parts[:-1])
            path = path.lower()
            if resource_name.lower() != data.m_Name.lower():
                print(f'Warning: resource name "{resource_name}" does not match asset name "{data.m_Name}" in path "{path}"')
            if path not in text_by_path:
                text_by_path[path] = {}
            if data.m_Name in text_by_path[path]:
                print(f'Warning: duplicate text asset "{data.m_Name}" with path "{path}"')
            text_by_path[path][data.m_Name] = data.m_Script
        return text_by_path

    @staticmethod
    def _is_xml(string: str):
        """rudimentary xml detection"""
        for line in string.split('\n'):
            if re.match(r'^\s*<', line):
                return True
            elif re.match(r'^\s*$', line):
                continue
            else:
                return False
        return False

    def dump_text_resources(self, output_folder: Path):
        for folder_name, files in self.text_asset_resources.items():
            folder = output_folder / folder_name
            folder.mkdir(parents=True, exist_ok=True)
            for filename, contents in files.items():
                if self._is_xml(contents):
                    file_extension = 'xml'
                else:
                    file_extension = 'txt'
                with open(folder / f'{filename}.{file_extension}', 'w') as file:
                    file.write(contents)

    @cached_property
    @disk_cache(game=millenniagame)
    def localizations(self):
        localizations = {}
        unresolved_imports = {}
        for path, texts in self.text_asset_resources.items():
            if path.lower().startswith('text/en_us'):
                for text in texts.values():
                    # root = et.fromstring(text)
                    root = ET.XML(text)
                    # print(root.tag)
                    for entry in root:
                        key = entry.find('Key')
                        if key is not None:  # entries without a key are ignored. They are probably empty
                            value = entry.find('Value')
                            value_text = None
                            if value is None:
                                import_key = entry.find('Import')
                                if import_key is None:
                                    print(f'Warning: loc key "{key.text}" has neither a value nor an import')
                                else:
                                    if import_key.text in localizations:
                                        value_text = localizations[import_key.text]
                                    else:
                                        value_text = f'import:{import_key.text}'
                                        if import_key.text not in unresolved_imports:
                                            unresolved_imports[import_key.text] = []
                                        unresolved_imports[import_key.text].append(key.text)
                            else:
                                value_text = value.text
                            if key.text in localizations:
                                print(
                                    f'Warning: duplicated loc key "{key.text}" old text was "{localizations[key.text]}" new text is "{value_text}"')
                            if value_text is None:
                                print(
                                    f'Warning: no value found for loc key "{key.text}"')
                            else:
                                localizations[key.text] = value_text
                                if key.text in unresolved_imports:
                                    for unresolved_import in unresolved_imports[key.text]:
                                        localizations[unresolved_import] = value_text
                                    del unresolved_imports[key.text]

        for import_key_text, key_text in unresolved_imports.items():
            print(f'Warning: loc key "{key_text}" has import "{import_key_text}" which was not found')
        return localizations

    def get_entity_icon(self, entity_name) -> Image.Image | None:
        path = f'entities/icons/{entity_name}'
        if path not in self.assets_by_key_lowercase:
            path += '-icon'  # try it with icon suffix
        return self.get_image_resource(path)

    def get_entity_portrait(self, portrait) -> Image.Image | None:
        path = f'entities/portraits/{portrait}'
        return self.get_image_resource(path)

    def get_card_icon(self, card_name, card_category):
        path = f'cards/{card_category}/{card_name}'
        return self.get_image_resource(path)

    def get_image_resource(self, path) -> Image.Image | None:
        path = path.lower()
        if path in self.assets_by_key_lowercase:
            sprite = self.assets_by_key_lowercase[path].read()
            # we can't just return sprite.image, because unityPy crops the images
            if isinstance(sprite, Texture2D):
                # texture2D would need a different handling, but they don't seem to crop the image, so we don't need the custom processing
                return sprite.image
            # this is a simplified version of the code from unityPy without all special cases which don't apply to millennia
            sprite_atlas_data = sprite.m_RD
            texture_2d = sprite_atlas_data.texture
            alpha_texture = sprite_atlas_data.alphaTexture
            original_image = SpriteHelper.get_image(sprite, texture_2d, alpha_texture)

            return original_image.transpose(Image.FLIP_TOP_BOTTOM)
        else:
            return None


if __name__ == '__main__':
    # output all keys for debugging
    unity_reader = UnityReaderMillennia()
    keys = unity_reader.assets_by_key.keys()
    for key in sorted(keys):
        print(key)
