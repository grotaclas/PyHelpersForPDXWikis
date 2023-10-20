from cs2.game import cs2game
from cs2.parser import CS2Parser
from common.file_generator import FileGenerator


class CS2FileGenerator(FileGenerator):

    parser: CS2Parser

    def __init__(self):
        super().__init__(cs2game)
