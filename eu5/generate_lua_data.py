"""

Generates lua data modules

"""
import luadata
import sys

from eu5.eu5_file_generator import Eu5FileGenerator


class LuaDataGenerator(Eu5FileGenerator):
    def generate_defines_list_lua(self) -> str:
        """
        generates https://eu5.paradoxwikis.com/Module:Defines/List

        """
        result = self.parser.defines.to_dict()
        return f'''
local NDefines = {luadata.serialize(result, indent=' ')}

return NDefines
'''


if __name__ == '__main__':
    LuaDataGenerator().run(sys.argv)
