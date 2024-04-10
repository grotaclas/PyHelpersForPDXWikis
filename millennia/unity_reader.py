import xml.etree.ElementTree as ET
from functools import cached_property

from PIL import Image
from UnityPy.classes import PPtr, Texture2D
from UnityPy.export import SpriteHelper

from common.cache import disk_cache
from common.unity_reader import UnityReader
from millennia.game import millenniagame


class UnityReaderMillennia(UnityReader):
    def __init__(self):
        super().__init__(millenniagame.game_path / 'Millennia_Data', millenniagame, 'Assembly-CSharp.dll')

    @cached_property
    def resource_manager(self):
        for obj in self.env.objects:
            if obj.type.name == 'ResourceManager':
                return obj.read()

    @cached_property
    def resources(self) -> dict[str, PPtr]:
        return {key: ptr for key, ptr in self.resource_manager.m_Container.items()}

    def get_resource_ptrs_by_prefix(self, prefix: str) -> dict[str, PPtr]:
        return {key: ptr for key, ptr in self.resources.items() if key.startswith(prefix)}

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
            if resource_name.lower() != data.name.lower():
                print(f'Warning: resource name "{resource_name}" does not match asset name "{data.name}" in path "{path}"')
            if path not in text_by_path:
                text_by_path[path] = {}
            if data.name in text_by_path[path]:
                print(f'Warning: duplicate text asset "{data.name}" with path "{path}"')
            text_by_path[path][data.name] = data.text
        return text_by_path

    @cached_property
    @disk_cache(game=millenniagame)
    def localizations(self):
        localizations = {}
        unresolved_imports = {}
        for path, texts in self.text_asset_resources.items():
            if path.startswith('text/en_us'):
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
        if path not in self.resources:
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
        if path in self.resources:
            sprite = self.resources[path].read()
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
