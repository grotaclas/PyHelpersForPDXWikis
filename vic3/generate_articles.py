from dataclasses import dataclass
from operator import attrgetter
import os
import sys
# add the parent folder to the path so that imports work even if this file gets executed directly
sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from vic3.text_formatter import Vic3WikiTextFormatter
from vic3.vic3_file_generator import Vic3FileGenerator


@dataclass
class GameConcept:
    name: str
    display_name: str
    description: str
    icon: str
    link: str


class ArticleGenerator(Vic3FileGenerator):
    concepts: dict[str, GameConcept]
    text_formatter: Vic3WikiTextFormatter

    def write_articles(self):
        self._write_text_file('articles', self.generate_articles())

    def generate_articles(self):
        self.concepts = {}
        self.text_formatter = Vic3WikiTextFormatter()
        for concept_name, data in self.parser.parser.parse_file('common/game_concepts/00_game_concepts.txt'):
            if concept_name == 'concept_concept':  # we dont need it for the wiki, because it just explains concepts
                continue
            if 'texture' in data:
                icon = data['texture']
            else:
                icon = None
            self.concepts[concept_name] = GameConcept(concept_name,
                                                      # self.localize_concepts_in_text(self.parser.localize(concept_name)),
                                                      self.text_formatter.format_localization_text(self.parser.localize(concept_name), []),
                                                      self.parser.localize(concept_name + '_desc'), icon,
                                                      link=self.parser.localize(concept_name))

        self.format_descriptions()

        headers = ['{| class="toccolours" style="width:100%"',
                   '! Game concepts',
                   '|-valign=top',
                   '|',
                   '{{MultiColumn|']
        lines = ['== List of Vickypedia entries ==']
        for concept in sorted(self.concepts.values(), key=attrgetter('display_name')):
            headers.append(':[[#{0}|{0}]]'.format(concept.display_name))
            lines.append(f'==={concept.display_name}===')
            lines.append(concept.description)
        headers.append('|6}}')
        headers.append('|}')
        return self.get_version_header() + '\n' + '\n'.join(headers + lines)

    def format_descriptions(self):
        concept_display_names = [concept.display_name for concept in self.concepts.values()]
        for concept in self.concepts.values():
            new_text = concept.description
            new_text = self.text_formatter.format_localization_text(new_text, concept_display_names)
            concept.description = new_text


if __name__ == '__main__':
    ArticleGenerator().run(sys.argv)
