import math
from typing import List

from common.wiki import WikiTextFormatter


class CS2WikiTextFormatter(WikiTextFormatter):

    def format_with_units(self, number, units: List[str], unit_weights: List[int] = None):

        if unit_weights is None:
            unit_weights = []
            unit_weight = 1
            for unit in units:
                unit_weights.append(unit_weight)
                unit_weight *= 1000

        suffix_map = {unit_weight: unit
                      for unit, unit_weight in zip(units, unit_weights)
                      }

        for threshold, suffix in reversed(suffix_map.items()):
            if number >= threshold:
                number /= threshold
                # number = math.floor(number * 100.0) / 100.0
                return f'{number:g} {suffix}'
        return f'{number:g} {suffix_map[1]}'

    def distance(self, number) -> str:
        return self.format_with_units(number, ['m', 'km'])

    def weight_per_month(self, weight):
        return self.format_with_units(weight, ['kg/month', 't/month'])

    def weight(self, weight):
        return self.format_with_units(weight, ['kg', 't', 'kt'])

    def power(self, power):
        # somehow the base value is 100 W
        power /= 10
        return self.format_with_units(power, ['KW', 'MW', 'GW'])

    def energy(self, power):
        # somehow the base value is 100 Wh
        power /= 10
        return self.format_with_units(power, ['KWh', 'MWh', 'GWh'])

    def data_rate(self, data_rate):
        return self.format_with_units(data_rate, ['GBit / s'])

    def area(self, area):
        return self.format_with_units(area, ['m²', 'km²'], [1, 1000*1000])

    def cost(self, cost: int | float):
        """add cost template and round number to integer"""
        return f'{{{{cost|{self.format_big_number(round(cost))}}}}}'