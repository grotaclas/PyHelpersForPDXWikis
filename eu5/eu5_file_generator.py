from functools import cached_property

from common.file_generator import FileGenerator
from eu5.game import eu5game
from eu5.parser import Eu5Parser
from eu5.text_formatter import Eu5WikiTextFormatter


class Eu5FileGenerator(FileGenerator):

    parser: Eu5Parser

    def __init__(self):
        super().__init__(eu5game)

    def localize(self, key: str, default: str = None) -> str:
        return self.parser.localize(key, default)

    @cached_property
    def formatter(self) -> Eu5WikiTextFormatter:
        return self.parser.formatter
