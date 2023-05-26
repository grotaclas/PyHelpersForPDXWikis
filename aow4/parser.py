import json
import inspect
import re
import sys
from gettext import GNUTranslations
from typing import Callable, TypeVar, Type
from functools import cached_property

from PyHelpersForPDXWikis.localsettings import AOW4DATADIR, AOW4DIR
from aow4.aow4lib import *
from common.paradox_lib import NameableEntity
from common.paradox_parser import Tree
NE = TypeVar('NE', bound=NameableEntity)
IE = TypeVar('IE', bound=IconEntity)


class AoW4Parser:

    @cached_property
    def formatter(self):
        from aow4.text_formatter import AoW4WikiTextFormatter
        return AoW4WikiTextFormatter()

    def read_json(self, file: str):
        with open(AOW4DATADIR / (file + '.json'), encoding='utf-8') as skill_file:
            return json.load(skill_file, object_hook=lambda x: Tree(x))

    @cached_property
    def _localization(self) -> GNUTranslations:
        with open(AOW4DIR / 'Language/EN/EN.MO', 'rb') as mofile:
            return GNUTranslations(mofile)

    def localize(self, key: str, default: str = None, loc_prefix: str = 'INTERFACE@TEXT@') -> str:
        """localize the key from the english localization files

        if the key is not found, the default is returned
        unless it is None in which case the key is returned
        """
        if default is None:
            default = key
        message = loc_prefix + key.upper()
        localization = self._localization.gettext(message)
        if localization == message and default:
            return default
        return  localization

    def parse_nameable_entities(self, folder: str, entity_class: Type[NE], name_column: str = 'id',
                                extra_data_functions: dict[str, Callable[[str, dict], any]] = None,
                                transform_value_functions: dict[str, Callable[[any], any]] = None) -> dict[str, NE]:
        """parse a folder into objects which are subclasses of NameableEntity

        Args:
            folder: relative to the 'steamapps/common/Victoria 3/game' folder
            entity_class: each entry in the files will create one of these objects. All the data will be passed as
                          keyword arguments to the constructor. If the NameableEntity constructor is not overridden, it
                          will turn these arguments into properties of the object
            extra_data_functions: create extra entries in the data. For each key in this dict, the corresponding function
                                  will be called with the name of the entity and the data dict as parameter. The return
                                  value will be added to the data dict under the same key
            transform_value_functions: the functions in this dict are called with the value of the data which matches
                                       the key of this dict. If the key is not present in the data, the function won't
                                       be called. The function must return the new value for the data

        Returns:
            a dict between the top level keys in the folder and the entity_class objects which were created from them
        """
        if extra_data_functions is None:
            extra_data_functions = {}
        if transform_value_functions is None:
            transform_value_functions = {}
        if 'display_name' not in extra_data_functions:
            extra_data_functions['display_name'] = lambda entity_name, entity_data: entity_data['name']
        entities = {}
        class_attributes = inspect.get_annotations(entity_class)
        for data in self.read_json(folder):
            entity_values = {}
            name = data[name_column]
            for key, func in extra_data_functions.items():
                entity_values[key] = func(name, data)
            for k, v in data:
                if k in transform_value_functions:
                    entity_values[k] = transform_value_functions[k](v)
                elif k in class_attributes and k not in entity_values:
                    entity_values[k] = v
            entities[name] = entity_class(name, **entity_values)
        return entities

    def parse_icon(self, name, data, possible_icon_keys: list[str] = None):
        if possible_icon_keys is None:
            possible_icon_keys = ['icon', 'texture']
        for icon_key in possible_icon_keys:
            if icon_key in data:
                return data[icon_key] + '.png'
        return ''

    def parse_icon_entities(self, folder: str, entity_class: Type[IE], name_column: str = 'id',
                                extra_data_functions: dict[str, Callable[[str, Tree], any]] = None,
                                transform_value_functions: dict[str, Callable[[any], any]] = None
                                ) -> dict[str, IE]:
        if extra_data_functions is None:
            extra_data_functions = {}
        if 'icon' not in extra_data_functions:
            extra_data_functions['icon'] = self.parse_icon
        return self.parse_nameable_entities(folder, entity_class, name_column=name_column,
                                            extra_data_functions=extra_data_functions,
                                            transform_value_functions=transform_value_functions)

    @cached_property
    def hero_skills(self) -> dict[str, HeroSkill]:
        skills = self.parse_icon_entities('Hero Skills', HeroSkill, transform_value_functions={
            'abilities': lambda ability_list: [self.abilities[ability['slug']] for ability in ability_list],
            'description': lambda desc: self.formatter.convert_to_wikitext(desc),
        })
        # remove empty entry
        del skills['']
        return skills

    @cached_property
    def abilities(self) -> dict[str, Ability]:
        return self.parse_icon_entities('Abilities', Ability, name_column='slug')

    @cached_property
    def spells(self) -> dict[str, Spell]:
        return self.parse_icon_entities('Spells', Spell, transform_value_functions={
            'description': lambda desc: self.formatter.convert_to_wikitext(desc),
            'upkeep': lambda upkeep: re.sub(r'([0-9]*)<mana></mana>\s*', r"{{icon|mana}} '''\1'''", upkeep),
            'casting_cost': lambda cost: re.sub(r'([0-9]*)<([^>]*)></\2>\s*', r"{{icon|\2}} '''\1'''", cost),
            'enchantment_requisites': lambda reqs: [self.formatter.convert_to_wikitext(req['requisite']) for req in reqs],
            'summoned_units': lambda units: [unit['slug'] for unit in units],
        }, extra_data_functions={
            'spell_type': lambda name, data: re.sub(
                r'<cast(strategic|tactical)></cast(strategic|tactical)> <hyperlink>(?P<spelltype>.*?)</hyperlink>', r'\g<spelltype>',
                data['spellType']),
            'tome': lambda name, data: self._get_tome_and_tier_for_spell(name, data['name'])[0],
            'tier': lambda name, data: self._get_tome_and_tier_for_spell(name, data['name'])[1],
        })

    def _parse_tomb_skills(self, skills):
        skill_objects = []
        for skill in skills:
            if 'spell_slug' in skill:
                slug = skill['spell_slug']
                skill_type = 'spell'
            elif 'siege_project_slug' in skill:
                slug = skill['siege_project_slug']
                skill_type = 'siege_project'
            elif 'unit_slug' in skill:
                slug = skill['unit_slug']
                skill_type = 'unit'
            elif 'upgrade_slug' in skill:
                slug = skill['upgrade_slug']
                skill_type = 'upgrade'
            elif 'Siege Project<' in skill['type']:
                slug = skill['name']
                skill_type = 'siege_project'
            elif 'Sustained City Spell' in skill['type']:
                slug = skill['name']
                skill_type = 'spell'
            else:
                print(f'Error: unhandled skill type in tomb: {skill.dictionary}', file=sys.stderr)
                continue
            skill_objects.append(TomeSkill(slug, skill['name'], skill['tier'], skill_type, self.formatter.convert_to_wikitext(skill['type']), self.formatter.convert_to_wikitext(skill['description'])))
        return skill_objects

    @staticmethod
    def _parse_affinity(tome_name: str, tome_data):
        if 'affinities' in tome_data:
            match = re.fullmatch(r'<empire(?P<affinity>[^>]*)></empire(?P=affinity)>\s*(?P<value>[0-9]+)\s*',
                                 tome_data['affinities'])
            if match:
                return match.group('affinity'), int(match.group('value'))
            else:
                raise Exception(f'Error: cant parse affinities "{tome_data["affinities"]}" in tome "{tome_name}"')
        else:
            # generic/cultural tomes
            return '', 0

    def _get_affinity_type_str(self, tome_name: str, tome_data):
        return self._parse_affinity(tome_name, tome_data)[0]

    def _get_affinity_value(self, tome_name: str, tome_data):
        return self._parse_affinity(tome_name, tome_data)[1]

    @cached_property
    def tomes(self) -> dict[str, Tome]:
        tomes = self.parse_icon_entities('Tomes', Tome, name_column='id', transform_value_functions={
            'skills': self._parse_tomb_skills,
            'hero_skills': lambda skills: [self.hero_skills[skill['slug']] for skill in skills],
            'gameplay_description': self.formatter.convert_to_wikitext
        }, extra_data_functions={
            'affinity_value': self._get_affinity_value,
            'affinity_type_str': self._get_affinity_type_str,
        })
        # remove empty entry
        del tomes['']
        return tomes

    def _get_tome_and_tier_for_spell(self, name: str, display_name):
        if name in self.spells_to_tome_and_tier:
            return self.spells_to_tome_and_tier[name]
        if display_name in self.spells_to_tome_and_tier:
            return self.spells_to_tome_and_tier[display_name]
        else:
            return None, None

    @cached_property
    def spells_to_tome_and_tier(self) -> dict[str, tuple[Tome, int]]:
        mapping = {}
        for tome in self.tomes.values():
            for skill in tome.skills:
                if skill.skill_type == 'spell':
                    mapping[skill.slug] = (tome, skill.tier)
        return mapping

    @cached_property
    def hero_skills_to_tome(self) -> dict[str, Tome]:
        mapping = {}
        for tome in self.tomes.values():
            for skill in tome.hero_skills:
                mapping[skill.name] = tome
        return mapping

    @cached_property
    def affinities(self):
        names = {tome.affinity_type_str for tome in self.tomes.values() if tome.affinity_type_str}
        return {name: Affinity(name, self.localize(name)) for name in names}
