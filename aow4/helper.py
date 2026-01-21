from aow4.parser import AoW4Parser
from common.helper import OneTypeHelper


class Aow4Helper(OneTypeHelper):

    def __init__(self, folder):
        super().__init__(folder)
        self.parser = AoW4Parser()

    def get_data(self):
        return {self.folder: self.parser.read_json(self.folder)}


if __name__ == '__main__':
    Aow4Helper('Tomes').print_examples_and_code()
