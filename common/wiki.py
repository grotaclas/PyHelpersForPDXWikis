import math


class WikiTextFormatter:
    @staticmethod
    def format_big_number(number) -> str:
        suffixes = {
            1000*1000*1000: 'B',
            1000*1000: 'M',
            1000: 'K',
        }
        for threshold, suffix in suffixes.items():
            if number > threshold:
                number /= threshold
                number = math.floor(number * 100.0) / 100.0
                return f'{number}{suffix}'
        # below 1k
        return str(number)

    @staticmethod
    def create_wiki_list(elements: list[str], indent=1, no_list_with_one_element=False) -> str:
        if len(elements) == 0:
            return ''
        elif len(elements) == 1 and no_list_with_one_element:
            return elements[0]
        else:
            line_prefix = '*' * indent
            return f'\n{line_prefix} ' + f'\n{line_prefix} '.join(elements)

    @staticmethod
    def add_red_green(number, positive_is_good: bool = True, add_plus: bool = False, add_percent: bool = False) -> str:
        if not isinstance(number, (int, float)):
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
            formatted_number = str(number)

        if bold:
            formatted_number = f"'''{formatted_number}'''"

        return formatted_number

    def format_percent(self, number, add_plus_minus: bool = False):
        number = number * 100
        number = round(number, 2)
        if add_plus_minus:
            return self.add_plus_minus(number) + '%'
        else:
            return f'{number:g}%'

    @staticmethod
    def quote(text):
        return f"''“{text}”''"

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
