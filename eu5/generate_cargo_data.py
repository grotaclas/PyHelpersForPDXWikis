import sys
from operator import attrgetter
from typing import Any, Iterable

from common.paradox_lib import unsorted_groupby
from eu5.eu5_file_generator import Eu5FileGenerator
from eu5.eu5lib import Country, Event, EventFile


class CargoDataGenerator(Eu5FileGenerator):
    def create_cargo_template_calls(self, template_name: str, data: list[dict[str, Any]],
                                    include_header_level: int | None = 3):
        lines = []
        for item_data in data:
            lines.append(self.create_cargo_template_call(template_name, item_data, include_header_level=include_header_level))
        return '\n'.join(lines)

    def create_cargo_template_call(self, template_name: str, item_data: dict[str, Any], include_header_level: int = None):
        lines = []
        if include_header_level is not None:
            if 'display_name' in item_data:
                display_name = item_data["display_name"]
            else:
                display_name = item_data["name"]

            lines.append(self.formatter.create_section_heading(display_name, include_header_level))
        lines.append(f'{{{{{template_name}')
        for column, value in item_data.items():
            lines.append(f'|{column}={value}')
        lines.append('}}')
        return '\n'.join(lines)

    def generate_building_table_cargo(self):
        sorted_buildings = sorted(
            self.parser.buildings.values(),
            # [good for good in self.parser.goods.values() if good.category == category and good.method == method]
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
            'can_destroy': self.formatter.format_trigger(building.can_destroy),
            # can_destroy: <class 'eu5.eu5lib.Trigger'>
            'capital_country_modifier': self.format_modifier_section('capital_country_modifier', building),
            # capital_country_modifier: list[eu5.eu5lib.Eu5Modifier]
            'capital_modifier': self.format_modifier_section('capital_modifier', building),
            # capital_modifier: list[eu5.eu5lib.Eu5Modifier]
            'category': building.category.name,  # category: <class 'str'>
            'city': 1 if building.city else 0,  # city: <class 'bool'>
            'construction_demand': building.construction_demand.format(icon_only=True) if hasattr(
                building.construction_demand,
                'format') else building.construction_demand,
            # construction_demand: <class 'eu5.eu5lib.GoodsDemand'>
            'country_potential': self.formatter.format_trigger(building.country_potential),
            # country_potential: <class 'eu5.eu5lib.Trigger'>
            'destroy_price': building.destroy_price.format(icon_only=True) if hasattr(building.destroy_price,
                                                                                      'format') else building.destroy_price,
            # destroy_price: <class 'eu5.eu5lib.Price'>
            'employment_size': building.employment_size,  # employment_size: <class 'float'>
            'estate': building.estate.name if building.estate else '',
            'foreign_country_modifier': self.format_modifier_section('foreign_country_modifier', building),
            # foreign_country_modifier: list[eu5.eu5lib.Eu5Modifier]
            'graphical_tags': ';'.join([graphical_tags for graphical_tags in building.graphical_tags]),
            # graphical_tags: list[str]
            'location_potential': self.formatter.format_trigger(building.location_potential),
            # location_potential: <class 'eu5.eu5lib.Trigger'>
            'market_center_modifier': self.format_modifier_section('market_center_modifier', building),
            # market_center_modifier: list[eu5.eu5lib.Eu5Modifier]
            'max_levels': building.max_levels,  # max_levels: int | str
            'obsolete': ';'.join([obsolete.name if obsolete else '' for obsolete in building.obsolete]),
            # obsolete: list[eu5.eu5lib.Building]
            'on_built': self.formatter.format_effect(building.on_built),  # on_built: <class 'eu5.eu5lib.Effect'>
            'on_destroyed': self.formatter.format_effect(building.on_destroyed),
            # on_destroyed: <class 'eu5.eu5lib.Effect'>
            'pop_type': building.pop_type.name if building.pop_type else '',
            'possible_production_methods': self.create_wiki_list(
                [pm.format(icon_only=True) for pm in building.possible_production_methods]),
            # possible_production_methods: list[eu5.eu5lib.ProductionMethod]
            'price': building.price.format(icon_only=True) if hasattr(building.price, 'format') else building.price,
            # price: <class 'eu5.eu5lib.Price'>
            'raw_modifier': self.format_modifier_section('raw_modifier', building),
            # raw_modifier: list[eu5.eu5lib.Eu5Modifier]
            'remove_if': self.formatter.format_trigger(building.remove_if),  # remove_if: <class 'eu5.eu5lib.Trigger'>
            'rural_settlement': 1 if building.rural_settlement else 0,  # rural_settlement: <class 'bool'>
            'town': 1 if building.town else 0,  # town: <class 'bool'>
            'unique_production_methods': ';'.join([self.create_wiki_list(
                [pm.format(icon_only=True) for pm in pms]) for pms in building.unique_production_methods]),
            # unique_production_methods: list[list[eu5.eu5lib.ProductionMethod]]
            'notes': self.get_building_notes(building),
        } for building in sorted_buildings]
        return self.create_cargo_template_calls('Building', buildings)

    def generate_building_categories_cargo(self):
        sorted_categories = sorted(
            self.parser.building_category.values(),
            key=attrgetter('display_name')
        )
        categories = [{
            'name': category.name,
            'display_name': category.display_name,
            'description': category.description,
            'icon': category.get_wiki_filename(),
        } for category in sorted_categories]
        return self.create_cargo_template_calls('Building_category', categories)

    def generate_countries_cargo(self):
        result = []
        for initial, cargo_data in self.get_countries_cargo_by_initials().items():
            result.append(f'== {initial} ==')
            result.append(cargo_data)
        return result

    def get_countries_cargo_by_initials(self):
        cargo_data = {}
        countries: list[Country]
        for initial, countries in unsorted_groupby(
                filter(lambda c: c.name not in ['DUMMY', 'PIR', 'MER'], self.parser.countries.values()),
                key=lambda c: c.display_name[0]):
            country_cargo_templates = []
            for country in sorted(countries, key=attrgetter('display_name')):
                country_cargo_templates.append(self.get_country_cargo(country, 3))
            cargo_data[initial] = '\n'.join(country_cargo_templates)
        return cargo_data

    def get_country_cargo(self, country: Country, include_header_level: int = None) -> str:
        country_data_for_cargo = {
            'tag': country.name,
            'name': country.display_name,

            'country_rank': country.country_rank.display_name,
            'flag': '' if country.flag is None else f'Flag {country.flag}.png' if isinstance(country.flag, str) else f'Flag {country.flag.name}.png',
            'type': self.localize(country.type),
            'government': country.government['type'],
            'culture': '' if country.culture_definition is None else country.culture_definition.display_name if country.culture_definition else '',
            # culture_definition: <class 'eu5.eu5lib.Culture'>
            'religion': '' if country.religion_definition is None else country.religion_definition.get_wiki_link_with_icon() if country.religion_definition else '',
            # religion_definition: <class 'eu5.eu5lib.Religion'>
            'capital': '' if country.capital is None else country.capital.display_name if country.capital else '',
            # capital: <class 'eu5.eu5lib.Location'>

            'country_name': country.country_name,  # country_name: <class 'str'>
            'description_category': '' if country.description_category is None else country.description_category.display_name if country.description_category else '',
            # description_category: <class 'eu5.eu5lib.CountryDescriptionCategory'>
            'description': country.description,
            'map_color': country.color.css_color_string,

            'accepted_cultures': ';'.join(
                [accepted_cultures.display_name if accepted_cultures else '' for accepted_cultures in
                 country.accepted_cultures]),  # accepted_cultures: list[eu5.eu5lib.Culture]
            'control': ';'.join([control.display_name if control else '' for control in
                                 country.control]),  # control: list[eu5.eu5lib.Location]
            'court_language': '' if country.court_language is None else country.court_language.display_name if country.court_language else '',
            # court_language: <class 'eu5.eu5lib.Language'>
            'currency_data': ';'.join([currency_value.format() for currency_value in country.currency_data]),
            'difficulty': country.difficulty,  # difficulty: <class 'int'>
            'dynasty': country.dynasty,  # dynasty: <class 'str'>
            'formable_level': country.formable_level,  # formable_level: <class 'int'>
            'is_historic': 1 if country.is_historic else 0,  # is_historic: <class 'bool'>

            'liturgical_language': '' if country.liturgical_language is None else country.liturgical_language.display_name if country.liturgical_language else '',
            # liturgical_language: <class 'eu5.eu5lib.Language'>
            'our_cores_conquered_by_others': ';'.join(
                [our_cores_conquered_by_others.display_name if our_cores_conquered_by_others else '' for
                 our_cores_conquered_by_others in
                 country.our_cores_conquered_by_others]),
            # our_cores_conquered_by_others: list[eu5.eu5lib.Location]
            'own_conquered': ';'.join([own_conquered.display_name if own_conquered else '' for own_conquered in
                                       country.own_conquered]),  # own_conquered: list[eu5.eu5lib.Location]
            'own_control_colony': ';'.join(
                [own_control_colony.display_name if own_control_colony else '' for own_control_colony in
                 country.own_control_colony]),  # own_control_colony: list[eu5.eu5lib.Location]
            'own_control_conquered': ';'.join(
                [own_control_conquered.display_name if own_control_conquered else '' for own_control_conquered
                 in
                 country.own_control_conquered]),  # own_control_conquered: list[eu5.eu5lib.Location]
            'own_control_core': ';'.join(
                [own_control_core.display_name if own_control_core else '' for own_control_core in
                 country.own_control_core]),  # own_control_core: list[eu5.eu5lib.Location]
            'own_control_integrated': ';'.join(
                [own_control_integrated.display_name if own_control_integrated else '' for
                 own_control_integrated in
                 country.own_control_integrated]),  # own_control_integrated: list[eu5.eu5lib.Location]
            'own_core': ';'.join([own_core.display_name if own_core else '' for own_core in
                                  country.own_core]),  # own_core: list[eu5.eu5lib.Location]
            'religious_school': '' if country.religious_school is None else country.religious_school.get_wiki_link_with_icon() if country.religious_school else '',
            # religious_school: <class 'eu5.eu5lib.ReligiousSchool'>
            'revolt': 1 if country.revolt else 0,  # revolt: <class 'bool'>
            'scholars': ';'.join(
                [scholars.get_wiki_link_with_icon() if scholars else '' for scholars in country.scholars]),
            # scholars: list[eu5.eu5lib.ReligiousSchool]
            'starting_technology_level': '' if country.starting_technology_level is None else country.starting_technology_level,
            # starting_technology_level: <class 'int'>
            'timed_modifier': self.create_wiki_list([[f'{k}: {v}' for k, v in mod] for mod in
                                                     country.timed_modifier]) if country.timed_modifier else '',
            'tolerated_cultures': ';'.join(
                [tolerated_cultures.display_name if tolerated_cultures else '' for tolerated_cultures in
                 country.tolerated_cultures]),  # tolerated_cultures: list[eu5.eu5lib.Culture]

        }
        return self.create_cargo_template_call('CountryCargo', country_data_for_cargo, include_header_level)

    def apply_event_template(self, event_file: EventFile, events_wiki_text: str) -> str:
        template = """{version_tag}
{{{{computer generated}}}}

{page_description}<ref>The script code is located in {{{{path|events/{filename}|in_game}}}}</ref>

== Events ==
{{{{box wrapper}}}}
{events}
{{{{end box wrapper}}}}
== Footnotes ==
<references/>
[[Category:Events]]"""
        topic_events_description = 'This is a list of events relating to [[{topic}]].'
        country_events_description = 'This is a list of all {{{{icon|event|w=20px}}}} events for {{{{flag|{country}}}}}.'
        topic = event_file.path.stem.lower()
        topic = topic.removesuffix('_events')
        topic = topic.removesuffix('_event')
        topic = topic.removesuffix('_flavor')
        topic = topic.removeprefix('flavor_')
        if len(topic) == 3 and topic.upper() in self.parser.countries_including_formables:
            description = country_events_description.format(country=self.parser.countries_including_formables[topic.upper()].display_name)
        else:
            description = topic_events_description.format(topic=topic.replace('_', ' '))

        return template.format(version_tag=self.get_version_header(), page_description=description, filename=event_file.filename, events=events_wiki_text)

    def generate_events_cargo(self):
        result = {}
        for event_file in self.parser.event_files.values():
            result[event_file.filename.removesuffix('.txt')] = self.apply_event_template(
                event_file,
                self.surround_with_autogenerated_section(
                    f'events_{event_file.filename.replace("/", "_")}',
                    self.get_events_cargo(event_file.events.values()),
                    add_version_header=False
                )
            )
        return result

    def get_events_cargo(self, events: Iterable[Event]) -> str:
        event_cargo_templates = []
        for event in events:
            event_data = {
            'version': self.game.major_version,
            'event_id': event.name,
            'event_name': str(event.title),
            'event_text': str(event.desc),
            }
            if event.historical_info:
                event_data['historical_info'] = event.historical_info
            if event.fire_only_once:
                event_data['fire_only_once'] = 'yes'
            if event.after:
                event_data['after'] = self.formatter.format_effect(event.after)
            if event.dynamic_historical_event:
                event_data['dhe_tags'] =  ','.join(event.dynamic_historical_event.tag)
                if event.dynamic_historical_event.from_date != '':
                    event_data['dhe_from'] =  event.dynamic_historical_event.from_date
                if event.dynamic_historical_event.to_date != '':
                    event_data['dhe_to'] = event.dynamic_historical_event.to_date
                event_data['dhe_monthly_chance'] = event.dynamic_historical_event.monthly_chance
            if event.trigger:
                event_data['trigger'] = self.formatter.format_trigger(event.trigger)
            if event.major:
                event_data['major'] = 'yes'
            if event.major_trigger:
                event_data['major_trigger'] = self.formatter.format_trigger(event.major_trigger)
            if event.immediate:
                event_data['immediate'] = self.formatter.format_effect(event.immediate)
            if event.option:
                event_data['options'] = self.create_cargo_template_calls('Option', [{
                    'option_text': option.display_name,
                    'trigger': self.formatter.format_trigger(option.trigger) if option.trigger else '',
                    'effect': self.formatter.format_trigger(option.effect) if option.effect else '',
                    'historical': 'yes' if option.historical_option else '',
                } for option in event.option.values()], include_header_level=None)
            if event.type:
                event_data['type'] = event.type
            event_cargo_templates.append(f'<section begin={event.event_id}/>')
            event_cargo_templates.append(self.create_cargo_template_call('Event', event_data, include_header_level=None))
            event_cargo_templates.append(f'<section end={event.event_id}/>')

        return '\n'.join(event_cargo_templates)

if __name__ == '__main__':
    CargoDataGenerator().run(sys.argv)