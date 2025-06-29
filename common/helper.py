import collections.abc


class Helper:

    def get_data(self, folder):
        raise NotImplementedError('Subclasses must implement this function')

    def find_all_keys_in_folder(self, folder, depth=0, ignored_toplevel_keys: list=None, ignored_keys: list=None):
        keys = {}
        if ignored_toplevel_keys is None:
            ignored_toplevel_keys = []
        if ignored_keys is None:
            ignored_keys = []
        for filename, filedata in self.get_data(folder):
            for toplevelkey, data in filedata:
                if toplevelkey in ignored_toplevel_keys:
                    continue
                if depth == 0:
                    self._update_keys_from_data(data, keys, ignored_keys)
                else:
                    for n2, d2 in data:
                        if depth == 1:
                            if n2 in ignored_toplevel_keys:
                                continue
                            self._update_keys_from_data(d2, keys, ignored_keys)
                        else:
                            for n3, d3 in d2:
                                if depth == 2:
                                    if n3 in ignored_toplevel_keys:
                                        continue
                                    self._update_keys_from_data(d3, keys, ignored_keys)
                                else:
                                    for n4, d4 in d3:
                                        if n4 in ignored_toplevel_keys:
                                            continue
                                        self._update_keys_from_data(d4, keys, ignored_keys)
        print('==Examples==')
        for key, values in sorted(keys.items()):
            print('{}: {}'.format(key, list(values)[:4]))
        print('==Definitions==')
        for key, values in sorted(keys.items()):
            value_types = {v if isinstance(v, type) else type(v) for v in values}
            if len(value_types) == 1:
                print('{}: {}'.format(key, value_types.pop().__name__))
            else:
                print('{}: any  # possible types: {}'.format(key, value_types))

        return keys

    def get_value_for_example(self, value):
        if isinstance(value, collections.abc.Hashable):
            return value
        else:
            return type(value)
    def _update_keys_from_data(self, data, keys, ignored_keys: list):
        if isinstance(data, list):
            for item in data:
                self._update_keys_from_data(item, keys, ignored_keys)
        else:
            for k, v in data:
                if k in ignored_keys:
                    continue
                if k not in keys:
                    keys[k] = set()
                keys[k].add(self.get_value_for_example(v))
