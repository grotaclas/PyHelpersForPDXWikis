import csv
from operator import attrgetter

import sys

from eu5.eu5_file_generator import Eu5FileGenerator


class Eu5CSVGenerator(Eu5FileGenerator):



    def _write_text_file(self, name: str, content: list[dict]):
        output_file = self.outpath / '{}{}.csv'.format(self.game.short_game_name, name)
        with open(output_file, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, content[0].keys())
            writer.writeheader()
            for row in content:
                writer.writerow(row)

    def generate_pm_list(self):
        #Building Category - Building - PM -----> all inputs and outputs fed into the cells
        headers = ['Building Category', 'Building', 'PM']
        headers.extend(f'Input {good.display_name}' for good in sorted(self.parser.goods.values(), key=attrgetter('display_name')))
        headers.extend(f'Output {good.display_name}' for good in sorted(self.parser.goods.values(), key=attrgetter('display_name')))
        row_template = dict.fromkeys(headers)
        result = []
        for building in self.parser.buildings.values():
            a = (building.unique_production_methods + [building.possible_production_methods])
            for pm_list in a:
                for pm in pm_list:
                    row = row_template.copy()
                    row['Building Category'] = building.category.display_name
                    row['Building'] = building.display_name
                    row['PM'] = pm.display_name
                    for input_cost in pm.input:
                        row[f'Input {input_cost.resource.display_name}'] = input_cost.value
                    if pm.produced:
                        row[f'Output {pm.produced.display_name}'] = pm.output
                    result.append(row)
        return result

if __name__ == '__main__':
    Eu5CSVGenerator().run(sys.argv)