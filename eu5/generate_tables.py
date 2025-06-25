import itertools
from functools import cached_property
from operator import attrgetter

import sys

from eu5.eu5_file_generator import Eu5FileGenerator
from eu5.eu5lib import GoodCategory, Eu5GameConcept, Price, Building, ProductionMethod
from eu5.text_formatter import Eu5WikiTextFormatter


class TableGenerator(Eu5FileGenerator):

    @cached_property
    def formatter(self) -> Eu5WikiTextFormatter:
        return self.parser.formatter

    def localize(self, key: str, default: str = None) -> str:
        return self.parser.localize(key, default)

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
        }
        for attribute, message in messages_for_non_default_values.items():
            if getattr(building, attribute) != building.default_values[attribute]:
                result.append(message)

        return self.create_wiki_list(result)

    def format_pms(self, building):
        pm_lists = building.unique_production_methods.copy()
        if building.possible_production_methods:
            pm_lists.append(building.possible_production_methods)
        formatted_pm_categories = []
        for pm_list in pm_lists:
            formatted_pms = []
            for pm in pm_list:
                formatted_pms.extend(pm.format(icon_only=True))
            formatted_pm_categories.append(self.create_wiki_list(formatted_pms))
        return '\n----\n'.join(formatted_pm_categories)

    def generate_building_tables(self):
        sorted_buildings = sorted(
            self.parser.buildings.values(),
            #[good for good in self.parser.goods.values() if good.category == category and good.method == method]
            key=attrgetter('display_name')
            )
        # sorted_buildings = [b for b in sorted_buildings if b.possible_production_methods and not isinstance(b.possible_production_methods[0], ProductionMethod)]
        # sorted_buildings = [self.parser.buildings['jewelry_guild']] + sorted_buildings[:20]
        buildings = [{
            # 'Name': f'{{{{iconbox|{building.display_name}|{building.description}|w=300px|image={building.get_wiki_filename()}}}}}',
            # 'Time': building.build_time,
            # 'Price': building.price.format() if isinstance(building.price, Price) else building.price,
            # 'Destroy Price': building.destroy_price.format() if building.destroy_price else '',
            # 'Construction demand': building.construction_demand.format(icon_only=True) if hasattr(building.construction_demand, 'format') else building.construction_demand,
            # 'category': building.category,
            # 'foreign':  building.is_foreign,
            # 'Pop': building.pop_type,
            # 'Employees': round(building.employment_size),
            # 'Town': building.town,
            # 'City': building.city,
            # 'Max levels': building.max_levels,
            # 'Modifiers': self.format_modifier_section('modifier', building),
            # 'Modifiers if in capital': self.format_modifier_section('capital_modifier', building),
            # 'Country modifiers if in capital': self.format_modifier_section('capital_country_modifier', building),
            'Name': f'{{{{iconbox|{building.display_name}|{building.description}|w=300px|image={building.get_wiki_filename()}}}}}',
'Modifier': self.format_modifier_section('modifier', building),  # modifier: list[eu5.eu5lib.Eu5Modifier]
'Allow': self.formatter.format_trigger(building.allow),  # allow: <class 'eu5.eu5lib.Trigger'>
'Build Time': building.build_time,  # build_time: <class 'int'>
'Can Destroy': self.formatter.format_trigger(building.can_destroy),  # can_destroy: <class 'eu5.eu5lib.Trigger'>
'Capital Country Modifier': self.format_modifier_section('capital_country_modifier', building),  # capital_country_modifier: list[eu5.eu5lib.Eu5Modifier]
'Capital Modifier': self.format_modifier_section('capital_modifier', building),  # capital_modifier: list[eu5.eu5lib.Eu5Modifier]
'Category': building.category,  # category: <class 'str'>
'City': '[[File:Yes.png|20px|City]]' if building.city else '[[File:No.png|20px|Not City]]',  # city: <class 'bool'>
'Construction Demand': building.construction_demand.format(icon_only=True) if hasattr(building.construction_demand, 'format') else building.construction_demand,  # construction_demand: <class 'eu5.eu5lib.GoodsDemand'>
'Country Potential': self.formatter.format_trigger(building.country_potential),  # country_potential: <class 'eu5.eu5lib.Trigger'>
'Destroy Price': building.destroy_price.format(icon_only=True) if hasattr(building.destroy_price, 'format') else building.destroy_price,  # destroy_price: <class 'eu5.eu5lib.Price'>
'Employment': f'{building.employment_size:g} {building.pop_type}',  # employment_size: <class 'float'>
'Estate': building.estate,  # estate: <class 'str'>
'Foreign Country Modifier': self.format_modifier_section('foreign_country_modifier', building),  # foreign_country_modifier: list[eu5.eu5lib.Eu5Modifier]
'Graphical Tags': self.create_wiki_list([graphical_tags for graphical_tags in building.graphical_tags]),  # graphical_tags: list[str]
'Location Potential': self.formatter.format_trigger(building.location_potential),  # location_potential: <class 'eu5.eu5lib.Trigger'>
'Market Center Modifier': self.format_modifier_section('market_center_modifier', building),  # market_center_modifier: list[eu5.eu5lib.Eu5Modifier]
'Max Levels': building.max_levels,  # max_levels: int | str
'Obsolete': self.create_wiki_list([obsolete.get_wiki_link_with_icon() if obsolete else '' for obsolete in building.obsolete]),  # obsolete: list[eu5.eu5lib.Building]
'On Built': self.formatter.format_effect(building.on_built),  # on_built: <class 'eu5.eu5lib.Effect'>
'On Destroyed': self.formatter.format_effect(building.on_destroyed),  # on_destroyed: <class 'eu5.eu5lib.Effect'>
'Production Methods': self.format_pms(building),  # possible_production_methods: list[eu5.eu5lib.ProductionMethod]
# 'Possible Production Methods': self.create_wiki_list([possible_production_methods.format(icon_only=True) if hasattr(possible_production_methods, 'format') else possible_production_methods for possible_production_methods in building.possible_production_methods]),  # possible_production_methods: list[eu5.eu5lib.ProductionMethod]
# 'Unique Production Methods': self.create_wiki_list([unique_production_methods.format(icon_only=True) if hasattr(unique_production_methods, 'format') else unique_production_methods for unique_production_methods in building.unique_production_methods]),  # unique_production_methods: list[eu5.eu5lib.ProductionMethod]
'Price': building.price.format(icon_only=True) if hasattr(building.price, 'format') else building.price,  # price: <class 'eu5.eu5lib.Price'>
'Raw Modifier': self.format_modifier_section('raw_modifier', building),  # raw_modifier: list[eu5.eu5lib.Eu5Modifier]
'Remove If': self.formatter.format_trigger(building.remove_if),  # remove_if: <class 'eu5.eu5lib.Trigger'>
'Rural Settlement': '[[File:Yes.png|20px|Rural Settlement]]' if building.rural_settlement else '[[File:No.png|20px|Not Rural Settlement]]',  # rural_settlement: <class 'bool'>
'Town': '[[File:Yes.png|20px|Town]]' if building.town else '[[File:No.png|20px|Not Town]]',  # town: <class 'bool'>
        'Notes': self.get_building_notes(building),
        } for building in sorted_buildings]
        return self.make_wiki_table(buildings, table_classes=['mildtable', 'plainlist'],
                                     one_line_per_cell=True,
                                     remove_empty_columns=True,
                                     )
    def create_cargo_tenplate_calls(self, data: list[dict[str, any]], template_name: str):
        lines = []
        for item_data in data:
            lines.append(f'=== {item_data["display_name"]} ===')
            lines.append(f'{{{{{template_name}')
            for column, value in item_data.items():
                lines.append(f'|{column}={value}')
            lines.append('}}')
        return '\n'.join(lines)

    def generate_building_table_cargo(self):
        sorted_buildings = sorted(
            self.parser.buildings.values(),
            #[good for good in self.parser.goods.values() if good.category == category and good.method == method]
            key=attrgetter('display_name')
            )
        buildings = [{
            'name': building.name,
            'display_name': building.display_name,
            'description': building.description,
            'icon': building.get_wiki_filename(),
            'modifier': self.format_modifier_section('modifier', building),  # modifier: list[eu5.eu5lib.Eu5Modifier]
            'allow': self.formatter.format_trigger(building.allow),  # allow: <class 'eu5.eu5lib.Trigger'>
            'build_time': building.build_time,  # build_time: <class 'int'>
            'can_destroy': self.formatter.format_trigger(building.can_destroy),  # can_destroy: <class 'eu5.eu5lib.Trigger'>
            'capital_country_modifier': self.format_modifier_section('capital_country_modifier', building),
            # capital_country_modifier: list[eu5.eu5lib.Eu5Modifier]
            'capital_modifier': self.format_modifier_section('capital_modifier', building),  # capital_modifier: list[eu5.eu5lib.Eu5Modifier]
            'category': building.category,  # category: <class 'str'>
            'city': 1 if building.city else 0,  # city: <class 'bool'>
            'construction_demand': building.construction_demand.format(icon_only=True) if hasattr(building.construction_demand,
                                                                                                  'format') else building.construction_demand,
            # construction_demand: <class 'eu5.eu5lib.GoodsDemand'>
            'country_potential': self.formatter.format_trigger(building.country_potential),  # country_potential: <class 'eu5.eu5lib.Trigger'>
            'destroy_price': building.destroy_price.format(icon_only=True) if hasattr(building.destroy_price, 'format') else building.destroy_price,
            # destroy_price: <class 'eu5.eu5lib.Price'>
            'employment_size': building.employment_size,  # employment_size: <class 'float'>
            'estate': building.estate,  # estate: <class 'str'>
            'foreign_country_modifier': self.format_modifier_section('foreign_country_modifier', building),
            # foreign_country_modifier: list[eu5.eu5lib.Eu5Modifier]
            'graphical_tags': ';'.join([graphical_tags for graphical_tags in building.graphical_tags]),  # graphical_tags: list[str]
            'location_potential': self.formatter.format_trigger(building.location_potential),  # location_potential: <class 'eu5.eu5lib.Trigger'>
            'market_center_modifier': self.format_modifier_section('market_center_modifier', building),  # market_center_modifier: list[eu5.eu5lib.Eu5Modifier]
            'max_levels': building.max_levels,  # max_levels: int | str
            'obsolete': ';'.join([obsolete.name if obsolete else '' for obsolete in building.obsolete]),  # obsolete: list[eu5.eu5lib.Building]
            'on_built': self.formatter.format_effect(building.on_built),  # on_built: <class 'eu5.eu5lib.Effect'>
            'on_destroyed': self.formatter.format_effect(building.on_destroyed),  # on_destroyed: <class 'eu5.eu5lib.Effect'>
            'pop_type': building.pop_type,  # pop_type: <class 'str'>
            'possible_production_methods': self.create_wiki_list(
                [pm.format(icon_only=True) for pm in building.possible_production_methods]),  # possible_production_methods: list[eu5.eu5lib.ProductionMethod]
            'price': building.price.format(icon_only=True) if hasattr(building.price, 'format') else building.price,  # price: <class 'eu5.eu5lib.Price'>
            'raw_modifier': self.format_modifier_section('raw_modifier', building),  # raw_modifier: list[eu5.eu5lib.Eu5Modifier]
            'remove_if': self.formatter.format_trigger(building.remove_if),  # remove_if: <class 'eu5.eu5lib.Trigger'>
            'rural_settlement': 1 if building.rural_settlement else 0,  # rural_settlement: <class 'bool'>
            'town': 1 if building.town else 0,  # town: <class 'bool'>
            'unique_production_methods': ';'.join([self.create_wiki_list(
                [pm.format(icon_only=True) for pm in pms]) for pms in building.unique_production_methods]),
            # unique_production_methods: list[list[eu5.eu5lib.ProductionMethod]]
            'notes': self.get_building_notes(building),
        } for building in sorted_buildings]
        return self.create_cargo_tenplate_calls(buildings, 'Building')

    def generate_concept_tables(self):
        concepts = sorted(self.parser.game_concepts.values(), key=attrgetter('family', 'display_name'))
        result = []
        family = None
        all_concept_names = list(self.parser.game_concepts.keys()) + [concept.display_name for concept in concepts]
        for concept in concepts:
            if concept.is_alias:
                continue
            if concept.family != family:
                family = concept.family
                result.append(f'== {family if family else "Uncategorized"} ==')
            result.extend(self.get_concept_section(all_concept_names, concept))
        return result

    def get_concept_section(self, all_concept_names, concept: Eu5GameConcept):
        result = [f'=== {concept} ===']
        if concept.alias:
            alias_display_names = [alias.display_name for alias in concept.alias]
            result.append(
                f'{{{{hatnote|Aliases: {", ".join(self.formatter.format_localization_text(alias_display_name, all_concept_names) for alias_display_name in alias_display_names)}}}}}{{{{anchor|{"}}{{anchor|".join(alias_display_names)}}}}}')
        result.append(f'<section begin=autogenerated_concept_{concept.name}/>')
        result.append(self.get_concept_section_contents(all_concept_names, concept))
        result.append(f'<section end=autogenerated_concept_{concept.name}/>')
        return result

    def get_concept_section_contents(self, all_concept_names, concept):
        return self.formatter.format_localization_text(concept.description, all_concept_names)

    def generate_goods_tables(self):
        result = []
        for section, table in self.get_goods_tables().items():
            result.append(f'=== {section} ===')
            result.append(self.surround_with_autogenerated_section(section, table, add_version_header=True))
        return result

    def get_goods_tables(self):
        result = {}
        for category in GoodCategory:
            methods = set(good.method for good in self.parser.goods.values() if good.category == category)
            for method in sorted(methods):
                result[f'{category}_{method if method else "default"}'] = self.get_goods_table(category, method)
        return result

    def get_goods_table(self, category: GoodCategory, method: str):
        sorted_goods = sorted([good for good in self.parser.goods.values() if good.category == category and good.method == method], key=attrgetter('display_name'))
        goods = [{
            'Name': f'{{{{iconbox|{good.display_name}|{good.description}|w=300px|image={good.get_wiki_filename()}}}}}',
            'Base production': good.base_production,
            'Default price': good.default_market_price,
            'Inflation': 'yes' if good.inflation else '',
            'Transport cost': good.transport_cost,

        } for good in sorted_goods]
        return self.make_wiki_table(goods, table_classes=['mildtable', 'plainlist'],
                                     one_line_per_cell=True,
                                     remove_empty_columns=True,
                                     )


if __name__ == '__main__':
    TableGenerator().run(sys.argv)