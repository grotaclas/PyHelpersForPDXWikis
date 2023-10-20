import math

from common.wiki import WikiTextFormatter


class CS2WikiTextFormatter(WikiTextFormatter):

    @staticmethod
    def format_distance(number) -> str:
        if number >= 1000:
            number /= 1000
            number = math.floor(number * 100.0) / 100.0
            suffix = ' km'
        else:
            suffix = ' m'
        return f'{number:g}{suffix}'