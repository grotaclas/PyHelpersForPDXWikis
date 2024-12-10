import re
import sys

from common.wiki import WikiTextFormatter


class AoW4WikiTextFormatter(WikiTextFormatter):

    # only the ones which are different from the xml
    icons = {
        'happiness': 'morale',
        'damageBlight': 'blight damage',
        'damageFire': 'fire damage',
        'damageFrost': 'frost damage',
        'damageLightning': 'lightning damage',
        'damagePhysical': 'physical damage',
        'damageSpirit': 'spirit damage',
        'statuseffectresistance': 'status resistance',
        'defenseblight': 'blight resistance',
        'defensefire': 'fire resistance',
        'defensefrost': 'frost resistance',
        'defenselightning': 'lightning resistance',
        'defensespirit': 'spirit resistance',
        'resistance': 'resistance',
        'structureprod': 'production',
        'unitprod': 'draft',
        'minorcity': 'free city',
        'caststrategic': 'cp world',
        'casttactical': 'cp combat',
        'optactical': 'cp combat',
        'unitBattleMage': 'battle mage unit',
        'unitCelestial': 'celestial unit',
        'unitCivilian': 'civilian unit',
        'unitFighter': 'fighter unit',
        'unitHero': 'hero unit',
        'unitMythic': 'mythic unit',
        'unitNaval': 'naval unit',
        'unitPolearm': 'polearm unit',
        'unitRanged': 'ranged unit',
        'unitRuler': 'ruler unit',
        'unitScout': 'scout unit',
        'unitShield': 'shield unit',
        'unitShock': 'shock unit',
        'unitSiegecraft': 'siegecraft unit',
        'unitSkirmisher': 'skirmisher unit',
        'unitSupport': 'support unit',
        'arcana': 'astral',
        'matter': 'materium',
        'influence': 'imperium',
        'temphp': 'temp hp',
        'garrison': 'fort health',
    }

    def convert_to_wikitext(self, xml_string: str):
        replacements = {
            r'<hyperlink>([^<{]*)</hyperlink>': r'[[\1]]',  # no nested tags
            r'<hyperlink>(.*?)</hyperlink>': r'\1',  # has nested tags which wikilinks cant handle, so we just remove the link
            r'<br></br><br></br>': r'\n\n',
            r'<br></br>': r'\n\n',
            r'<bulletlist></bulletlist>': '',
            r'<bullet></bullet>': '',
            r'<bullet>(.*?)(</bullet>|$)': r'<li>\1</li>',
            r'<bulletlist>(((?!</bulletlist>).)*)$': r'<ul>\1</ul>',
            r'<bulletlist>': '<ul>',
            r'</bulletlist>': '</ul>',
            # not sure what this is doing. Maybe it makes the text blue in the game.
            # use italics in the wiki to not completely lose the marking
            r'<abilityblue>(.*?)</abilityblue>': r"''\1''",

            # assume that the rest are icons
            r'<([^>]*)></\1>': r'{{icon|\1}}',

            # strip links if they are preceded by an icon with the same name
            r'(?i)\{\{icon\|([^}]*)\}\}\s*\[\[(\1)\]\]': r'{{icon|\1}} \2',
        }

        result = xml_string
        # link with identical icon. strip the link. This is done before the icon replacements to operate on the
        # not-replaced values
        # it is repeated for the replaced icons as the last line in the replacements
        result = re.sub(r'(?i)(<([^>]*)></\2>)\s*<hyperlink>(\2)</hyperlink>', r'\1 \3', result)
        for xml_icon, wiki_icon in self.icons.items():
            result = re.sub(f'<{xml_icon}></{xml_icon}>', f'{{{{icon|{wiki_icon}}}}}', result, flags=re.IGNORECASE)

        for pattern, replacement in replacements.items():
            result = re.sub(pattern, replacement, result)

        for match in re.findall(r'</?[^>]*>', result):
            if match not in ['<ul>', '</ul>', '<li>', '</li>']:
                print(f'Error: unhandled xml: {match}', file=sys.stderr)
        return result
