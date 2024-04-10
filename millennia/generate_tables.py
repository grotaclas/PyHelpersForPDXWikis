from collections import OrderedDict
from operator import attrgetter

import sys

from millennia.game import MillenniaFileGenerator
from millennia.millennia_lib import *
from millennia.text_formatter import MillenniaWikiTextFormatter


class TableGenerator(MillenniaFileGenerator):

    @cached_property
    def formatter(self) -> MillenniaWikiTextFormatter:
        return self.parser.formatter

    def localize(self, key: str, localization_category: str = None, localization_suffix: str = None,
                 default: str = None) -> str:
        return self.parser.localize(key, localization_category, localization_suffix, default)

    def generate_infopedia_tables(self):
        topics = sorted(self.parser.infopedia_topics.values(), key=attrgetter('display_name'))
        result = []
        for topic_type in self.parser.infopedia_topic_types.values():
            result.append(f'== {topic_type.display_name} ==')
            for topic in topics:
                if topic.topicType == topic_type:
                    result.append(f'=== {topic} ===')
                    result.append(f'<section begin=autogenerated_infopedia_{topic.name} />')
                    result.append(topic.text)
                    result.append(f'<section end=autogenerated_infopedia_{topic.name} />')

        return result

    def get_domain_power_notes(self, domain_power: DomainPower):
        notes = []
        target_tooltip = self.parser.localize(domain_power.name, 'Game-Culture', 'Targeting-Tooltip', '')
        if target_tooltip != '':
            target_tooltip = self.formatter.convert_to_wikitext(target_tooltip.removeprefix('Invalid Target - '))
            notes.append(f'Target: {target_tooltip}')
        if domain_power.cooldown:
            notes.append(f'Cooldown: {domain_power.cooldown} turns')

        progressive_cost = domain_power.params.get('ProgressiveCost')
        if progressive_cost:
            notes.append(f'Progressive cost factor: {progressive_cost}')
        return self.create_wiki_list(notes)

    def generate_domain_power_table(self):
        powers = [power for power in self.parser.domain_powers.values() if power.has_localized_display_name and not power.is_culture_power()]
        powers = sorted(powers, key=attrgetter('domain', 'cost.value', 'display_name'))

        data = [{
            'id': power.display_name,
            '': power.get_wiki_file_tag('48px'),
            'Power': power.display_name,
            'Cost': power.cost.format() if power.cost else '',
            'Effects': power.description,
            'Unlocked by': '',
            'Notes': self.get_domain_power_notes(power),

        } for power in powers]
        result = []
        result.append(self.get_SVersion_header(scope='table') + '\n'
                      + self.make_wiki_table(data, table_classes=['mildtable'],
                                             one_line_per_cell=True, row_id_key='id'))

        return result

    def generate_culture_power_table(self):
        powers = [power for power in self.parser.domain_powers.values() if power.has_localized_display_name and power.is_culture_power()]
        powers = sorted(powers, key=attrgetter('domain', 'display_name'))

        data = [{
            'id': power.display_name,
            '': power.get_wiki_file_tag('48px'),
            'Power': power.display_name,
            'Domain': power.get_domain_icon(),
            'Effects': power.description,
            # 'Effects2': power.effc,
            'Unlocked by': '',
            'Notes': self.get_domain_power_notes(power),

        } for power in powers]
        result = []
        result.append(self.get_SVersion_header(scope='table') + '\n'
                      + self.make_wiki_table(data, table_classes=['mildtable'],
                                             one_line_per_cell=True, row_id_key='id'))

        return result

    def improvement_sort_key(self, improvement):
        upgrade_line = improvement.startingData.get('UpgradeLine')
        if upgrade_line:
            line, tier = next(iter(upgrade_line.items()))
            return (line, int(tier), improvement.display_name)
        else:
            return ('zzzzzzzzzz', 0, improvement.display_name)

    @staticmethod
    def _requirements_to_strings(improvement: Improvement) -> list[str]:
        strings = []
        for requirement in improvement.build_requirements:
            if isinstance(requirement, str):
                strings.append(requirement)
            else:
                if requirement.has_localized_display_name:  # ignore non-localized stuff
                    strings.append(requirement.get_wiki_file_tag('24px'))
        return list(OrderedDict.fromkeys(strings))

    def generate_improvement_table(self):
        result = []
        for title, contents in self.get_improvement_sections().items():
            # result.append(f'== List of {title.replace("_"," ")} ==')
            result.append(f'== {title.replace("_"," ").removesuffix("_list").capitalize()} ==')
            result.append(self.surround_with_autogenerated_section(f'{title}', contents))
        return result

    def get_improvement_sections(self):
        sections = {
            'improvements': [improvement for improvement in self.parser.improvements.values() if
                                not improvement.is_outpost_improvement and not improvement.tags.has('RebuildableTown') and not improvement.is_outpost_specialization],
            'outpost_improvements': [improvement for improvement in self.parser.improvements.values() if improvement.is_outpost_improvement],
        }
        for improvement in self.parser.improvements.values():
            if improvement.is_outpost_specialization and improvement.display_name != 'Outpost':
                sections[improvement.display_name.lower().replace(' ', '_')] = [improvement]
        results = {}
        for title, improvements in sections.items():
            improvements = sorted(improvements, key=self.improvement_sort_key)
            if title == 'outpost_improvements':
                name_column = 'style="width:20%;" | Improvement'
                build_on_column = 'class="unsortable" style="width:25%;" | Build on'
            else:
                build_on_column = 'class="unsortable" | Build on'
                name_column = 'Improvement'
            data = [{
                'id': improvement.display_name,
                # 'class="unsortable" | ': improvement.get_wiki_file_tag('64px'),
                # 'Improvement': improvement.display_name,
                name_column: f'{{{{iconbox|{improvement.display_name}|{improvement.description}|image={improvement.get_wiki_filename()}}}}}',
                'Unlocked By': self.get_unlocked_by(improvement),
                'Base Cost': improvement.cost.format(icon_only=True),
                build_on_column: ' '.join(self._requirements_to_strings(improvement)),
                'class="unsortable" | Work effects': self.create_wiki_list(improvement.work_production),
                'class="unsortable" | Passive effects': self.create_wiki_list(improvement.non_work_production),
                'class="unsortable" | Upgrades': self.create_wiki_list([upgrade.get_wiki_link_with_icon() for upgrade in improvement.upgrades]),
                'class="unsortable" | Notes': self.create_wiki_list(improvement.notes),
                # 'class="hidem unsortable" | Description': 'class="hidem" | ' + improvement.description,

            } for improvement in improvements]
            results[title + '_list'] = (self.get_SVersion_header(scope='table') + '\n'
                              + self.make_wiki_table(data, table_classes=['mildtable', 'plainlist'],
                                                     one_line_per_cell=True, row_id_key='id', remove_empty_columns=True))
        return results

    def generate_building_table(self):
        result = []
        buildings = sorted([building for building in self.parser.buildings.values() if building.has_localized_display_name], key=self.improvement_sort_key)
        data = [{
            'id': building.display_name,
            # 'class="unsortable" | ': building.get_wiki_file_tag('64px'),
            # 'Improvement': building.display_name,
            'Building': f'{{{{iconbox|{building.display_name}|{building.description}|image={building.get_wiki_filename()}}}}}',
            'Unlocked By': self.get_unlocked_by(building),
            'Base Cost': building.cost.format(),
            'class="unsortable" | Effects': self.create_wiki_list(building.non_work_production),
            'class="unsortable" | Upgrades': self.create_wiki_list([upgrade.get_wiki_link_with_icon() for upgrade in building.upgrades]),
            'class="unsortable" | Notes': self.create_wiki_list(building.notes),
            # 'class="unsortable" | Description': self.formatter.convert_to_wikitext(building.description),
            # 'class="unsortable" | Infopedia': self.formatter.convert_to_wikitext(building.infopedia),

        } for building in buildings]
        # result.append(f'== {title} ==')
        result.append(self.get_SVersion_header(scope='table') + '\n'
                      + self.make_wiki_table(data, table_classes=['mildtable'],
                                             one_line_per_cell=True, row_id_key='id'))
        return result

    def generate_unit_table(self):
        result = []
        sections = self.get_unit_sections()
        for unit_type in unit_types.values():
            result.append(f'== {unit_type.display_name} ==')
            for secondary_type_tag, secondary_type_heading in self.secondary_types.items():
                section_tag = f'units_{unit_type.tag}_{secondary_type_tag}'
                if section_tag in sections:
                    if secondary_type_heading:
                        result.append(f'=== {secondary_type_heading} ===')
                    result.append(sections[section_tag])
        return result

    def get_unit_sections(self):
        result = {}
        all_units = sorted([unit for unit in self.parser.units.values() if unit.has_localized_display_name], key=self.improvement_sort_key)
        self.secondary_types = {
                 'WaterTransport': 'Transports',
                 'TypeMobileRecon': 'Recon units',
                 # could also use scout tag, but balloon engineer is TypeMobileRecon, but not scout and icarus is scout, but not TypeMobileRecon
                 'ActInAirCombatRounds': 'Fighters',
                 'ActInBombingRound': 'Bombers',  # there is also the AirBomber tag, but the airship doesnt have it
                 'CombatWall': 'Walls',
                 'CombatTower': 'Tower',
                 'Leader': 'Leaders',
                 'TypeSiege': 'Siege',
                 'TypeRanged': 'Ranged',
                 'TypeMobile': 'Mobile',
                 'TypeLine': 'Line',
                 'Unit': 'Other units',  # fallback
                 'ALL': '',
                 }
        for unit_type in unit_types.values():

            units_by_secondary_type = {typ: list() for typ in self.secondary_types}
            if unit_type.tag in ['SETTLER', 'TILEHARVEST']:
                units_by_secondary_type['ALL'] = [unit for unit in all_units if unit.primary_type == unit_type]
            else:
                for unit in all_units:
                    if unit.primary_type == unit_type:
                        units_by_secondary_type[unit.get_first_matching_tag(list(self.secondary_types.keys()))].append(unit)
            for secondary_type_tag, secondary_type_heading in self.secondary_types.items():
                units = units_by_secondary_type[secondary_type_tag]
                if units:
                    data = [{
                        'id': unit.display_name,
                        # 'class="unsortable" | ': unit.get_wiki_file_tag('64px'),
                        # 'Improvement': unit.display_name,
                        'Unit': f'{{{{iconbox|{unit.display_name}|{unit.description}|image={unit.get_wiki_filename()}}}}}',
                        'Unlocked By': self.get_unlocked_by(unit, include_not_found_note=False),  # units have many unhandled unlocks, so the note would not make sense
                        'Cost': unit.cost.format(icon_only=True),
                        'Upkeep': unit.upkeep.format(icon_only=True),
                        'Health': unit.health,
                        'Morale': unit.command,
                        'Movement': unit.movement,
                        'Attack': unit.attack,
                        'Defense': unit.defense,
                        'Sight': unit.revealRadius,
                        'Target prio': unit.targetPriority,
                        'Unrest suppression': unit.unrestSuppression,
                        'class="unsortable" | Upgrades': self.create_wiki_list([upgrade.get_wiki_link_with_icon() for upgrade in unit.upgrades]),
                        'class="unsortable" | Notes': self.create_wiki_list(unit.notes),
                        # 'class="unsortable" | Description': self.formatter.convert_to_wikitext(unit.description),
                        # 'class="unsortable" | Infopedia': self.formatter.convert_to_wikitext(unit.infopedia),

                    } for unit in units]
                    table = self.get_SVersion_header(scope='table') + '\n' + self.make_wiki_table(data, table_classes=['mildtable', 'plainlist'],
                                                                                                  one_line_per_cell=True,
                                                                                                  row_id_key='id')
                    result[f'units_{unit_type.tag}_{secondary_type_tag}'] = table
        return result

    def get_unlocked_by(self, entity, include_not_found_note=True):
        unlocks = [tech.get_wiki_link_with_icon()
                   for tech in entity.unlocked_by]
        if len(entity.spawned_by) > 0:
            unlocks.append('Spawned by:')
            unlocks.append([tech.get_wiki_link_with_icon() for tech in entity.spawned_by])
        if len(unlocks) == 0 and include_not_found_note:
            return f"''Nothing''<ref name=\"no_unlock_found\">{self.name_of_this_tool} did not find a way to unlock or spawn this in the game. This probably means that it was disabled and is not available. But there might be a way to spawn it which {self.name_of_this_tool} can't handle. In this case, please leave a message about this on the talk page</ref>"
        else:
            return self.create_wiki_list(unlocks)

    def generate_unit_action_table(self):
        actions = self.parser.unit_actions.values()
        data = [{
            'id': action.display_name,
            '': action.get_wiki_file_tag('48px'),
            'Action': action.display_name,
            'Available': '',
            'Requirements': self.create_wiki_list(action.requirements),
            'Effects': self.create_wiki_list(action.all_effects),
            'Description': self.formatter.convert_to_wikitext(action.description),

        } for action in actions]
        result = []
        result.append(self.get_SVersion_header(scope='table') + '\n'
                      + self.make_wiki_table(data, table_classes=['mildtable'],
                                             one_line_per_cell=True, row_id_key='id'))

        return result

    def generate_tech_table(self):
        return [self.surround_with_autogenerated_section(section, contents) for section, contents in self.get_tech_sections().items()]

    def get_tech_sections(self):
        technologies = sorted([tech for tech in self.parser.technologies.values() if not tech.is_age_advance], key=lambda tech: tech.ages[0].order)
        return {'technology_list': self.get_tech_table(technologies)}

    def get_tech_table(self, technologies, include_age=True, include_requirements=False):
        data = [{
            'id': tech.display_name,
            'Technology': f'{{{{iconbox|{tech.display_name}| |image={tech.get_wiki_filename()}}}}}',
            'Cost': tech.cost,
            'Requirements': self.create_wiki_list(tech.requirements) if include_requirements else '',
            'Age': self.create_wiki_list([age.get_wiki_link() for age in tech.ages]) if include_age else '',
            # 'Unlocks': self.create_wiki_list([self.parser.all_entities[unlock].get_wiki_link_with_icon() for unlock in tech.unlocks]),
            'Unlocks': self.create_wiki_list(tech.get_unlock_list('')),
            'Effects': self.create_wiki_list(tech.other_effects),
            'class="hidem" | Description': 'class="hidem" | ' + tech.description,
        } for tech in technologies]
        if len(data) == 0:
            return ''
        else:
            return self.make_wiki_table(data, table_classes=['mildtable', 'plainlist'], one_line_per_cell=True,
                                        row_id_key='id', remove_empty_columns=True)

    def _strip_unnecssary_information_from_ages_infopedia(self, infopedia_text: str, age: Age):
        infopedia_text = re.sub(r"^''[^']*?" + age.type_loc + f"]]''\n*", '', infopedia_text)
        infopedia_text = re.sub(r"^''[^']*?Final Age]]''\n*", '', infopedia_text)
        infopedia_text = re.sub(r'\n{2,}', '\n\n', infopedia_text)
        return infopedia_text

    def get_ages_sections(self):
        results = {}
        for age in sorted(self.parser.ages.values(), key=attrgetter('order')):
            name = age.display_name.lower().replace(' ', '_')
            # sorted_techs = sorted(age.technologies.values(), key=lambda tech: 1 if tech.is_age_advance else 0)  # sort advances after the normal techs
            sorted_techs = [tech for tech in age.technologies.values() if not tech.is_age_advance]
            for section, contents in {
                    f'infopedia_{name}': self._strip_unnecssary_information_from_ages_infopedia(self.formatter.convert_to_wikitext(age.infopedia), age),
                    f'unlocks_{name}': self.create_wiki_list(age.base_tech.get_unlock_list('')),
                    f'effects_{name}': self.create_wiki_list(age.base_tech.other_effects),
                    f'technologies_{name}': '\n' + self.get_tech_table(sorted_techs, include_age=False, include_requirements=True),
                    f'advances_{name}': '\n' + self.get_tech_table([tech for tech in age.technologies.values() if tech.is_age_advance], include_age=False, include_requirements=True),
            }.items():
                if not contents.isspace():
                    results[section] = self.get_SVersion_header() + contents
        return results

    def generate_ages_page(self):
        result = []
        sections = {name: self.surround_with_autogenerated_section(name, contents) for name, contents in self.get_ages_sections().items()}
        for age in sorted(self.parser.ages.values(), key=attrgetter('order')):
            name = age.display_name.lower().replace(' ', '_')
            result.append(f'=== {age.display_name} ===')
            result.append(f"'''''{age.type_loc}'''''")
            result.append(f'[[File:{age.display_name}.png|320px|right]]')
            result.append(f'==== Infopedia description ====')
            result.append(sections[f'infopedia_{name}'])
            result.append(f'==== Start unlocks ====')
            result.append(sections[f'unlocks_{name}'])
            result.append(f'==== Start effects ====')
            result.append(sections[f'effects_{name}'])
            result.append(f'==== Research options ====')
            result.append(sections[f'technologies_{name}'])
            if f'advances_{name}' in sections:
                result.append(f'==== Advances ====')
                result.append(sections[f'advances_{name}'])

        return result

    def generate_city_projects_table(self):
        result = []
        projects = sorted([project for project in self.parser.city_projects.values() if project.has_localized_display_name], key=attrgetter('display_name'))
        data = [{
            'id': project.display_name,
            'style="width: 30em" | City project': f'{{{{iconbox|{project.display_name}|{project.description}|image={project.get_wiki_filename()}}}}}',
            'Unlocked By': self.get_unlocked_by(project),
            'Base effect': project.effect,
            # 'class="unsortable" | Notes': self.create_wiki_list(project.notes),

        } for project in projects]
        result.append(self.get_SVersion_header(scope='table') + '\n'
                      + self.make_wiki_table(data, table_classes=['mildtable'],
                                             one_line_per_cell=True, row_id_key='id'))
        return result

    def get_domain_specialization_ideals_table(self, technologies):
        data = [{
            'id': tech.display_name,
            'Ideal': tech.display_name,
            'Tier': tech.layer,
            'Cost': tech.cost.format(icon_only=True),
            'Requirements': self.create_wiki_list(tech.requirements),
            # 'Unlocks': self.create_wiki_list([self.parser.all_entities[unlock].get_wiki_link_with_icon() for unlock in tech.unlocks]),
            'Effects': self.create_wiki_list(tech.all_effects),
            'class="hidem" | Description': 'class="hidem" | ' + tech.description,
        } for tech in technologies]
        return self.make_wiki_table(data, table_classes=['mildtable', 'plainlist'], one_line_per_cell=True,
                                    row_id_key='id')

    def get_domain_specializations_sections(self, spirit: DomainSpecialization):
        results = {}
        name = spirit.display_name.lower().replace(' ', '_')
        sorted_techs = spirit.technologies.values()
        for section, contents in {
                f'description_{name}': self.formatter.convert_to_wikitext(spirit.description),
                f'infopedia_{name}': self.formatter.convert_to_wikitext(spirit.infopedia),
                f'requirements_{name}': self.create_wiki_list(spirit.base_tech.requirements),
                # f'unlocks_{name}': self.create_wiki_list(
                #     [unlock.get_wiki_link_with_icon() for unlock in spirit.base_tech.unlocks_as_entities]),
                f'effects_{name}': self.create_wiki_list(spirit.base_tech.all_effects),
                f'ideals_{name}': '\n' + self.get_domain_specialization_ideals_table(sorted_techs)}.items():
            if contents:
                if section != 'requirements_space_agency':
                    results[section] = self.get_SVersion_header() + contents
        return results

    def generate_national_spirit_list(self):
        return self.generate_domain_specialization_list('National Spirits', self.parser.national_spirits, 'CONCEPT_SPECIALIZATIONS')

    def generate_government_list(self):
        return self.generate_domain_specialization_list('Governments', self.parser.governments, 'CONCEPT_GOVERNMENT')

    def get_national_spirit_sections(self):
        result = {}
        for spirit in self.parser.national_spirits.values():
            result.update(self.get_domain_specializations_sections(spirit))
        return result

    def get_governments_sections(self):
        result = {}
        for government in self.parser.governments.values():
            result.update(self.get_domain_specializations_sections(government))
        return result

    def generate_domain_specialization_list(self, domain_type: str, entities: dict[str, DomainSpecialization], main_article):
        results = [self.get_version_header(),
                   f'== {domain_type} ==',
                   self.surround_with_autogenerated_section(f'infopedia_{main_article}', self.parser.infopedia_topics[main_article].text),
                   '== Ideals ==',
                   self.surround_with_autogenerated_section('infopedia_CONCEPT_IDEALS', self.parser.infopedia_topics['CONCEPT_IDEALS'].text)
                   ]
        grouped_spirits = {}

        for name, spirit in entities.items():
            if spirit.age not in grouped_spirits:
                grouped_spirits[spirit.age] = {}
            if spirit.resource not in grouped_spirits[spirit.age]:
                grouped_spirits[spirit.age][spirit.resource] = []
            grouped_spirits[spirit.age][spirit.resource].append(spirit)
        for age, resources in sorted(grouped_spirits.items()):
            results.append(f'== Age {age}==')
            for resource, spirits in resources.items():
                if resource.name != 'ResDomainGovernment':
                    results.append(f'== {resource.display_name.removesuffix(" XP")}==')
                for spirit in spirits:
                    sections = self.get_domain_specializations_sections(spirit)
                    name = spirit.display_name.lower().replace(' ', '_')
                    results.append(f'=== {spirit} ===')
                    results.append(f'[[File:{spirit.get_wiki_image_filename()}|300px|right]]')  # TODO: change size back to 320px after the old images left the cache
                    results.append(f'==== Description ====')
                    results.append(sections[f'description_{name}'])
                    results.append(f'==== Infopedia ====')
                    results.append(sections[f'infopedia_{name}'])
                    if f'requirements_{name}' in sections and name != 'space_agency':  # TODO: space agency requirements only apply to some of the effects
                        results.append(f'==== Requirements ====')
                        results.append(sections[f'requirements_{name}'])
                    results.append(f'==== Effects ====')
                    results.append(f'These effects are applied when selecting {spirit}')
                    results.append(sections[f'effects_{name}'])
                    results.append(f'==== Ideals ====')
                    results.append(sections[f'ideals_{name}'])
        results.append('== References ==')
        results.append('<references />')
        results.append('[[Category:Government]]')
        return results

    def generate_goods_table(self):
        goods = [good for good in self.parser.goods.values() if not isinstance(good, GoodsTag) and good.name != 'TradeGoods2' and good.has_localized_display_name]
        data = [{
            'id': good.display_name,
            'class="unsortable"|': good.get_wiki_icon('40px'),
            'Good': good.display_name,
            'Consumed for': self.create_wiki_list(good.consumeValues),
            'Produced in': self.create_wiki_list([building.get_wiki_link_with_icon() for building in good.produced_in]),
            'class="unsortable" | Made from': self.create_wiki_list([item.get_wiki_link_with_icon() for item in good.made_from]),
            'Used in': self.create_wiki_list([building.get_wiki_link_with_icon() for building in good.used_in]),
            'class="unsortable" | Converted to': self.create_wiki_list([item.get_wiki_link_with_icon() for item in good.converted_to]),

        } for good in goods]
        return (self.get_SVersion_header(scope='table') + '\n'
                                                         + self.make_wiki_table(data, table_classes=['mildtable', 'plainlist'],
                                                                                one_line_per_cell=True, row_id_key='id'))

    def generate_card_tables(self):
        results = []
        for section, content in self.get_card_lists().items():
            results.append(f'== {section.capitalize().replace("_", " ")} events ==')
            results.append(self.surround_with_autogenerated_section(section, content))
        return results

    def get_card_lists(self):
        MAX_CHOICE_COLUMNS = 4
        sections = {deck_name.lower(): cards.values() for deck_name, cards in self.parser.event_cards.items()}
        results = {}
        for section, cards in sections.items():
            data = []
            for card in cards:
                if card.name == f'{card.deck_name}-AUTOMATIC':
                    # automatic cards are played each time that a card is drawn from the deck.
                    # This is used to reduce to apply INNOVATION_CARD_DECAY and CHAOS_CARD_DECAY
                    continue
                # if hasattr(card, 'count') and card.count == '0':
                #     continue
                row = {
                    'id': card.display_name,
                    'Title': card.display_name,
                    'Text': card.description,
                    'Deck': f'{card.deck_name.capitalize().replace("_", " ")}' if card.deck is None else card.deck.get_wiki_link_with_icon(),
                    'Requirements': self.create_wiki_list(card.requirements),
                    # 'Layer': card.layer if hasattr(card, 'layer') else '',
                }

                effects = card.get_effects(include_unlocks=True, recursive=True, group_by_choice=True)
                if len(effects) > MAX_CHOICE_COLUMNS:
                    print(f'More than {MAX_CHOICE_COLUMNS} choices in {card.name}')
                for choice_number in range(MAX_CHOICE_COLUMNS):
                    if len(effects) > choice_number:
                        effects_text = self.create_wiki_list(effects[choice_number])
                        if card.choice_localisations[choice_number]:
                            effects_text = f'{self.formatter.quote(card.choice_localisations[choice_number])}\n{effects_text}'
                    else:
                        effects_text = ''
                    row[f'Choice {choice_number+1}'] = effects_text
                data.append(row)
            results[section] = (self.get_SVersion_header(scope='table') + '\n'
                                + self.make_wiki_table(data, table_classes=['mildtable'], one_line_per_cell=True, row_id_key='id', remove_empty_columns=True))
        return results

    def generate_small_ages_table(self):
        data = [{
            'id': age.display_name,
            'width="96px" class="unsortable"|': age.get_wiki_icon('96px'),
            'Age': age.order,
            'Name': f'{age.get_wiki_link()}',
            'Type': age.type_loc,

        } for age in sorted(self.parser.ages.values(), key=attrgetter('order'))]
        return (self.get_SVersion_header(scope='table') + '\n'
                                                         + self.make_wiki_table(data, table_classes=['mildtable'],
                                                                                one_line_per_cell=True, row_id_key='id'))

    def generate_game_value_table(self):
        data = [{
            'id': game_value.name.removeprefix('#'),
            'Game Value': game_value.name,
            'Name': game_value.display_name if game_value.has_localized_display_name else '',
            'Base value': game_value.base,
            'Comment': f'<pre>{game_value.comment}</pre>' if game_value.comment else '',

        } for game_value in self.parser.game_values.values()]
        return (self.get_SVersion_header(scope='table') + '\n'
                + self.make_wiki_table(data, table_classes=['mildtable'],
                                       one_line_per_cell=True, row_id_key='id'))

    def generate_starting_bonus_table(self):
        """Not used on the wiki"""
        data = [{
            'id': bonus.display_name,
            'Bonus': bonus.display_name,
            'Effect': f'<section begin={bonus.transclude_section_name} />' + re.sub(r'\[\[MENU_[A-Z_]*\|([^]]*]])', '', self.formatter.convert_to_wikitext(
                bonus.description)) + f'<section end={bonus.transclude_section_name} />',
        } for bonus in self.parser.startup_bonuses.values()]
        return (self.get_SVersion_header() + '\n'
                + self.make_wiki_table(data, table_classes=['mildtable'],
                                       one_line_per_cell=True, row_id_key='id'))

    def generate_nation_table(self):
        data = [{
            'id': nation.display_name,
            'Nation': f"'''{nation.display_name}'''",
            'Flag !! Bonus !! Effect': nation.get_wiki_file_tag('30px') + f'\n{{{{#lst:Nations|{nation.startupBonuses[0].transclude_section_name}}}}}',
            'AI Personality': nation.personality_loc,
            'City Names': f'{nation.cityNameCollection.display_name}{{{{collapse|{self.create_wiki_list(nation.cityNameCollection.localized_names)}}}}}',
            'Town Names': f'{nation.townNameCollection.display_name}{{{{collapse|{self.create_wiki_list(nation.townNameCollection.localized_names)}}}}}',
        } for nation in sorted(self.parser.nations.values(), key=attrgetter('display_name')) if nation.name != 'random']
        return (self.get_SVersion_header() + '\n'
                + self.make_wiki_table(data, table_classes=['mildtable'],
                                       one_line_per_cell=True, row_id_key='id'))

    def generate_terrain_table(self):
        """Incomplete and not used on the wiki"""
        data = [{
            'id': terrain.display_name,
            'width=1% class="unsortable" |': terrain.get_wiki_file_tag('64px'),
            'width=10% | Tile': terrain.display_name,
            'Foraging': '',
            'Gathering': self.create_wiki_list([f'{gather.display_name}: {gather.goods.get_wiki_icon()} {gather.amount} {gather.goods.display_name}' for gather in terrain.gathers]),
            ' Potential Good ': '',
            ' Potential Landmark': '',
            ' Allows Improvements': '',
            ' Combat modifier': '',
            ' Terrain type expansion cost': '',
            ' Movement cost': '',
            ' Allows town?': '',
        } for terrain in self.parser.terrains.values()]
        return (self.get_SVersion_header() + '\n'
                + self.make_wiki_table(data, table_classes=['mildtable'],
                                       one_line_per_cell=True, row_id_key='id'))


if __name__ == '__main__':
    generator = TableGenerator()
    generator.run(sys.argv)