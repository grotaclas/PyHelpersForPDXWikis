from common.helper import OneTypeHelper
from vic3.game import vic3game
from vic3.parser import Vic3Parser


class Vic3Helper(OneTypeHelper):
    parser: Vic3Parser

    def __init__(self, folder):
        super().__init__(folder)
        self.parser = vic3game.parser

    def get_data(self):
        return self.parser.parser.parse_files(f'{self.folder}/*')


if __name__ == '__main__':
    Vic3Helper('common/power_bloc_principle_groups').print_examples_and_code()