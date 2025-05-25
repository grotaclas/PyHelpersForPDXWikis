from common.file_generator import FileGenerator
from eu5.game import eu5game
from eu5.parser import Eu5Parser


class Eu5FileGenerator(FileGenerator):

    parser: Eu5Parser

    def __init__(self):
        super().__init__(eu5game)
