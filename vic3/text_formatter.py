import re
from functools import cached_property

from common.paradox_parser import Tree
from common.wiki import WikiTextFormatter
from vic3.vic3_file_generator import vic3game, Vic3FileGenerator
from vic3.vic3lib import AdvancedEntity


class Vic3WikiTextFormatter(WikiTextFormatter):

    def __init__(self):
        self.parser = vic3game.parser

    def format_localization_text(self, text, concepts_in_same_article: list[str]):
        """

        @param text: the text which should be formatted
        @param concepts_in_same_article: these strings will use a link starting with #
        """
        previous_text = None
        # some concept localizations use other localizations themselves.
        # So we replace till nothing changes anymore (and hope that there is no loop)
        while previous_text != text:
            previous_text = text
            # the next line doesn't really fit here, but it has to be done early,
            # because it matches the [concept] formmating which comes afterwards
            text = text.replace('[Nbsp]', '&nbsp;')
            text = re.sub(
                r"(?<!\[)\[\s*(Concept\s*\(\s*')?(?P<concept_name>[^]']*)('\s*,\s*'(?P<concept_display_string>[^']*)'\s*\))?\s*(?P<formatting>\|[l])?\s*](?!])",
                # r"\[\s*Concept\s*\(\s*'(?P<concept_name>[^]']*)('\s*,\s*'(?P<concept_display_string>[^']*)'\s*\))?\s*(?P<formatting>\|[l])?\s*]",
                self.get_concept_link, text)
            text = self.resolve_nested_localizations(text)
            text = self.apply_localization_formatting(text)
        text = re.sub(r'\[\[([^]|]+)(\|[^]]+)?]]',
                      lambda match: '[[#{}]]'.format(match.group(1) + match.group(2))
                      if match.group(1) in concepts_in_same_article
                      else '[[{}]]'.format(match.group(1) + match.group(2)),
                      text)
        return text

    def _apply_formatting_markers(self, match: re.Match) -> str:
        format_key = match.group(1).lower()
        text = match.group(2)
        replacements = {'p': '{{{{green|{}}}}}',
                        'n': '{{{{red|{}}}}}',
                        'bold': "'''{}'''",
                        'b': "'''{}'''",
                        'italic': "''{}''",
                        'v': '{}'  # white
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
                        }
        if icon_key not in replacements:
            Vic3FileGenerator.warn('unknown icon {} in "{}"'.format(icon_key, match.group(0)))
            return match.group(0)
        else:
            return '{{icon|' + replacements[icon_key] + '}}'

    def _replace_defines(self, match: re.Match) -> str:
        value = self.parser.defines[match.group('category')][match.group('define')]
        prefix = ''
        suffix = ''
        formatting = match.group('formatting')
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
        text = re.sub(r"\[\s*GetDefine\s*\(\s*'(?P<category>[^']*)'\s*,\s*'(?P<define>[^']*)'\s*\)\s*\|\s*(?P<formatting>[-vK0+=%]+)\s*]",
                      self._replace_defines, text)
        text = re.sub(r"\[\s*Get[a-zA-Z_]+\s*\(\s*'(?P<loc_key>[^']+)'\s*\).GetName\s*]",
                      lambda match: self.parser.localize(match.group('loc_key')), text)
        text = re.sub(r"\[\s*GetLawType\s*\(\s*'(?P<law_key>[^']+)'\s*\).GetGroup.GetName\s*]",
                      lambda match: self.parser.laws[match.group('law_key')].group.display_name, text)
        text = re.sub(r"\[\s*GetInterestGroupVariant\s*\(\s*'(?P<ig_key>[^']+)'\s*,\s*GetPlayer\s*\).GetNameWithCountryVariant\s*]",
                      lambda match: self.parser.interest_groups[match.group('ig_key')].display_name, text)
        return text

    def resolve_nested_localizations(self, text: str):
        previous_text = None
        new_text = text
        # some localizations use other localizations themselves.
        # so we replace till nothing changes anymore (and hope that there is no loop)
        while previous_text != new_text:
            previous_text = new_text
            new_text = re.sub(r'\$([^$]*)\$', lambda match: self.parser.localize(match.group(1)), previous_text)

        return new_text

    def get_concept_link(self, match: re.Match) -> str:
        link = self.parser.localize(match.group('concept_name'))
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

    def format_conditions(self, conditions: Tree, indent: int = 1):
        result = []
        for key, value in conditions:
            result.append(self.format_key_value_pair(key, value, indent))
        return self.create_wiki_list(result, indent)

    def format_key_for_compound_statement(self, key):
        key_mappings = {
            'OR': 'At least one of',
            'NOR': 'Neither of the following',
        }
        if key in key_mappings:
            return key_mappings[key]
        else:
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
                if isinstance(value, AdvancedEntity):
                    value = value.get_wiki_link_with_icon()
                return mapping[key][0].format(value=value)
        else:
            return f'{key}: {value}'

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



