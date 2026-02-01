"""

generates list and other things which are not run regularly, but which might come in handy again

"""
import itertools
import re
import sys
from collections import Counter

from eu5.eu5_file_generator import Eu5FileGenerator


class OneTimeGenerator(Eu5FileGenerator):

    def generate_northern_court_country_list(self):
        return self.create_wiki_list([
            country.display_name
            for country in self.parser.countries.values()
            if country.has_flag('supports_northern_court')])

    def generate_southern_court_country_list(self):
        return self.create_wiki_list([
            country.display_name
            for country in self.parser.countries.values()
            if country.has_flag('supports_southern_court')])

    def generate_modifier_counts(self):
        ignored_paths = [
            'in_game/common/*localization*',
            'in_game/common/attribute_columns',
            'in_game/common/ethnicities',
            'in_game/common/genes',
            'main_menu/common/modifier_icons',
            'main_menu/common/modifier_type_definitions',
            'main_menu/common/game_concepts',
        ]
        regex_lines = ['|'.join(batch) for batch in itertools.batched([m.name for m in self.parser.modifier_types.values()], 100)]
        regexes = [re.compile(r'\b(' + regex + r')\b') for regex in regex_lines]
        modifier_count = Counter()
        for textfile in self.game.game_path.glob('game/*/common/**/*.txt'):
            ignored = False
            for ignored_path in ignored_paths:
                if ignored_path in str(textfile) or textfile.parent.match(str(self.game.game_path / 'game') + '/' + ignored_path):
                    ignored = True
                    break
            if ignored:
                continue
            contents = textfile.read_text(encoding='utf-8_sig')
            for regex in regexes:
                modifier_count.update(regex.findall(contents))

        table_data = []
        for modifier in self.parser.modifier_types.values():
            if modifier.name in modifier_count:
                count = modifier_count[modifier.name]
            else:
                count = 0
            table_data.append({
                'Uses': count,
                'Name': modifier.name,
                'Category': modifier.category,
                'into_template': f'<code><nowiki>{{{{modifier info|{modifier.name}}}}}</nowiki></code>',
                'Display Name': modifier.display_name,
                'Description': modifier.description
            })
        return self.make_wiki_table(table_data)


if __name__ == '__main__':
    OneTimeGenerator().run(sys.argv)
