import re
import sys
from decimal import Decimal

from common.wiki import WikiTextFormatter
from millennia.game import millenniagame
from millennia.millennia_lib import Resource


class MillenniaWikiTextFormatter(WikiTextFormatter):

    def convert_to_wikitext(self, xml_string: str):
        replacements = {
            r'<sprite name="IconLineBreak">': '\n\n',  # I have no idea why this is an icon
            r'<sprite name="Icon([^"]*)">': r'{{icon|\1}}',  # replace icons with icon tags. Icons which have different names were already replaced
            r'<indent=[0-9]+%> *[*+]?': '*',   # just use the default item list in wiki style
            r'</indent>': '',
            r'<margin=[0-9]+%>': '',   # used similarly as indent, but for a whole section
            r'</margin>': '',
            r'(?m)^ *\*': '*',
            r'</?align[^>]*>': '',  # no real wiki equivalent and probably not a good idea anyway
            r'(?<![>}|] )(?<![>}|])<b>([^<[]*)(</b>|$)(?!])': r"'''\1'''",  # bold with nothing inbetween and which is not preceded by another tag or icon
            r'</?b>': '',   # strip other bolds, because we don't want big bold sections and they are likely to break the wikitext
            r'<i>(.*?)(</i>|$)': r"''\1''",
            r'</?i>': '',   # strip multi-line italics, because mediawiki can't handle that
            r'<size=[0-9]+%>': '',  # we don't want text with different sizes on the wiki
            r'</size>': '',
            r'</?color=?[^>]*>': '',  # no colors either

            # strip links if they are preceded by an icon with the same name
            r'(?i)\{\{icon\|([^}]*)}}\s*\[\[([^]|]*\|)?\'*(\1)\'*]]': r'{{icon|\1}} \3',
        }

        result = xml_string
        for xml_icon, wiki_icon in Resource.icon_overrides.items():
            result = re.sub(f'<sprite name="Icon{xml_icon}">', f'{{{{icon|{wiki_icon}}}}}', result, flags=re.IGNORECASE)
        for res, name in Resource.resource_names.items():
            result = re.sub(f'<sprite name="Icon{res}">', f'{{{{icon|{name.lower()}}}}}', result, flags=re.IGNORECASE)

        result = re.sub(r'LINKSTART\[(?P<linktype>[^]|:]*)[|:](?P<linktarget>[^]]*)](?P<linktext>.*?)LINKEND',
                        self._replace_links, result)
        result = re.sub(r'<link="(?P<linktype>[^"|:]*)[|:](?P<linktarget>[^"]*)">(?P<linktext>.*?)</link>',
                        self._replace_links, result)

        for pattern, replacement in replacements.items():
            result = re.sub(pattern, replacement, result)

        for match in re.findall(r'</?[^>]*>', result):
            if match not in ['<tt>', '</tt>'] and '<GDVAL' not in match:
                print(f'Error: unhandled xml: {match} in {result}', file=sys.stderr)
        return result

    def _replace_links(self, matchobj: re.Match):
        groups = matchobj.groups()
        a = matchobj.groupdict()
        parser = millenniagame.parser
        link_type = matchobj.group('linktype')
        link_target = matchobj.group('linktarget')
        link_text = matchobj.group('linktext')
        match link_type:
            case 'ITT_Misc':
                if link_target in parser.infopedia_topics:
                    target = parser.infopedia_topics[link_target].display_name
                elif link_target.startswith('MENU_'):
                    return link_text  # strip link, because they seem to be used for complex nested tooltips
                elif link_target == 'DLC1':
                    if link_text == '<sprite name="IconDLC1">':
                        return '{{icon|ancient worlds}}'
                    else:
                        target = 'Ancient Worlds'
                        link_text = link_text.replace('DLC1', 'Ancient Worlds')
                elif ('PLAYERACTIONS-' + link_target) in parser.player_actions:
                    return parser.player_actions['PLAYERACTIONS-' + link_target].get_wiki_link_with_icon()
                elif ('UNITACTIONS-' + link_target) in parser.unit_actions:
                    return parser.unit_actions['UNITACTIONS-' + link_target].get_wiki_link_with_icon()
                elif link_target in parser.domain_decks:
                    return parser.domain_decks[link_target].get_wiki_link_with_icon()
                else:
                    print(f'Error: unhandled parameter "{link_target}" for link type: {link_type}', file=sys.stderr)
                    target = link_text
            case 'ALT_CulturePower':
                target = f'Culture#{parser.localize(link_target, "Game-Culture", "DisplayName")}'
            case 'ALT_Unit':
                target = parser.units[link_target].get_wiki_link_with_icon()
            case 'ALT_Building':
                if link_target in parser.buildings:
                    target = parser.buildings[link_target].get_wiki_link_with_icon()
                elif link_target in parser.improvements:
                    target = parser.improvements[link_target].get_wiki_link_with_icon()
                else:
                    target = link_target
            case 'ALT_GoodsInfo':
                if link_target in parser.goods:
                    target = parser.goods[link_target].get_wiki_link_with_icon()
                else:
                    target = link_target
            case 'ALT_Tile':
                target = parser.map_tiles[link_target].get_wiki_link()
            case _:
                print(f'Error: unhandled link type: {link_type}', file=sys.stderr)
                target = link_target
        if target.startswith('[['):  # already a link
            return target
        if target == link_text:
            return f'[[{link_text}]]'
        else:
            return f'[[{target}|{link_text}]]'

    def strip_formatting(self, text):
        """strip HTML formatting and millenia-links"""
        return re.sub(r'LINKSTART\[[^]]*](.*?)LINKEND', r'\1', re.sub(r'<[^<]+?>', '', text))

    def format_cost(self, resource: str, value: int, icon_only=False):
        return self.format_resource(resource, value, cost=True, icon_only=icon_only)

    @staticmethod
    def is_number(s: str):
        try:
            float(s)
            return True
        except ValueError:
            return False

    def format_resource(self, resource: str | Resource, value=None, cost=False, icon_only=False, add_plus=False):
        if not isinstance(resource, Resource):
            resource = Resource(resource)
        if value is None:
            value_str = ''
        elif isinstance(value, str) and not self.is_number(value):
            value_str = f' {value}'
        else:
            positive_is_bad = resource.positive_is_bad
            if cost:
                positive_is_bad = not positive_is_bad
            value_str = f' {self.add_red_green(Decimal(value), positive_is_good=not positive_is_bad, add_plus=add_plus)}'

        icon_str = f'{{{{icon|{resource.icon}}}}}'
        if icon_only:
            name_str = ''
        else:
            name_str = f' {resource.display_name}'
        return f'{icon_str}{value_str}{name_str}'

    def format_resource_without_value(self, resource: str, icon_only=False):
        return self.format_resource(resource, icon_only=icon_only)
