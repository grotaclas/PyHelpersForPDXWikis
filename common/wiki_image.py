import re
import shutil
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Any

from PIL import Image

from common.wiki import WikiTextFormatter


@dataclass
class WikiImageFileReference:
    """There can be multiple references for the same file, possibly with different wiki filenames or different redirects."""
    wiki_filename: str
    category: str
    description: str = ''
    # the main reference is the one whose filename will be used if there are multiple references and
    # the file does not exist on the wiki yet. If the image file is in a folder for images of a specific type,
    # that type should be the main reference. e.g. if a concept uses the icon of a modifier, the modifier is the main
    # reference. If there are multiple modifiers which use the same image, the main reference is the one which name
    # matches the filename
    # there must only be one main reference
    is_main_reference: bool = False

    # for redirects; if one of these contains the image, it should be moved to one of the main filenames
    alternative_filenames: list[str] = field(default_factory=list)

    # these should not be created anymore, but can be used to find an old version of the image which can be moved
    obsolete_filenames: list[str] = field(default_factory=list)

    # the reference is game specific. It can be a path to an actual file or a reference to a texture
    image_reference: Path | Any = None

    # game specific, but usually the sha256 hash over the raw pixel data
    image_data_hash: str = None

    def __post_init__(self):
        self.wiki_filename = WikiTextFormatter.normalize_page_title(self.wiki_filename, False)
        self.alternative_filenames = [WikiTextFormatter.normalize_page_title(filename, False) for filename in self.alternative_filenames]
        normalized_obsolete_filenames = []
        for filename in self.obsolete_filenames:
            normalized_name = WikiTextFormatter.normalize_page_title(filename, False)
            if normalized_name.casefold() != self.wiki_filename.casefold() and normalized_name not in normalized_obsolete_filenames:
                normalized_obsolete_filenames.append(normalized_name)
        self.obsolete_filenames = normalized_obsolete_filenames


@dataclass
class WikiImageFile:
    """
    Groups all WikiImageFileReference which link to the same file.
    There could still be multiple WikiImageFile with the same hash, if the game files have the same image multiple
    times(or images which only differ in mipmaps or file format)
    """
    references: list[WikiImageFileReference]

    # game specific, but usually the sha256 hash over the raw pixel data

    @cached_property
    def image_data_hash(self) -> str:
        return self.references[0].image_data_hash

    @cached_property
    def main_wiki_filename(self):
        main_wiki_filenames = [ref.wiki_filename for ref in self.references if ref.is_main_reference]

        if len(main_wiki_filenames) == 0:
            return self.references[0].wiki_filename
        elif len(main_wiki_filenames) == 1:
            return main_wiki_filenames[0]
        else:
            raise Exception(f'Multiple main filenames {", ".join(main_wiki_filenames)}')


@dataclass
class WikiImage:
    """
    Points multiple WikiImageFile for identical images to the same wiki image
     """

    image_files: list[WikiImageFile]
    license: str = 'C-Paradox'


    @cached_property
    def category(self):
        categories = {ref.category for image_file in self.image_files for ref in image_file.references}
        if len(categories) > 1:
            raise NotImplementedError('TODO: implement handling of multiple categories')
        return categories.pop()

    @cached_property
    def description(self) -> str | None:
        descriptions = []
        for image_file in self.image_files:
            for ref in image_file.references:
                if ref.description and ref.description not in descriptions:
                    descriptions.append(ref.description)
        if descriptions:
            return '\n\n'.join(descriptions)
        else:
            return None

    @cached_property
    def main_wiki_filename(self) -> str:
        if len(self.image_files) > 1:
            raise NotImplementedError('TODO: implement handling of multiple WikiImageFile')
        else:
            return self.image_files[0].main_wiki_filename

    @cached_property
    def image_reference(self) -> Path | Image.Image | Any | None:
        return self.image_files[0].references[0].image_reference

    @cached_property
    def obsolete_filenames(self) -> list[str]:
        return [
            name
            for f in self.image_files
            for ref in f.references
            for name in ref.obsolete_filenames
        ]

    @cached_property
    def alternative_filenames(self) -> list[str]:
        return [
            name
            for f in self.image_files
            for ref in f.references
            for name in ref.alternative_filenames
        ]

    def get_all_possible_wiki_filenames(self) -> list[str]:
        """this includes redirects and obsolete filenames"""
        return [
            name
            for f in self.image_files
            for ref in f.references
            for name in ([ref.wiki_filename] + ref.alternative_filenames + ref.obsolete_filenames)
        ]

    def save_image_as(self, destination_file: Path):
        desired_format = self._get_format(self.main_wiki_filename)
        if isinstance(self.image_reference, Path):
            if self._get_format(self.image_reference) != desired_format:
                self.convert_image(self.image_reference, destination_file, desired_format)
            else:
                shutil.copy(self.image_reference, destination_file)
        elif isinstance(self.image_reference, Image.Image):
            self.image_reference.save(str(destination_file), optimize=True, format=desired_format)
        else:
            raise NotImplementedError(f'Unknown image reference type {type(self.image_reference)}')


    def _get_format(self, filename: str|Path) -> str:
        if isinstance(filename, str):
            filename = Path(filename)
        file_format = filename.suffix.removeprefix('.').upper()
        if file_format == 'JPG':
            file_format = 'JPEG'
        return file_format


    @staticmethod
    def convert_image(source_file: Path, destination_file: Path, file_format: str = 'PNG'):
        with Image.open(source_file) as im:
            im.save(str(destination_file), optimize=True, format=file_format)

    def unify_image_page_text(self, page_text: str):
        if (self.category_is_missing(page_text) or
                self.description_is_missing(page_text) or
                self.license_is_missing(page_text)):
            new_text = f'''== Summary ==
{self.description if self.description else ''}
== Licensing ==
{{{{C-Paradox}}}}
[[Category:{self.category}]]'''
            return new_text
        else:
            return page_text

    def license_is_missing(self, page_text: str) -> bool:
        if re.match(r'\{\{\s*' + self.license + r'\s*}}', page_text, flags=re.IGNORECASE):
            return False
        else:
            return True

    def category_is_missing(self, page_text: str) -> bool:
        if re.match(r'\[\[\s*Category\s*:\s*' + self.category.replace(' ', '[ _]') + r'\s*]]', page_text,
                    flags=re.IGNORECASE):
            return False
        else:
            return True

    def description_is_missing(self, page_text: str) -> bool:
        return self.description and self.description not in page_text