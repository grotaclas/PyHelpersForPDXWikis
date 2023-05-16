import os
import sys
from operator import attrgetter
# add the parent folder to the path so that imports work even if this file gets executed directly
sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

from aow4.aow4_file_generator import AoW4FileGenerator
from aow4.aow4lib import HeroSkill, Affinity
from aow4.text_formatter import AoW4WikiTextFormatter


class TableGenerator(AoW4FileGenerator):

    @property
    def formatter(self) -> AoW4WikiTextFormatter:
        return self.parser.formatter

    def _get_hero_kill_effect(self, skill: HeroSkill):
        effect = ''
        if skill.description:
            effect += skill.description
        if skill.abilities:
            effect += 'Ability: ' + ', '.join([ability.get_wiki_link() for ability in skill.abilities])

        return effect

    def get_skills_with_category(self) -> dict[str, list[HeroSkill]]:
        skills = {}
        for skill in sorted(self.parser.hero_skills.values(), key=attrgetter('group_name', 'display_name')):
            if skill.category_name not in skills:
                skills[skill.category_name] = []
            skills[skill.category_name].append(skill)
        return skills

    def generate_hero_skills_table(self) -> str:
        result = ''
        descriptions = {'Battle Magic': 'Battle Magic skills focus on granting the hero magical attacks and improving its spellcasting capabilities.',
                        'Support': 'Support skills focus on granting bonuses to the army the hero is leading.',
                        'Warfare': 'Warfare skills focus on making the hero more dangerous in physical combat.',
                        }
        for category, skills in self.get_skills_with_category().items():
            if category:
                if category not in descriptions:  # ignore other categories for now, because they are already manually created
                    continue
                result += f'=== {category} skills ===\n'
                result += f'{descriptions[category]}\n'
                data = [{
                    'Skill': f'data-sort-value="{skill.display_name}" | {skill.get_wiki_icon("40px")} {skill.display_name}',
                    'Source': skill.tome.get_wiki_link_with_icon() if skill.tome else skill.group_name,
                    'Level': skill.level_name,
                    'Effect': self._get_hero_kill_effect(skill),
                } for skill in skills]
            else:  # signature skills (ignored for now)
                continue
                # result += f'=== Signature skills ===\n'
                # data = [{
                #     'Skill': f'data-sort-value="{skill.display_name}" | {skill.get_wiki_icon("40px")} {skill.display_name}',
                #     'Ability': ', '.join([ability.get_wiki_link() for ability in skill.abilities]),
                # } for skill in skills]

            result += self.make_wiki_table(data, table_classes=['mildtable', 'plainlist'],
                                           one_line_per_cell=True,
                                           )
        return result

    def generate_spell_tables(self):
        return '== Strategic spells ==\n' + self.get_spell_tables(False) + \
            '\n== Tactical spells ==\n' + self.get_spell_tables(True)

    def get_spell_tables(self, tactical: bool):
        spells = {}
        for spell in sorted(self.parser.spells.values(), key=attrgetter('spell_type', 'display_name')):
            if spell.tactical == tactical:
                if spell.spell_type not in spells:
                    spells[spell.spell_type] = []
                spells[spell.spell_type].append(spell)

        result = ''
        for category, spells_in_category in spells.items():
            result += f'=== {category} ===\n'
            result += self.get_spell_table(spells_in_category)
            result += '\n'
        return result

    def get_spell_table(self, spells):
        data = [{
            'Spell': f'data-sort-value="{spell.display_name}" | {spell.get_wiki_icon("40px")} {spell.display_name}',
            'Tome': spell.tome.get_wiki_link() if spell.tome else '',
            'Tier': f'{spell.tier}' if spell.tier else '',
            'Requirements': self.create_wiki_list(spell.enchantment_requisites),
            'Casting cost': spell.casting_cost,
            'Operation point cost':  '' if spell.operation_point_cost == 0 else f"'''{spell.operation_point_cost}'''",
            'Upkeep': spell.upkeep,
            # the description seems to have enough info about the units
            # 'Summoned units': self.create_wiki_list([f'{{{{Unit|Tooltip|{unit}}}}}' for unit in spell.summoned_units])
            # 'Summoned units': self.create_wiki_list(spell.summoned_units),
            'Description': spell.description,
        } for spell in spells]

        return self.make_wiki_table(data, table_classes=['mildtable'],
                                    one_line_per_cell=True, remove_empty_columns=True)

    def generate_tome_table(self, affinity: Affinity | None):
        if affinity:
            affinity_short_name = affinity.display_name.removesuffix(' Affinity')
        else:
            affinity_short_name = 'Generic or cultural'

        result = [f'= {affinity_short_name} tomes =']
        for tome in sorted([tome for tome in self.parser.tomes.values() if tome.affinity == affinity], key=attrgetter('tier', 'display_name')):
            result.append(f'== {tome} ==')
            result.append(f'{{{{main|{tome}}}}}')
            if tome.tier:
                # if tome.tier:
                #     result.append(f'Tier {tome.tier}')
                # tier_prefix = f'{self.formatter.format_roman(tome.tier)} - '
                tier_prefix = f"'''Tier {tome.tier}''' - "
            else:
                tier_prefix = ''
            result.append(f"{{|\n|-\n| {tome.get_wiki_file_tag('64px')} || {tier_prefix}''{tome.gameplay_description}''\n|}}""")
            result.append(f'=== Skills ===')
            skills = [{
                'class="unsortable" width=1% |': skill.get_wiki_icon("40px"),
                'Skill': skill.get_wiki_link(),
                'Tier': '',
                'Type': skill.level_name,
                'Effects': self._get_hero_kill_effect(skill),
            } for skill in tome.hero_skills]

            skills.extend([{
                'class="unsortable" width=1% |': skill.object.get_wiki_icon("40px"),
                'Skill': skill.get_wiki_link(),
                'Tier': f'{skill.tier}' if skill.tier else '',
                'Type': skill.type_desc,
                'Effects': skill.object.description,
                # TODO add additional info for different types of skills. The following are used in the spells table for example:
                # 'Requirements': self.create_wiki_list(skill.enchantment_requisites),
                # 'Casting cost': skill.casting_cost,
                # 'Operation point cost':  '' if skill.operation_point_cost == 0 else f"'''{skill.operation_point_cost}'''",
                # 'Upkeep': skill.upkeep,
            } for skill in sorted(tome.skills, key=attrgetter('tier', 'skill_type', 'display_name'))])
            result.append(self.make_wiki_table(skills, table_classes=['mildtable'],
                                               one_line_per_cell=True, remove_empty_columns=True))
        return result


    def generate_tome_tables(self):
        result = []
        for affinity in sorted(self.parser.affinities.values()):
            result.extend(self.generate_tome_table(affinity))
        result.extend(self.generate_tome_table(None))
        return result


if __name__ == '__main__':
    generator = TableGenerator()
    generator.run(sys.argv)
