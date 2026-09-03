import re
import sys
from functools import cached_property

from common.paradox_lib import AdvancedEntity, NameableEntity
from common.paradox_parser import Tree
from common.wiki import WikiTextFormatter
from vic3.vic3_file_generator import vic3game, Vic3FileGenerator
from vic3.vic3lib import Vic3AdvancedEntity, Event, Option


class Vic3WikiTextFormatter(WikiTextFormatter):

    def __init__(self):
        self.parser = vic3game.parser

    def format_localization_text(self, text: str, concepts_in_same_article: list[str] = None):
        """

        @param text: the text which should be formatted
        @param concepts_in_same_article: these strings will use a link starting with #
        """
        if concepts_in_same_article is None:
            concepts_in_same_article = []
        previous_text = None
        # some concept localizations use other localizations themselves.
        # So we replace till nothing changes anymore (and hope that there is no loop)
        while previous_text != text:
            previous_text = text
            # the next line doesn't really fit here, but it has to be done early,
            # because it matches the [concept] formating which comes afterwards
            text = text.replace('[Nbsp]', '&nbsp;')
            text = re.sub(
                r"(?<!\[)\[\s*(Concept\s*\(\s*')?(?P<concept_name>[^]|']*)('\s*,\s*'(?P<concept_display_string>[^']*)'\s*\))?\s*(?P<formatting>\|[leE])?\s*](?!])",
                # r"\[\s*Concept\s*\(\s*'(?P<concept_name>[^]']*)('\s*,\s*'(?P<concept_display_string>[^']*)'\s*\))?\s*(?P<formatting>\|[l])?\s*]",
                self.get_concept_link, text)
            text = self.resolve_nested_localizations(text)
            text = self.apply_localization_formatting(text)
        def make_relative_links(match: re.Match):
            target = match.group(1)
            if match.group(2) is not None:
                link_name = match.group(2).removeprefix('|')
            else:
                link_name = target
            if target in concepts_in_same_article:
                return f'[[#{target}|{link_name}]]'
            elif target == link_name:
                return f'[[{link_name}]]'
            else:
                return f'[[{target}|{link_name}]]'

        text = re.sub(r'\[\[([^]|]+)(\|[^]]+)?]]', make_relative_links,
                      text)
        return text

    def _apply_formatting_markers(self, match: re.Match) -> str:
        format_key = match.group(1).lower()
        text = match.group(2)
        replacements = {'p': '{{{{green|{}}}}}',
                        'g': '{{{{green|{}}}}}',
                        'n': '{{{{red|{}}}}}',
                        'r': '{{{{red|{}}}}}',
                        'bold': "'''{}'''",
                        'b': "'''{}'''",
                        'italic': "''{}''",
                        'v': '{}',  # white
                        'y': '{}',  # zero_value / white
                        'z': '{}',  # zero_value / white
                        'e': '{}',  # explanation_link in ck3 / TODO: this is normally blue, but we don't want to make it blue if it is a normal link, because they are already blue
                        }
        if format_key not in replacements:
            Vic3FileGenerator.warn('ignoring unknown formatting marker {} in "{}"'.format(format_key, match.group(0)))
            return text
        else:
            return replacements[format_key].format(text)

    def _replace_icons(self, match: re.Match) -> str:
        icon_key = match.group(1).lower()
        replacements = {'aut': 'authority',
                        'bur': 'bureaucracy',
                        'construction': 'construction',
                        'green_checkmark_box': 'yes',
                        'inf': 'influence',
                        'information': 'info',
                        'innovation': 'innovation',
                        'convoys': 'convoys',
                        # pop types
                        'academics': 'academics',
                        'aristocrats': 'aristocrats',
                        'bureaucrats': 'bureaucrats',
                        'capitalists': 'capitalists',
                        'clergymen': 'clergymen',
                        'clerks': 'clerks',
                        'engineers': 'engineers',
                        'farmers': 'farmers',
                        'laborers': 'laborers',
                        'machinists': 'machinists',
                        'officers': 'officers',
                        'peasants': 'peasants',
                        'shopkeepers': 'shopkeepers',
                        'slaves': 'slaves',
                        'soldiers': 'servicemen',
                        # goods
                        'aeroplanes': 'aeroplanes',
                        'ammunition': 'ammunition',
                        'artillery': 'artillery',
                        'automobiles': 'automobiles',
                        'clippers': 'clippers',
                        'clothes': 'clothes',
                        'coal': 'coal',
                        'coffee': 'coffee',
                        'dye': 'dye',
                        'electricity': 'electricity',
                        'engines': 'engines',
                        'explosives': 'explosives',
                        'fabric': 'fabric',
                        'fertilizer': 'fertilizer',
                        'fine_art': 'fine art',
                        'fish': 'fish',
                        'fruit': 'fruit',
                        'furniture': 'furniture',
                        'glass': 'glass',
                        'gold': 'gold',
                        'grain': 'grain',
                        'groceries': 'groceries',
                        'hardwood': 'hardwood',
                        'ironclads': 'ironclads',
                        'iron': 'iron',
                        'lead': 'lead',
                        'liquor': 'liquor',
                        'luxury_clothes': 'luxury clothes',
                        'luxury_furniture': 'luxury furniture',
                        'manowars': 'man-o-wars',
                        'meat': 'meat',
                        'money': 'money',
                        'oil': 'oil',
                        'opium': 'opium',
                        'paper': 'paper',
                        'porcelain': 'porcelain',
                        'radios': 'radios',
                        'radio': 'radios',
                        'rubber': 'rubber',
                        'services': 'services',
                        'silk': 'silk',
                        'small_arms': 'small arms',
                        'steamers': 'steamers',
                        'steel': 'steel',
                        'sugar': 'sugar',
                        'sulfur': 'sulfur',
                        'tanks': 'tanks',
                        'tea': 'tea',
                        'telephones': 'telephones',
                        'tobacco': 'tobacco',
                        'tools': 'tools',
                        'transportation': 'transportation',
                        'wine': 'wine',
                        'wood': 'wood',
                        #new
                        'acceptance_status_1': 'acceptance_status_1',
                        'acceptance_status_2': 'acceptance_status_2',
                        'acceptance_status_3': 'acceptance_status_3',
                        'acceptance_status_4': 'acceptance_status_4',
                        'acceptance_status_5': 'acceptance_status_5',
                        'merchant_marine': 'merchant marine',
                        'warning': 'warning',
                        }
        if icon_key not in replacements:
            Vic3FileGenerator.warn('unknown icon {} in "{}"'.format(icon_key, match.group(0)))
            return match.group(0)
        else:
            return '{{icon|' + replacements[icon_key] + '}}'

    def _replace_defines(self, match: re.Match) -> str:
        category = match.group('category')
        define = match.group('define')
        if category in self.parser.defines and define in self.parser.defines[category]:
            value = self.parser.defines[category][define]
        else:
            Vic3FileGenerator.warn(f'unknown define "{category}.{define}" in "{match.group(0)}"')
            return match.group(0)
        prefix = ''
        suffix = ''
        formatting = match.group('formatting')
        if not formatting:
            return str(value)
        if 'K' in formatting:
            value = value / 1000
            suffix = 'K'
        if '%' in formatting:
            value = value * 100
            suffix = '%'
        if '=-' in formatting:
            if value > 0:
                prefix = '{{red|+' + prefix
                suffix += '}}'
            elif value < 0:
                prefix = '{{green|' + prefix
                suffix += '}}'
        if '=+' in formatting:
            if value > 0:
                prefix = '{{green|+' + prefix
                suffix += '}}'
            elif value < 0:
                prefix = '{{red|' + prefix
                suffix += '}}'

        return '{}{}{}'.format(prefix, value, suffix)

    def _add_optional_localization(self, match: re.Match) -> str:
        # ingame_added are usually texts specific to the situation in the player's country
        if match.group('loc_key').endswith('ingame_added'):
            return ''
        else:
            return self.parser.localize(match.group('loc_key'))

    def apply_localization_formatting(self, text: str) -> str:
        text = re.sub(r"\[\s*(SelectLocalization|AddLocalizationIf)\s*\(\s*GetPlayer\.IsValid\s*,\s*'(?P<loc_key>[^']*)'[^]]*]",
                      self._add_optional_localization, text)

        # various special cases
        text = re.sub(r'(\\n){2,}', '\n\n', text)
        text = re.sub(r'\\n', '<br />', text)
        text = text.replace(r"\\'", "'")

        # to support nested formatting, we loop as long as something changes
        previous_text = None
        new_text = text
        while previous_text != new_text:
            previous_text = new_text
            # only matches the inner formatting. The others will be done in future loops
            new_text = re.sub(r'#(\S+) ([^#]+)#!', self._apply_formatting_markers, previous_text)

        text = re.sub(r'@([^!]*)!', self._replace_icons, new_text)
        text = re.sub(r"\[\s*GetDefine\s*\(\s*'(?P<category>[^']*)'\s*,\s*'(?P<define>[^']*)'\s*\)\s*(\|\s*(?P<formatting>[-vK0+=%W]+))?\s*]",
                      self._replace_defines, text)
        text = re.sub(r"\[\s*Get[a-zA-Z_]+\s*\(\s*'(?P<loc_key>[^']+)'\s*\).GetName\s*]",
                      lambda match: self.parser.localize(match.group('loc_key')), text)
        text = re.sub(r"\[\s*GetLawType\s*\(\s*'(?P<law_key>[^']+)'\s*\).GetGroup.GetName\s*]",
                      lambda match: self.parser.laws[match.group('law_key')].group.display_name, text)
        text = re.sub(r"\[\s*GetInterestGroupVariant\s*\(\s*'(?P<ig_key>[^']+)'\s*,\s*GetPlayer\s*\).GetNameWithCountryVariant\s*]",
                      lambda match: self.parser.interest_groups[match.group('ig_key')].display_name, text)
        return text

    def resolve_nested_localizations(self, text: str, seen_keys = None) -> str:
        if seen_keys is None:
            seen_keys = set()
        def resolve_replacement(match: re.Match) -> str:
            key_to_replace = match.group(1)
            if key_to_replace in seen_keys:
                print(f'Recursive localisation "{key_to_replace}" when resolving "{text}"', file=sys.stderr)
                return key_to_replace
            return  self.resolve_nested_localizations(self.parser.localize(key_to_replace), seen_keys | {key_to_replace})
        previous_text = None
        new_text = text
        # some localizations use other localizations themselves.
        # so we replace till nothing changes anymore (and hope that there is no loop)
        while previous_text != new_text:
            previous_text = new_text
            new_text = re.sub(r'\$([^$]*)\$', resolve_replacement, previous_text)
            new_text = re.sub(r"\[Localize\('([^']+)'\)]", resolve_replacement, new_text, flags=re.IGNORECASE)

        return new_text

    def get_concept_link(self, match: re.Match) -> str:
        concept_name = match.group('concept_name')
        link = self.localize_concept_name(concept_name)
        display_str = match.group('concept_display_string')
        if display_str is None:
            display_str = link
        else:
            display_str = self.resolve_nested_localizations(display_str)
        if match.group('formatting') == '|l':
            display_str = display_str[0].lower() + display_str[1:]

        # if display_str == link:
        #     return f'[[{link}]]'
        # else:
        #     return f'[[{link}|{display_str}]]'
        # return f'[[#{link}|{display_str}]]'
        return f'[[{link}|{display_str}]]'


    def strip_formatting(self, text, strip_newlines=False):
        return super().strip_formatting(self.format_localization_text(text, []), strip_newlines)

    def localize_concept_name(self, concept_name):
        return self.parser.localize(concept_name)

    def format_conditions(self, conditions: Tree, indent: int = 1):
        result = []
        for key, value in conditions.iterate_with_duplicates():
            result.append(self.format_key_value_pair(key, value, indent))
        return self.create_wiki_list(result, indent)

    def format_key_for_compound_statement(self, key):
        key_mappings = {
            'OR': 'At least one of',
            'NOR': 'Neither of',
            'AND': 'All of',
            'NOT': 'Not',
        }
        if key in key_mappings:
            return key_mappings[key]
        else:
            # print(f'Notice: Unhandled compound key "{key}"')
            return key

    @cached_property
    def entities_with_prefix(self):
        return {'law_type:' + law.name: law for law in self.parser.laws.values()}

    def format_simple_statement(self, key, value):
        mapping = {
            'has_converting_pops': f'{"Has" if value else "does not have"} converting pops',
            'has_assimilating_pops': f'{"Has" if value else "does not have"} assimilating pops',
            'is_isolated_from_market': f'Is {"" if value else "not "}an isolated state',
            'has_decree': ('Has the decree {value}', self.parser.decrees),
            'has_law': ('Has the law {value}', self.entities_with_prefix)
        }
        if key in mapping:
            if isinstance(mapping[key], str):
                return mapping[key]
            else:
                value = mapping[key][1][value]
                value = self.format_RHS(value)
                return mapping[key][0].format(value=value)
        else:
            return f'{key}: {self.format_RHS(value)}'

    def format_key_value_pair(self, key: str, value, indent):

        if isinstance(value, Tree):
            return self.format_key_for_compound_statement(key) + ':' + self.format_conditions(value, indent + 1)
        elif isinstance(value, list):
            return self.create_wiki_list([self.format_key_value_pair(key, inner_value, indent + 1) for inner_value in value], indent)
        elif isinstance(value, AdvancedEntity):
            return self.format_simple_statement(key, value.get_wiki_link_with_icon())
        # elif isinstance(value, (int, float, str)):
        else:
            return self.format_simple_statement(key, value)

    def format_RHS(self, value) -> str:
        if isinstance(value, str) and ':' in value:
            typ, value_without_prefix = value.split(':')
            match typ:
                case 'c':
                    value = self.parser.countries[value_without_prefix]
                case 's':
                    value = self.parser.states[value_without_prefix]
                case 'rel':
                    value = self.parser.religions[value_without_prefix]
        if isinstance(value, Vic3AdvancedEntity):
            value = value.get_wiki_link_with_icon()
        elif isinstance(value, NameableEntity):
            value = value.display_name

        return value

    def format_event(self, event: 'Event') -> str:
        """Format an Event object into the {{event}} wiki template.

        Args:
            event: the Event object to format

        Returns:
            wiki text for the event
        """

        lines = ["{{event"]
        lines.append(f"|version = {event.version if event.version else self.parser.game.version}")
        lines.append(f"|event_id = {event.event_id}")
        if event.collapse:
            lines.append(f"|collapse = {event.collapse}")
        if event.header:
            lines.append(f"|header = {event.header}")
        if event.icon_group:
            lines.append(f"|icon_group = {event.icon_group}")
        if event.icon_type:
            lines.append(f"|icon_type = {event.icon_type}")
        if event.event_name:
            lines.append(f"|event_name = {event.event_name}")
        if event.cond_event_text:
            lines.append(f"|cond_event_text = {event.cond_event_text}")
        if event.event_text:
            lines.append(f"|event_text = {self.format_localization_text(event.event_text)}")
        if event.flavor_text:
            lines.append(f"|flavor_text = {self.format_localization_text(event.flavor_text)}")
        lines.append("|triggered by = FILL IN MANUALLY")
        if event.trigger:
            lines.append(f"|trigger = {self.format_conditions(event.trigger)}")
        if event.immediate:
            lines.append(f"|immediate = {self.format_conditions(event.immediate)}")

        option_texts = []
        lines.append("|options = ")
        for opt in event.options:
            option_texts.append(self.format_option(opt))
        lines.append('\n'.join(option_texts))

        lines.append("}}")

        return '\n'.join(lines)

    def format_option(self, option: Option) -> str:
        """Format an Option object into the {{option}} wiki template.

        Args:
            option: the Option object to format

        Returns:
            wiki text for the option
        """

        lines = ["{{option"]
        lines.append(f"|option_text = {self.format_localization_text(option.option_text)}")
        if option.trigger is not None:
            lines.append(f"|trigger = {self.format_conditions(option.trigger)}")
        if option.default:
            lines.append("|default = yes")
        lines.append(f"|effect = {self.format_conditions(option.effect)}")
        lines.append("}}")

        return '\n'.join(lines)
