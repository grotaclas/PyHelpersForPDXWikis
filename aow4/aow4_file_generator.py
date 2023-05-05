from aow4.game import aow4game
from aow4.parser import AoW4Parser
from common.file_generator import FileGenerator


class AoW4FileGenerator(FileGenerator):

    parser: AoW4Parser

    def __init__(self):
        super().__init__(aow4game)
