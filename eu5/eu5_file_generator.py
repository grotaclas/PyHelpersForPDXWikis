from functools import cached_property

from common.file_generator import FileGenerator
from eu5.eu5lib import Building
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

    def format_modifier_section(self, section: str, entity):
        if hasattr(entity, section):
            return self.create_wiki_list([modifier.format_for_wiki() for modifier in getattr(entity, section)])
        else:
            return ''

    def get_building_notes(self, building: Building):
        result = []
        messages_for_non_default_values = {
            'always_add_demands': 'Demand does not scale with workers',
            'AI_ignore_available_worker_flag': 'Build by AI even without available workers',
            'AI_optimization_flag_coastal': '',
            'allow_wrong_startup': '<tt>allow_wrong_startup</tt>',
            'can_close': 'Cannot be closed',
            'conversion_religion': f'Converts pops to {building.conversion_religion}',
            'forbidden_for_estates': 'Cannot be build by estates',
            'increase_per_level_cost': f'Cost changes by {self.formatter.add_red_green(building.increase_per_level_cost, positive_is_good=False, add_plus=True, add_percent=True)} per level',
            'in_empty': f'Can { {"empty": "only", "any": "also", "owned": "not"}[building.in_empty] } be built in empty locations',
            'is_foreign': 'Foreign building',
            'lifts_fog_of_war': 'Lifts fog of war',
            'need_good_relation': 'Needs good relations when building in foreign provinces',
            'pop_size_created': f'Creates {building.pop_size_created} pops when building(taken from the capital of the owner)',
            'stronger_power_projection': 'Requires more power projection to construct in a foreign location',
            'on_built': "'''On Built:'''\n" + self.formatter.format_effect(building.on_built),
            'on_destroyed': "'''On Destroyed:'''\n" + self.formatter.format_effect(building.on_destroyed),
        }
        for attribute, message in messages_for_non_default_values.items():
            if getattr(building, attribute) != building.default_values[attribute]:
                result.append(message)

        return self.create_wiki_list(result)
