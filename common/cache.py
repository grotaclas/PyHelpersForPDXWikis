import pickle
# import numpy
from functools import wraps


class NoParserPickler(pickle.Pickler):
    """replaces instances of the game's parser with a persistent id,
     because the parser contains references which can't be pickled,
     and it would not be a good idea to pickle the parser anyway.

     NoParserUnpickler can be used to unpickle the data"""

    def __init__(self, file, game):
        super().__init__(file)
        self.game = game

    def persistent_id(self, obj):
        """the only persistent id is the parser"""
        if obj is self.game.parser:
            return 'game.parser', 0
        return None


class NoParserUnpickler(pickle.Unpickler):
    """To unpickle data from NoParserPickler"""

    def __init__(self, file, game):
        super().__init__(file)
        self.game = game

    def persistent_load(self, pid):
        type_tag, key_id = pid
        if type_tag == 'game.parser':
            return self.game.parser
        else:
            # Always raises an error if you cannot return the correct object.
            # Otherwise, the unpickler will think None is the object referenced
            # by the persistent ID.
            raise pickle.UnpicklingError("unsupported persistent object")


class PickleSerializer:

    @staticmethod
    def get_file_extension():
        return 'pkl'

    @staticmethod
    def serialize(data, filename, game):
        with open(filename, 'wb') as cachefile:
            pickler = NoParserPickler(cachefile, game)
            pickler.dump(data)

    @staticmethod
    def deserialize(filename, game):
        with open(filename, 'rb') as cachefile:
            unpickler = NoParserUnpickler(cachefile, game)
            return unpickler.load()


# class NumpySerializer:
#
#     @staticmethod
#     def get_file_extension():
#         return 'npy'
#
#     @staticmethod
#     def serialize(data, filename):
#         numpy.save(filename, data)
#
#     @staticmethod
#     def deserialize(filename):
#         return numpy.load(filename)


def disk_cache(game, serializer=PickleSerializer):
    """Cache the method result on disk

    Warning: the cache assumes that the return value does not change
    as long as the game version stays the same. When changing the code
    of the decorated method, you have to clear the cache manually

    setting CACHEPATH to None disables the cache, but it doesn't clear it
    """
    def decorating_function(f):
        if not game.cachepath:
            return f

        @wraps(f)
        def wrapper(self):
            cachedir_with_module = game.cachepath / f.__module__
            cachedir_with_module.mkdir(parents=True, exist_ok=True)
            cachefile = cachedir_with_module / (f.__name__ + '.' + serializer.get_file_extension())
            if cachefile.exists():
                return serializer.deserialize(cachefile, game)
            else:
                return_value = f(self)
                serializer.serialize(return_value, cachefile, game)
                return return_value
        return wrapper
    return decorating_function
