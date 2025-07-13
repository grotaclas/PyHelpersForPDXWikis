"""

generates list and other things which are not run regularly, but which might come in handy again

"""
import sys

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

if __name__ == '__main__':
    OneTimeGenerator().run(sys.argv)
