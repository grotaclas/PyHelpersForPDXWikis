import os
import sys
from operator import attrgetter
from typing import Any, Iterable

# add the parent folder to the path so that imports work even if this file gets executed directly
sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from common.paradox_lib import unsorted_groupby, IconMixin
from eu5.eu5_file_generator import Eu5FileGenerator
from eu5.eu5lib import Country, Event, EventFile, Advance


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
            if value is not None:  # skip None values so that cargo stores them as NULL in the DB
                lines.append(f'|{column}={value}')
        lines.append('}}')
        return '\n'.join(lines)

    def generate_advances_cargo(self):
        result = []
        for age, cargo_data in self.get_advances_cargo_by_ages().items():
            result.append(f'== {self.parser.age[age]} ==')
            result.append(cargo_data)
        return result

    def get_advances_cargo_by_ages(self):
        cargo_data = {}
        advances: list[Advance]
        for age, advances in unsorted_groupby(
                self.parser.advances.values(),
                key=lambda a: a.age.name):
            advances_cargo_templates = []
            for advance in sorted(advances, key=attrgetter('display_name')):
                advances_cargo_templates.append(self.get_advances_cargo(advance, 3))
            cargo_data[age] = '\n'.join(advances_cargo_templates)
        return cargo_data

    def _get_all_unlocks(self, advance: Advance) -> str:
        unlock_lines = []
        for unlocks in [
            advance.unlock_ability,
            advance.unlock_building,
            advance.unlock_cabinet_action,
            advance.unlock_casus_belli,
            advance.unlock_chivalric_order,
            advance.unlock_country_interaction,
            advance.unlock_diplomacy,
            advance.unlock_estate_privilege,
            advance.unlock_government_reform,
            advance.unlock_heir_selection,
            advance.unlock_interaction,
            advance.unlock_law,
            advance.unlock_levy,
            advance.unlock_policy,
            advance.unlock_production_method,
            advance.unlock_relation_type,
            advance.unlock_road_type,
            advance.unlock_subject_type,
            advance.unlock_town_rights,
            advance.unlock_unit,
        ]:
            for unlock in unlocks:
                if isinstance(unlock, IconMixin):
                    unlock_lines.append(unlock.get_wiki_link_with_icon())
                else:
                    unlock_lines.append(unlock.display_name)

        if len(unlock_lines) > 0:
            return f'Unlocks:{self.create_wiki_list(unlock_lines)}'
        else:
            return ''

    def get_advances_cargo(self, advance: Advance, include_header_level: int = None):
        advance_data_for_cargo = {
            'name': advance.name,
            'display_name': advance.display_name,
            'description': advance.description,
            'icon': advance.get_wiki_filename(),
            'age': advance.age.display_name if advance.age else '',  # age: <class 'eu5.eu5lib.Age'>
            'ai_preference_tags': ';'.join([ai_preference_tags for ai_preference_tags in advance.ai_preference_tags]),  # ai_preference_tags: list[str]
            'ai_weight': '' if advance.ai_weight is None else advance.ai_weight.format() if hasattr(advance.ai_weight, 'format') else advance.ai_weight,  # ai_weight: <class 'eu5.eu5lib.ScriptValue'>
            'allow': self.formatter.format_trigger(advance.allow),  # allow: <class 'eu5.trigger.Trigger'>
            'allow_children': 1 if advance.allow_children else 0,  # allow_children: <class 'bool'>
            'content_priority': advance.content_priority,  # content_priority: <class 'int'>
            'country_type': '' if advance.country_type is None else advance.country_type,  # country_type: <class 'str'>
            'depth': advance.depth,  # int, but can be None
            'age_specialization': '' if advance.age_specialization is None else advance.age_specialization,  # age_specialization: <class 'str'>
            'government': advance.government.display_name if advance.government else '',  # government: <class 'eu5.eu5lib.GovernmentType'>
            'modifiers': self.format_modifier_section('modifiers', advance),
            'modifier_while_progressing': self.format_modifier_section('modifier_while_progressing', advance),  # modifier_while_progressing: list[eu5.eu5lib.Eu5Modifier]
            'potential': self.formatter.format_trigger(advance.potential),  # potential: <class 'eu5.trigger.Trigger'>
            'requires': ';'.join([requires.name for requires in advance.requires]),  # requires: list[str]
            'in_tree_of': advance.in_tree_of,  # in_tree_of: <class 'str'>
            'research_cost': advance.research_cost,  # float, but can be None
            'starting_technology_level': advance.starting_technology_level,  # int, default 0
            'tags': ';'.join(advance.tags),
            'unlocks': self._get_all_unlocks(advance),
            'unlock_ability': ';'.join([unlock_ability.display_name for unlock_ability in advance.unlock_ability]),  # unlock_ability: list[eu5.eu5lib.UnitAbility]
            'unlock_building': ';'.join([unlock_building.display_name for unlock_building in advance.unlock_building]),  # unlock_building: list[eu5.eu5lib.Building]
            'unlock_cabinet_action': ';'.join([unlock_cabinet_action.display_name for unlock_cabinet_action in advance.unlock_cabinet_action]),  # unlock_cabinet_action: list[eu5.eu5lib.CabinetAction]
            'unlock_casus_belli': ';'.join([unlock_casus_belli.display_name for unlock_casus_belli in advance.unlock_casus_belli]),  # unlock_casus_belli: list[eu5.eu5lib.CasusBelli]
            'unlock_chivalric_order': ';'.join([unlock_chivalric_order.display_name for unlock_chivalric_order in advance.unlock_chivalric_order]),  # unlock_chivalric_order: list[eu5.eu5lib.ChivalricOrder]
            'unlock_country_interaction': ';'.join([unlock_country_interaction.display_name for unlock_country_interaction in advance.unlock_country_interaction]),  # unlock_country_interaction: list[eu5.eu5lib.CountryInteraction]
            'unlock_diplomacy': ';'.join([unlock_diplomacy.display_name if unlock_diplomacy else '' for unlock_diplomacy in advance.unlock_diplomacy]),  # unlock_diplomacy: list[eu5.eu5lib.Eu5GameConcept]
            'unlock_estate_privilege': ';'.join([unlock_estate_privilege.display_name for unlock_estate_privilege in advance.unlock_estate_privilege]),  # unlock_estate_privilege: list[eu5.eu5lib.EstatePrivilege]
            'unlock_government_reform': ';'.join([unlock_government_reform.display_name for unlock_government_reform in advance.unlock_government_reform]),  # unlock_government_reform: list[eu5.eu5lib.GovernmentReform]
            'unlock_heir_selection': ';'.join([unlock_heir_selection.display_name for unlock_heir_selection in advance.unlock_heir_selection]),  # unlock_heir_selection: list[eu5.eu5lib.HeirSelection]
            'unlock_interaction': ';'.join([unlock_interaction.display_name for unlock_interaction in advance.unlock_interaction]),  # unlock_interaction: list[eu5.eu5lib.CharacterInteraction]
            'unlock_law': ';'.join([unlock_law.display_name for unlock_law in advance.unlock_law]),  # unlock_law: list[eu5.eu5lib.Law]
            'unlock_levy': ';'.join([unlock_levy.display_name if unlock_levy else '' for unlock_levy in advance.unlock_levy]),  # unlock_levy: list[eu5.eu5lib.Levy]
            'unlock_policy': ';'.join([unlock_policy.display_name if unlock_policy else '' for unlock_policy in advance.unlock_policy]),  # unlock_policy: list[eu5.eu5lib.LawPolicy]
            'unlock_production_method': ';'.join([unlock_production_method.display_name for unlock_production_method in advance.unlock_production_method]),  # unlock_production_method: list[eu5.eu5lib.ProductionMethod]
            'unlock_road_type': ';'.join([unlock_road_type.display_name for unlock_road_type in advance.unlock_road_type]),  # unlock_road_type: list[eu5.eu5lib.RoadType]
            'unlock_subject_type': ';'.join([unlock_subject_type.display_name for unlock_subject_type in advance.unlock_subject_type]),  # unlock_subject_type: list[eu5.eu5lib.SubjectType]
            'unlock_unit': ';'.join([unlock_unit.display_name for unlock_unit in advance.unlock_unit]),  # unlock_unit: list[eu5.eu5lib.UnitType]
            'unlock_town_rights': ';'.join([unlock_town_rights.display_name for unlock_town_rights in advance.unlock_town_rights]),  # unlock_town_rights: list[str]
        }

        return self.create_cargo_template_call('Advance', advance_data_for_cargo, include_header_level)

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
            'megalopolis': 1 if building.megalopolis else 0,  # megalopolis: <class 'bool'>
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
            'dynasty': ';'.join([
                dynasty.display_name
                if dynasty else ''
                for dynasty in country.dynasty
            ]),
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