"""
    Runs all the generators from the generate_X.py files

    This is about twice as fast as running them separately,
    because they share the parser, so that its cached_properties
    don't have to be calculated again
"""
import sys
from eu5.generate_cargo_data import CargoDataGenerator
from eu5.generate_csv import Eu5CSVGenerator
from eu5.generate_lua_data import LuaDataGenerator
from eu5.generate_one_time_data import OneTimeGenerator
from eu5.generate_tables import TableGenerator

if __name__ == '__main__':
    print('Running CargoDataGenerator...')
    CargoDataGenerator().run(sys.argv)
    print('Running LuaDataGenerator...')
    LuaDataGenerator().run(sys.argv)
    print('Running TableGenerator...')
    TableGenerator().run(sys.argv)
    print('Running OneTimeGenerator...')
    OneTimeGenerator().run(sys.argv)
    print('Running Eu5CSVGenerator...')
    Eu5CSVGenerator().run(sys.argv)
