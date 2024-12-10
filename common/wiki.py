from decimal import Decimal

import math
from typing import List


class WikiTextFormatter:
    roman_letters = (('M', 1000),
                     ('CM', 900),
                     ('D', 500),
                     ('CD', 400),
                     ('C', 100),
                     ('XC', 90),
                     ('L', 50),
                     ('XL', 40),
                     ('X', 10),
                     ('IX', 9),
                     ('V', 5),
                     ('IV', 4),
                     ('I', 1))

    @staticmethod
    def format_big_number(number, suffixes: List[str] = None) -> str:
        if not suffixes:
            suffixes = ['K', 'M', 'B']
        suffix_map = {
            1000*1000*1000: suffixes[2],
            1000*1000: suffixes[1],
            1000: suffixes[0],
        }
        for threshold, suffix in suffix_map.items():
            if number > threshold:
                number /= threshold
                number = math.floor(number * 100.0) / 100.0
                return f'{number}{suffix}'
        # below 1k
        return str(number)

    @staticmethod
    def create_wiki_list(elements: list[str], indent=1, no_list_with_one_element=False, prefix_with_linebreak=True, format_with_icon=False) -> str:
        if len(elements) == 0:
            return ''
        elif len(elements) == 1 and no_list_with_one_element:
            return elements[0]
        else:
            line_prefix = '*' * indent
            results = []
            if prefix_with_linebreak:
                results.append('')
            for element in elements:
                if isinstance(element, list):
                    results.append(WikiTextFormatter.create_wiki_list(element, indent+1, prefix_with_linebreak=False, format_with_icon=format_with_icon))
                else:
                    if not isinstance(element, str):
                        if format_with_icon:
                            element = element.get_wiki_link_with_icon()
                        else:
                            element = str(element)
                    results.append(f'{line_prefix} {element}')
            return f'\n'.join(results)

    @staticmethod
    def add_red_green(number, positive_is_good: bool = True, add_plus: bool = False, add_percent: bool = False) -> str:
        if not isinstance(number, (int, float, Decimal)):
            return str(number)

        if number == 0:
            return f"'''{number}'''"
        if number > 0:
            if positive_is_good:
                color = 'green'
            else:
                color = 'red'
            if add_plus:
                number = f'+{number}'
        else:
            # add the unicode minus sign
            number = f'−{abs(number)}'
            if positive_is_good:
                color = 'red'
            else:
                color = 'green'
        return f'{{{{{color}|{number}}}}}'

    @staticmethod
    def add_plus_minus(number, bold: bool = False) -> str:
        if number > 0:
            formatted_number = f'+{number:g}'
        elif number < 0:
            formatted_number = f'−{abs(number):g}'
        else:
            formatted_number = f'{number:g}'

        if bold:
            formatted_number = f"'''{formatted_number}'''"

        return formatted_number

    @staticmethod
    def add_minus(number) -> str:
        """add the unicode minus sign if the number is negative"""
        if number < 0:
            return f'−{abs(number):g}'
        else:
            return f'{number:g}'


    def format_percent(self, number, add_plus_minus: bool = False):
        number = number * 100
        number = round(number, 2)
        if add_plus_minus:
            return self.add_plus_minus(number) + '%'
        else:
            return f'{number:g}%'

    @staticmethod
    def format_yes_no(boolean: bool):
        if boolean:
            return '{{icon|yes}}'
        else:
            return '{{icon|no}}'

    @staticmethod
    def quote(text):
        return f"''“{text}”''"

    @staticmethod
    def join_with_comma_and_or(elements: list, seperator=', ', conjunction=" ''or'' ") -> str:
        """joins a list with separator, but the last two elements are joined with the conjunction"""
        n = len(elements)
        if n > 1:
            return (('{}' + seperator) * (n - 2) + '{}' + conjunction + '{}').format(*elements)
        elif n > 0:
            return elements[0]
        else:
            return ''

    @staticmethod
    def uc_first(text: str):
        if len(text) > 0:
            return text[0].upper() + text[1:]
        else:
            return text

    @staticmethod
    def lc_first(text: str):
        if len(text) > 0:
            return text[0].lower() + text[1:]
        else:
            return text

    def format_roman(self, number: int) -> str:
        """convert an integer to a roman number"""

        result = ""
        for numeral, integer in self.roman_letters:
            while number >= integer:
                result += numeral
                number -= integer
        return result


# the rest of the file is an unfinished version of a better wiki-table generator
class Cell:

    def __init__(self, column_header, contents):
        self.column_header = column_header
        self.contents = contents


class Row:
    def __init__(self, cells=None):
        self.cells = {}
        if cells:
            for column_header, contents in cells.items():
                self.cell(column_header, contents)

    def cell(self, column_header, contents):
        new_cell = Cell(column_header, contents)
        self.cells[column_header] = new_cell
        return new_cell


class Table:

    def __init__(self, data=None):
        self.rows = []
        if data:
            for row in data:
                self.row(row)

    def row(self, cells=None):
        new_row = Row(cells)
        self.rows.append(new_row)
        return new_row

    def format(self):
        table_string = self.format_headers()

    def format_headers(self):
        pass
