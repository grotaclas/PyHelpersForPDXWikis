import re
from decimal import Decimal

from common.paradox_lib import NameableEntity
from common.paradox_parser import Tree
from eu5.eu5lib import Resource, HardcodedResource, Eu5AdvancedEntity
from eu5.game import eu5game
from vic3.text_formatter import Vic3WikiTextFormatter


class Eu5WikiTextFormatter(Vic3WikiTextFormatter):

    def __init__(self):
        self.parser = eu5game.parser

    def localize_concept_name(self, concept_name):
        return self.parser.localize('game_concept_' + concept_name.removesuffix('_with_icon'))

    def _replace_icons(self, match: re.Match) -> str:
        icon_key = match.group(1).lower().replace('_', ' ')
        return f'{{{{icon|{icon_key}}}}}'


    def _resolve_data_function(self, data_function: str, parameter: str, name_function: str = None):
        if data_function in ['GetEstateNameWithNoTooltip', 'GetEstateName']:
            return self.parser.estates[parameter].display_name
        if data_function in ['ShowSocietyDirectionName']:
            return self.parser.localize(f'{parameter}_focus')
        return self.parser.localize(parameter)

    def apply_localization_formatting(self, text: str) -> str:
        text = super().apply_localization_formatting(text)
        text = re.sub(r"\[\s*(?P<data_function>(Show|Get)[a-zA-Z_]+)\s*\(\s*'(?P<loc_key>[^']+)'\s*\)(.(?P<name_function>(GetNameWithNoTooltip|GetLongNameWithNoTooltip)))?\s*]",
                      lambda match: self._resolve_data_function(match.group('data_function'), match.group('loc_key'), match.group('name_function')), text)

        return text

    def resolve_nested_localizations(self, text: str, seen_keys=None):
        # dont treat BULLET_WITH_TAB as a nested loc, so that we can turn it into a wiki list
        text = re.sub(r"\\n\$BULLET_WITH_TAB\$", '\n* ', text)
        text = re.sub(r"\\n\$BULLET\$", '\n* ', text)
        return super().resolve_nested_localizations(text, seen_keys)

    def format_resource(self, resource: str | Resource, value=None, cost=False, icon_only=False, add_plus=False):
        if  isinstance(resource, str):
            resource = HardcodedResource(resource)
        if value is None:
            value_str = ''
        elif isinstance(value, str) and not self.is_number(value):
            value_str = f' {value}'
        else:
            positive_is_good = resource.positive_is_good
            if cost:
                positive_is_good = not positive_is_good
            value_str = f' {self.add_red_green(value, positive_is_good=positive_is_good, add_plus=add_plus)}'

        icon_str = resource.get_wiki_icon()
        if icon_only:
            name_str = ''
        else:
            name_str = f' {resource.display_name}'
        return f'{icon_str}{value_str}{name_str}'

    def format_resource_without_value(self, resource: str, icon_only=False):
        return self.format_resource(resource, icon_only=icon_only)

    def format_cost(self, resource: str, value: int, icon_only=False):
        return self.format_resource(resource, value, cost=True, icon_only=icon_only)

    def format_trigger(self, trigger: Tree|None):
        if not trigger:
            return ''
        if isinstance(trigger, list):
            if len(trigger) == 1:
                return self.format_conditions(trigger[0])
            result = []
            for condition in trigger:
                if isinstance(condition, Tree):
                    result.append(self.format_conditions(condition, indent=2))
                else:
                    result.append(condition)
            return self.create_wiki_list(result)
        return self.format_conditions(trigger)

    def format_effect(self, effect: Tree|None):
        if not effect:
            return ''
        return self.format_trigger(effect)

    def format_simple_statement(self, key, value):
        return f'{key}: {self.format_RHS(value)}'

    def format_RHS(self, value) -> str:
        suffix = None
        if isinstance(value, str) and ':' in value:
            typ, _, value_without_prefix = value.partition(':')
            value_without_prefix_and_suffix, _seperator, suffix = value_without_prefix.partition('.')
            type_sources = {
                'building_type': self.parser.buildings,
                'c': self.parser.countries_including_formables,
                'culture': self.parser.cultures,
                'culture_group': self.parser.culture_groups,
                'estate_privilege': self.parser.estate_privileges,
                'estate_type': self.parser.estates,
                'goods': self.parser.goods,
                'languages': self.parser.languages,
                'religion': self.parser.religions,
                'religion_group': self.parser.religion_groups,
            }
            if typ in type_sources:
                value = type_sources[typ][value_without_prefix_and_suffix]
            else:
                suffix = None  # we use the unchanged value, so we don't want to add the suffix to it
        if isinstance(value, Eu5AdvancedEntity):
            value = value.get_wiki_link_with_icon()
        elif isinstance(value, NameableEntity):
            value = value.display_name
        if suffix:
            return f'{value}.{suffix}'
        else:
            return value
