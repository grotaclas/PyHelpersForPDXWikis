"""ParadoxParser is a class to parse paradox development studio game scripts into python objects.

Key value pairs get converted into the Tree class which is a thin wrapper around a dict with helper functions.

The parsing is done with the rakaly command line tool (https://github.com/rakaly/cli), because it is very fast and
supports more quirks of the format than existing python tools. The location of rakaly must be configured with the
constant RAKALY_CLI in localsettings.py """
import json
import os
import re
import subprocess
from pathlib import Path
from collections.abc import MutableMapping
from tempfile import mkstemp
from typing import Callable, Any, Iterator

try:  # when used by PyHelpersForPDXWikis
    from PyHelpersForPDXWikis.localsettings import RAKALY_CLI
except:  # when used by ck2utils
    RAKALY_CLI = ''


class ParsingWorkaround:
    """Workarounds to change files into a format which rakaly can parse. They are only needed in rare cases.

    The actual workarounds are in subclasses
    """
    replacement_regexes: dict[str, str]

    def apply_to_string(self, file_contents):
        for pattern, replacement in self.replacement_regexes.items():
            file_contents = re.sub(pattern, replacement, file_contents)
        return file_contents


class UnmarkedListWorkaround(ParsingWorkaround):
    """replaces statements like
        pattern = list "christian_emblems_list"
    with
        pattern = { list "christian_emblems_list" }
    """
    replacement_regexes = {r'(=\s*)(list\s+[^#{}=\n]+)': r'\1{ \2 }'}


class QuestionmarkEqualsWorkaround(ParsingWorkaround):
    """replaces statements like
        x ?= y
    with
        x = y"""
    replacement_regexes = {r' \?= ': ' = '}


class IgnoreAtVariablesWorkaround(ParsingWorkaround):
    """ignores lines which start with code like
        @abc = 123
    """
    replacement_regexes = {r'(?m)^\s*@[a-zA-Z]+[^\n]*\n?': ''}


class ScriptedWorkaround(ParsingWorkaround):
    """
    replaces
        scripted_effect minor_earthquake_payment = {
    with
        scripted_effect = { id = minor_earthquake_payment
    """
    replacement_regexes = {
        r'(?m)^scripted_(effect|trigger)\s+([^\s={}#]+)\s*=\s*\{': r'scripted_\1 = { id = \2',
    }


class ParadoxParser:
    """the parse_ methods parse paradox development studio game scripts into python objects"""

    def __init__(self, base_folder: Path):
        """
        Args:
             base_folder: the base for the files which will be parsed. The various parse_ methods expect
                            their parameters to be relative to this base_folder
        """
        self.base_folder = base_folder

    def parse_files(self, glob: str, workarounds: list[ParsingWorkaround] = None) -> Iterator[tuple[Path, 'Tree']]:
        """Generator to parse all files which match the glob with rakaly. The files are parsed in alphabetical order.

        If there are duplicate keys, their values will be grouped into a list(rakaly --duplicate-keys group).
        Such a list can be unwrapped with Tree.find_all() or merged with Tree.merge_duplicate_keys().

        Args:
            glob: a file pattern which is relative to the base_folder. See pathlib.Path.globs for the supported format
            workarounds: workarounds to apply before handling the file to rakaly

        Returns:
            An iterator over tuples of the file path and a Tree with the result
        """
        for file in sorted(self.base_folder.glob(glob)):
            yield file, self._really_parse_file(file, workarounds)

    def parse_folder_as_one_file(self, folder: str, recursive=True, file_extension='txt',
                                 workarounds: list[ParsingWorkaround] = None,
                                 overwrite_duplicate_keys_at_level: int|None = 0,
                                 ) -> 'Tree':
        """Parse all text files in a folder with rakaly and merge them into one Tree.

        If there are duplicate keys, their values will be grouped into a list(rakaly --duplicate-keys group).
        Such a list can be unwrapped with Tree.find_all() or merged with Tree.merge_duplicate_keys().

        Args:
            folder: the folder to parse
            recursive: parse subfolders as well
            file_extension: only files with this extension will be parsed
            workarounds: workarounds to apply before handling the file to rakaly
            overwrite_duplicate_keys_at_level: how to handle duplicate top level keys from different files. If this
                is set to 0, later files will overwrite the keys from previous files. If set to None, the behavior
                depends on the value of the key. If it is a Tree, it will be merged (overwriting keys in that tree if
                there are duplications) If it is a list, the new value will be appended. Otherwise, it will be turned
                into a list. If set to a number above 0, overwriting will start at that level

        Returns:
            the merged Tree
        """
        result = Tree({})
        glob = '*.' + file_extension
        if recursive:
            glob = '**/' + glob
        glob = f'{folder}/{glob}'
        for file in sorted(self.base_folder.glob(glob)):
            if overwrite_duplicate_keys_at_level == 0:
                result.dictionary.update(self._really_parse_file(file, workarounds).dictionary)
            else:
                for key, value in self._really_parse_file(file, workarounds):
                    if key in result.dictionary:
                        if isinstance(result.dictionary[key], Tree):
                            result.dictionary[key].update(value, (overwrite_duplicate_keys_at_level - 1) if overwrite_duplicate_keys_at_level is not None else None)
                        elif isinstance(result.dictionary[key], list):
                            result.dictionary[key].append(value)
                        else:
                            result.dictionary[key] = [result.dictionary[key], value]
                    else:
                        result.dictionary[key] = value
        return result

    def parse_file(self, relative_path: str, workarounds: list[ParsingWorkaround] = None) -> 'Tree':
        """Parse one file into a Tree with rakaly

        If there are duplicate keys, their values will be grouped into a list(rakaly --duplicate-keys group).
        Such a list can be unwrapped with Tree.find_all() or merged with Tree.merge_duplicate_keys().

        Args:
            relative_path: path of the file relative to the base_folder
            workarounds: workarounds to apply before handling the file to rakaly

        Returns:
            the parsed file as a Tree
        """
        return self._really_parse_file(self.base_folder / relative_path, workarounds)

    def _really_parse_file(self, file: Path, workarounds: list[ParsingWorkaround] = None) -> 'Tree':
        if workarounds:
            with open(file, encoding='utf-8-sig') as fp:
                contents = fp.read()
            for workaround in workarounds:
                contents = workaround.apply_to_string(contents)
            fp, temp_filename = mkstemp(prefix='paradox_parser_workaround', suffix='.txt')
            try:
                with os.fdopen(fp, mode='w', encoding='utf-8') as temp_file:
                    temp_file.write(contents)
                return self._run_rakaly(Path(temp_filename))
            finally:
                os.remove(temp_filename)
        else:
            return self._run_rakaly(file)

    def _run_rakaly(self, file: Path):
        rakaly_result = subprocess.run([RAKALY_CLI, 'json', '--format', 'utf-8', '--interpolation', '--duplicate-keys', 'preserve', file], capture_output=True)
        if rakaly_result.returncode != 0:
            rakaly_error_message = str(rakaly_result.stderr, 'UTF-8')[:-1]  # [:-1] removes the final linebreak
            raise Exception('Error reading "{}": {}'.format(file, rakaly_error_message))
        return self.json_to_tree(rakaly_result.stdout)

    def parse_ordered_pairs_into_tree(self, ordered_pairs) -> 'Tree|TreeWithDuplicates':
        """
        Returns a Tree from the ordered pairs

        if there are duplicate keys, it returns a TreeWithDuplicates instead
        in this case, the Tree gets both a dict and the ordered_pairs. In the dict,
        the values for duplicate keys are turned into a list. But this does not preserve
        the order of the duplicate keys. If these are needed,, the ordered_pairs in
        TreeWithDuplicates have to be used
        """
        pairs_as_dict = {}
        # keep track of duplicate keys, both to determine if there are duplicates
        # and to know if the values of the duplicate key have already been turned into
        # a list. We can't check the type of the value, because the value could have been a list to begin with
        seen_duplicates = set()
        for key, value in ordered_pairs:
            if key in pairs_as_dict:
                if key in seen_duplicates:
                    pairs_as_dict[key].append(value)
                else:
                    pairs_as_dict[key] = [pairs_as_dict[key], value]
                    seen_duplicates.add(key)
            else:
                pairs_as_dict[key] = value

        if len(seen_duplicates) > 0:
            return TreeWithDuplicates(pairs_as_dict, ordered_pairs)
        else:
            return Tree(pairs_as_dict)


    def json_to_tree(self, json_string: str) -> 'Tree':
        return json.loads(json_string, object_pairs_hook=self.parse_ordered_pairs_into_tree)


class Tree(MutableMapping):
    """A wrapper around dict with some helper functions"""


    def __init__(self, dictionary: dict):
        self.dictionary = dictionary

    def __getitem__(self, key):
        return self.dictionary[key]

    def __delitem__(self, key):
        del self.dictionary[key]

    def __setitem__(self, key, value):
        self.dictionary[key] = value

    def __len__(self) -> int:
        return len(self.dictionary)

    def __iter__(self) -> Iterator:
        """iterates over the items of the dictionary.

        This is the same as Tree.dictionary.items(), but it avoids the items() call for the common case
        that we want to iterate over the items.
        """
        return iter(self.dictionary.items())

    def iterate_with_duplicates(self) -> Iterator[tuple[str, Any]]:
        """iterates over the items in this tree as tuples of key value pairs

        Keys can appear multiple times and are preserved in the order which they had in the file.
        In contrast, the default __iter__() turns the value of duplicate keys into lists. But this
        makes them appear together even if the there were other keys inbetween

        this is the basic implementation for the case that there are no duplicate keys.
        Subclasses with duplicate keys must override this
        """
        return self.__iter__()

    def keys(self):
        return self.dictionary.keys()

    def get_or_default(self, key: str, default: Any):
        """Return the value for the given key or the default if the key is not in this Tree"""
        if key in self.dictionary:
            return self.dictionary[key]
        else:
            return default

    def find_all(self, search_key: str) -> Iterator:
        """Iterates over the values for this search_key.

        This is most useful for files which may or may not contain the same key multiple times
        """
        if search_key not in self.dictionary:
            return
        if isinstance(self.dictionary[search_key], list):
            for entry in self.dictionary[search_key]:
                yield entry
        else:
            yield self.dictionary[search_key]

    def find_all_recursively(self, search_key: str) -> Iterator:
        """Like find_all, but searches the whole Tree recursively"""
        for key, value in self.dictionary.items():
            if key == search_key:
                if isinstance(value, list):
                    for entry in value:
                        yield entry
                else:
                    yield value
            elif isinstance(value, Tree):
                yield from value.find_all_recursively(search_key)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, Tree):
                        yield from item.find_all_recursively(search_key)

    def find_all_recursively_with_parents(self, search_key: str, parents: list[str] = None) -> Iterator[tuple[list[str], Any]]:
        """Like find_all_recursively, but also returns the keys which were descended to find the search term"""
        if parents is None:
            parents = []
        for key, value in self.iterate_with_duplicates():
            if key == search_key:
                yield parents, value,
            elif isinstance(value, Tree):
                yield from value.find_all_recursively_with_parents(search_key, parents + [key])
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, Tree):
                        yield from item.find_all_recursively_with_parents(search_key, parents + [key])

    def merge_duplicate_keys(self):
        """merges duplicate keys which have Tree as their value

        if the values have duplicate keys, the last one will overwrite the previous ones
        @TODO: it might be useful to change this
        """
        for key, value in self.dictionary.items():
            if isinstance(value, list) and len(value) > 0 and isinstance(value[0], Tree):
                merged = Tree({})
                for item in value:
                    merged.dictionary.update(item.dictionary)
                self.dictionary[key] = merged
        return self

    def filter_elements(self, filter_func: Callable[[str, Any], bool]) -> 'Tree':
        """create a new tree which only contains the elements for which filter_func returns True"""
        return Tree({k: v for k, v in self.dictionary.items() if filter_func(k, v)})

    def update(self, other: 'Tree', overwrite_duplicate_keys_at_level: int|None = None) -> 'Tree':
        """Update the tree with the key/value pairs from other. Existing keys are handled depending on the type
        of the value:

        Tree/MutableMapping: the value from this tree is updated with the value from the other tree.
        list: the value from this tree is extended with the value from the other tree.
        everything else: the value from the other tree overwrites the value from this tree"""

        for key, value in other:
            if key in self and overwrite_duplicate_keys_at_level != 0:
                if isinstance(value, Tree):
                    if isinstance(self[key], Tree):
                        self[key].update(value,  (overwrite_duplicate_keys_at_level - 1) if overwrite_duplicate_keys_at_level is not None else None)
                    elif isinstance(self[key], list) and len(self[key]) == 0:
                        self[key] = value
                    elif isinstance(self[key], list) and isinstance(self[key][0], Tree):
                        self[key].append(value)
                    else:
                        raise Exception(f'mismatching types for key "{key}" when updating tree. The value from this tree is a "{type(self[key])}" and the value from the other tree is a "{type(value)}".')
                elif isinstance(value, MutableMapping):
                    if isinstance(self[key], MutableMapping):
                        self[key].update(value)
                    else:
                        raise Exception(f'mismatching types for key "{key}" when updating tree. The value from this tree is a "{type(self[key])}" and the value from the other tree is a "{type(value)}".')
                elif isinstance(value, list) and isinstance(self[key], list):
                    self[key].extend(value)
                elif isinstance(value, list):
                    new_value = value.copy()
                    new_value.append(self[key])
                    self[key] = new_value
                elif isinstance(self[key], list):
                    self[key].append(value)
                elif value is None and self[key] is not None:
                    pass
                else:
                    self.dictionary[key] = value
            else:
                self.dictionary[key] = value
        return self

    def __getstate__(self):
        return self.dictionary

    def __setstate__(self, state):
        self.dictionary = state

    def _to_dict_one_value(self, value: Any) -> Any:
        if isinstance(value, Tree):
            return value.to_dict()
        elif isinstance(value, list):
            return [self._to_dict_one_value(v) for v in value]
        else:
            return value

    def to_dict(self) -> dict:
        """recursively convert the tree into a dict"""
        return {k: self._to_dict_one_value(v) for k, v in self}

    def _lowercase(self, obj):
        """ Make dictionary lowercase
            from: https://stackoverflow.com/a/40789531
         """
        if isinstance(obj, dict):
            return {k.lower(): self._lowercase(v) for k, v in obj.items()}
        elif isinstance(obj, (list, set, tuple)):
            t = type(obj)
            return t(self._lowercase(o) for o in obj)
        elif isinstance(obj, str):
            return obj.lower()
        else:
            return obj

    def is_equal_to_dict(self, comparison_dict: dict, case_sensitive = False) -> bool:
        self_dict = self.to_dict()
        if not case_sensitive:
            self_dict = self._lowercase(self_dict)
            comparison_dict = self._lowercase(comparison_dict)
        return self_dict == comparison_dict


class TreeWithDuplicates(Tree):

    def __init__(self, dictionary: dict, ordered_pairs: list[tuple[str, Any]]):
        super().__init__(dictionary)
        self.ordered_pairs = ordered_pairs

    def __delitem__(self, key):
        super().__delitem__(key)
        self.ordered_pairs = [(k, v) for k, v in self.ordered_pairs if k != key]

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self.ordered_pairs.append((key, value))

    def __getstate__(self):
        return self.dictionary, self.ordered_pairs

    def __setstate__(self, state):
        self.dictionary, self.ordered_pairs = state

    def iterate_with_duplicates(self) -> Iterator[tuple[str, Any]]:
        """iterates over the items in this tree as tuples of key value pairs

        Keys can appear multiple times and are preserved in the order which they had in the file.
        In contrast, the default __iter__() turns the value of duplicate keys into lists. But this
        makes them appear together even if the there were other keys inbetween
        """
        return iter(self.ordered_pairs)

    def update(self, other: 'Tree', overwrite_duplicate_keys_at_level: int|None = None) -> 'Tree':
        if isinstance(other, TreeWithDuplicates):
            self.ordered_pairs.extend(other.ordered_pairs)
        else:
            for key, value in other:
                self.ordered_pairs.append((key, value))
        return super().update(other, overwrite_duplicate_keys_at_level)
