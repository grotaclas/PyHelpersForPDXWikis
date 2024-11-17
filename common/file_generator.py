import inspect
import sys
from numbers import Number

from common.paradox_lib import Game
from common.wiki import WikiTextFormatter
from pyradox.filetype.table import make_table, WikiDialect


try:  # when used by PyHelpersForPDXWikis
    from PyHelpersForPDXWikis.localsettings import OUTPATH
except:  # when used by ck2utils
    from localpaths import outpath
    OUTPATH = outpath


class FileGenerator:
    name_of_this_tool = 'PyHelpersForPDXWikis'

    def __init__(self, game: Game):
        self.game = game
        self.parser = game.parser

        self.outpath = OUTPATH / game.short_game_name / game.version
        if not self.outpath.exists():
            self.outpath.mkdir(parents=True)

    def run(self, command_line_args):
        """call all generators which were specified on the command line or all if none were specified"""
        if len(command_line_args) > 1:
            for arg in command_line_args[1:]:
                method_name = 'generate_' + arg
                if hasattr(self, method_name):
                    self._write_text_file(arg, getattr(self, method_name)())
                else:
                    print('Method {} not found in {}'.format(method_name, self.__class__.__name__))
        else:
            for method_name, method in inspect.getmembers(self):
                if method_name.startswith('generate_'):
                    if len(inspect.signature(method).parameters) == 0:  # skip functions which require a parameter
                        self._write_text_file(method_name.removeprefix('generate_'), method())

    def _write_text_file(self, name: str, content: str | list | dict):
        if isinstance(content, dict):
            for name_suffix, data in content.items():
                self._really_write_file(f'{name}_{name_suffix}', data)
        elif isinstance(content, list):
            self._really_write_file(name, '\n'.join(content))
        else:
            self._really_write_file(name, content)

    def _really_write_file(self, name: str, content: str):
        output_file = self.outpath / '{}{}.txt'.format(self.game.short_game_name, name)
        with output_file.open('w', encoding='utf-8') as f:
            f.write(content)

    def _write_lines_to_text_file(self, name: str, lines: list[str]):
        self._write_text_file(name, '\n'.join(lines))

    def make_wiki_table(self, data, column_specs=None, table_style='', sortable=True, one_line_per_cell=False,
                        merge_identical_cells_in_column=False, remove_empty_columns=False, row_id_key=None, **kwargs):
        class dialect(WikiDialect):
            pass
        dialect.row_cell_begin = lambda s: ''

        if one_line_per_cell:
            dialect.row_cell_delimiter = '\n| '
        else:
            dialect.row_cell_delimiter = ' || '

        if row_id_key is None:
            dialect.row_begin = '| '
            dialect.row_delimiter = '|-\n'
        else:
            dialect.row_begin = lambda row: f'|- id="{row[row_id_key]}"\n| '
            dialect.row_delimiter = '\n'

        if remove_empty_columns:
            for key in list(data[0].keys()):
                is_empty = True
                for row in data:
                    value = row[key]
                    if isinstance(value, Number):
                        if value != 0:
                            is_empty = False
                            break
                    else:
                        if not isinstance(value, str):
                            value = str(value)
                        if value.strip() != '':
                            is_empty = False
                            break
                if is_empty:
                    for row in data:
                        del row[key]

        if column_specs is None:
            column_specs = self.get_column_specs(data, row_id_key)

        if isinstance(data, list):
            data = dict(zip(range(len(data)), data))

        if merge_identical_cells_in_column:
            row_count = len(data)
            for i in range(row_count - 1):
                for key, column_spec in column_specs:
                    if key in data[i]:
                        same_rows = 0
                        while i+same_rows+1<row_count and data[i][key] == data[i+same_rows+1][key]:
                            del data[i+same_rows+1][key]
                            same_rows += 1
                        if same_rows > 0:
                            if ' | ' in data[i][key]:
                                separator = ' '
                            else:
                                separator = ' | '
                            data[i][key] = f'rowspan="{same_rows+1}"{separator}{data[i][key]}'

        return make_table(data, dialect, column_specs=column_specs, table_style=table_style, sortable=sortable, **kwargs)

    @staticmethod
    def get_column_specs(data, row_id_key=None):
        """generate a simple column specs for the table generator. All keys of the data array are used as table headers"""
        return [(k, '%%(%s)s' % k) for k in data[0].keys() if k != row_id_key]

    @staticmethod
    def warn(message: str):
        print('WARNING: {}'.format(message), file=sys.stderr)

    def get_SVersion_header(self, scope=None):
        """generate a SVersion wiki template for the current version

        for example {{SVersion|1.33}}

        @param scope a string which is used as the second parameter to the template
        @see https://eu4.paradoxwikis.com/Template:SVersion
        """
        version_header = '{{SVersion|' + self.get_version_string_for_version_tag()
        if scope:
            version_header += '|' + scope
        version_header += '}}'
        return version_header

    def get_version_header(self):
        """generate a Version wiki template for the current version

        for example {{Version|1.33}}
        """
        return '{{Version|' + self.get_version_string_for_version_tag() + '}}'

    def get_version_string_for_version_tag(self):
        """includes handling for pre-release versions"""
        if self.game.is_pre_release_version():
            version = 'pre-release'
        else:
            version = self.game.major_version
        return version

    @staticmethod
    def create_wiki_list(elements: list[str], indent=1, format_with_icon=False) -> str:
        return WikiTextFormatter.create_wiki_list(elements, indent, format_with_icon=format_with_icon)

    def surround_with_autogenerated_section(self, section_name, contents, generator=name_of_this_tool, add_version_header=False, custom_warning_message: str = None):
        if isinstance(contents, list):
            contents = '\n'.join(contents)

        # tables and lists need a linebreak before them. Otherwise avoid linebreaks, because additional linebreaks can lead to unwanted whitespace
        if contents.startswith('{|') or contents.startswith('*'):
            contents = '\n' + contents
        full_section_name = 'autogenerated_' + section_name
        if generator != self.name_of_this_tool:
            with_generator = f' with {generator}'
        else:
            with_generator = ''
        if add_version_header:
            version_tag = self.get_SVersion_header()
        else:
            version_tag = ''
        if custom_warning_message is None:
            warning_message = 'Please suggest changes on the talk page, because all manual changes will be overwritten by the next update!'
        else:
            warning_message = custom_warning_message
        new_contents_with_sections = f'''<section begin={full_section_name}/><!--
    Everything in this section is generated{with_generator} and automatically uploaded with {self.name_of_this_tool}
    {warning_message} 
-->{version_tag}{contents}<section end={full_section_name}/>'''
        return new_contents_with_sections
