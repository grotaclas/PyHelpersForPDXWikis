from io import BufferedReader
from leb128 import u
from PyHelpersForPDXWikis.localsettings import CS2DIR


class CS2Localization:
    """Implementation of the custom localization format of Cities Skylines II"""

    # allows the overriding of localization strings
    localizationOverrides = {}

    def __init__(self, locale='en-US'):
        self.locale = locale
        self._data_loaded = False

    def _load_data(self):
        path = CS2DIR / 'Cities2_Data' / 'StreamingAssets' / 'Data~' / (self.locale + '.loc')
        with path.open('rb') as file:

            # I'm not sure what this is used for. It seems to always be one. Maybe it is a format type
            self.file_header = self._read_int(file, 16)
            self.locale_name_en = self._read_string(file)
            locale_id = self._read_string(file)
            if locale_id != self.locale:
                raise Exception(f'expected locale "{self.locale}", but the file has "{locale_id}" instead')
            self.locale_name_localized = self._read_string(file)

            localization_count = self._read_int(file, 32)
            localization_dict = {}
            for i in range(localization_count):
                key = self._read_string(file)
                value = self._read_string(file)
                if key in localization_dict:
                    raise Exception(f'duplicate localization key "{key}". Previous localization was "{localization_dict[key]}", new localization is "{value}"')
                localization_dict[key] = value

            index_counts = self._read_int(file, 32)
            index_count_dict = {}
            for i in range(index_counts):
                key = self._read_string(file)
                value = self._read_int(file, 32)
                index_count_dict[key] = value

        self._localization_dict = localization_dict
        self._index_count_dict = index_count_dict
        self._data_loaded = True

    @staticmethod
    def _read_string(file: BufferedReader):
        length, _read_bytes = u.decode_reader(file)
        return file.read(length).decode('utf8')

    @staticmethod
    def _read_int(file: BufferedReader, bits: int = 8):
        return int.from_bytes(file.read(bits // 8), 'little')

    def get_localization_dict(self):
        if not self._data_loaded:
            self._load_data()
        return self._localization_dict

    def get_index_count_dict(self):
        if not self._data_loaded:
            self._load_data()
        return self._index_count_dict

    @staticmethod
    def get_full_localization_key(group: str, loc_id: str, loc_sub_id: str = None, index: int = None) -> str:
        key = f'{group}.{loc_id}'
        if loc_sub_id is not None:
            key += f'[{loc_sub_id}]'
        if index is not None:
            key += f':{index}'
        return key

    def localize(self, group: str, loc_id: str, loc_sub_id: str = None, default: str = None, index: int = None) -> str:
        """localize the key from the cities skylines II localization files

        A localization key is compromised of a group, followed by a dot, followed by the loc_id,
        optionally followed by [local_sub_id], optionally followed by colon
        if the key is not found, the default is returned
        unless it is None in which case the key is returned
        """
        key = self.get_full_localization_key(group, loc_id, loc_sub_id, index)
        if default is None:
            default = key

        if key in self.localizationOverrides:
            return self.localizationOverrides[key]
        else:
            return self.get_localization_dict().get(key, default)

    def get_indexed_localizations(self, group: str, loc_id: str, loc_sub_id: str = None, default: str = None) -> [str]:
        """Indexed localizations have multiple options for the same localization key

        These can be items which are naturally indexed like Progression.MILESTONE_NAME and Common.MONTH
        or list of possible options like Assets.CITIZEN_SURNAME_HOUSEHOLD and Chirper.HOUSING_SHORTAGE"""
        key = self.get_full_localization_key(group, loc_id, loc_sub_id)
        if key not in self.get_index_count_dict():
            raise Exception(f'The key "{key}" is not an indexed localization')
        return [self.localize(f'{key}:{i}', default) for i in range(self.get_index_count_dict()[key])]
