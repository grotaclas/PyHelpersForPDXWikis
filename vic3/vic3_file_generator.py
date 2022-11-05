from common.file_generator import FileGenerator
from vic3.game import vic3game
from vic3.parser import Vic3Parser


class Vic3FileGenerator(FileGenerator):

    parser: Vic3Parser

    def __init__(self):
        super().__init__(vic3game)
