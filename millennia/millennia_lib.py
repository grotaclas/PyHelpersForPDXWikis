import re
from abc import ABC, abstractmethod
from collections.abc import Iterator, Callable
from dataclasses import dataclass
from decimal import Decimal
from functools import cached_property
from itertools import groupby
from pprint import pprint, pformat

from PIL import Image
from common.paradox_lib import AttributeEntity, NameableEntity, IconMixin
from common.paradox_parser import Tree
from millennia.game import millenniagame


def convert_xml_tag_to_python_attribute(s: str):
    """ lowercase the first letter"""
    return s[0].lower() + s[1:]


def unsorted_groupby(iterable, key):
    """
    wrapper around itertools.groupby which works even if values with the same keys are non-consecutive

      iterable
        Elements to divide into groups according to the key function.
      key
        A function for computing the group category for each element.
        If the key function is not specified or is None, the element itself
        is used for grouping.
    """
    return groupby(sorted(iterable, key=key), key=key)


class MillenniaIconMixin(IconMixin):

    def get_wiki_filename(self) -> str:
        filename = f'{self.display_name}.png'
        prefix = self.get_wiki_filename_prefix()
        if not filename.lower().startswith(prefix.lower()):
            filename = f'{prefix} {filename}'
        filename = filename.replace(':', '')
        return filename

    def get_wiki_icon(self, size: str = '24px', link='self') -> str:
        return self.get_wiki_file_tag(size, link)


class Resource(NameableEntity):
    icon: str

    resource_names = {'ResArcana': 'Arcana',
                      'ResArcanaMax': 'Maximum Arcana',
                      'ResChaos': 'Accumulated Chaos',
                      'ResChaosPerTurn': 'Chaos',
                      'ResCityEducation': 'Education',
                      'ResCityExpansionPoints': 'Influence',
                      'ResCityFaith-{PlayerReligion}': 'Faith',
                      'ResCityFaith': 'Faith',
                      'ResCityFood': 'Food',
                      'ResCityHousing': 'Housing',
                      'ResCityIdeology': 'Ideology',
                      'ResCityInformation': 'Information',
                      'ResCityLuxury': 'Luxury',
                      'ResCityPower': 'Power',
                      'ResCityPowerRequired': 'Power Drain',
                      'ResCityProduction': 'Production',
                      'ResCitySanitation': 'Sanitation',
                      'ResCoin': 'Wealth',
                      'ResColonyShipProgress': 'Colony Ship Progress',
                      'ResCulture': 'Culture',
                      'ResDomainArts': 'Arts XP',
                      'ResDomainDiplomacy': 'Diplomacy XP',
                      'ResDomainEngineering': 'Engineering XP',
                      'ResDomainEnigneering': 'Engineering XP',
                      'ResDomainExploration': 'Exploration XP',
                      'ResDomainGovernment': 'Government XP',
                      'ResDomainWarfare': 'Warfare XP',
                      'ResDomainArtsMax': 'Maximum Arts XP',
                      'ResDomainDiplomacyMax': 'Maximum Diplomacy XP',
                      'ResDomainEngineeringMax': 'Maximum Engineering XP',
                      'ResDomainExplorationMax': 'Maximum Exploration XP',
                      'ResDomainGovernmentMax': 'Maximum Government XP',
                      'ResDomainWarfareMax': 'Maximum Warfare XP',
                      'ResImprovementPoints': 'Improvement Points',
                      'ResImprovementPointsMax': 'Maximum Improvement Points',
                      'ResInnovation': 'Accumulated Innovation',
                      'ResInnovationPerTurn': 'Innovation',
                      'ResKnowledge': 'Knowledge',
                      'ResLuxury': 'Luxury',
                      'ResMonumentProgress': 'Monument Progress',
                      'ResSocialFabricWildcard': 'Social Fabric Wildcard',
                      'ResSpecialPowerCharge': 'Archangel Charge',
                      'ResSpecialists': 'Specialists',
                      'ResSpecialistsMax': 'Maximum Specialists',
                      'StatUnrestSuppression': 'Unrest suppression',
                      'StatUnrest': 'Unrest',
                      'ResScrap': 'Scrap',
                      'ResWarheads': 'Warheads',
                      # 'ResTempMonumentProgress': 'Monument Progress'  # is just in the loc files
                      }

    icon_overrides = {
        # no XP in icon
        'ResArcanaMax': 'arcana',
        'ResDomainArts': 'arts',
        'ResDomainArtsMax': 'arts',
        'ResDomainDiplomacy': 'diplomacy',
        'ResDomainDiplomacyMax': 'diplomacy',
        'ResDomainEngineering': 'engineering',
        'ResDomainEnigneering': 'engineering',
        'ResDomainEngineeringMax': 'engineering',
        'ResDomainExploration': 'exploration',
        'ResDomainExplorationMax': 'exploration',
        'ResDomainGovernment': 'government',
        'ResDomainGovernmentMax': 'government',
        'ResDomainWarfare': 'warfare',
        'ResDomainWarfareMax': 'warfare',
        'ResImprovementPoints': 'improvement point',
        'ResImprovementPointsMax': 'improvement point',
        'ResSpecialistsMax': 'specialists',
    }

    positive_is_bad_overrides = [
        'ResChaos',
        'ResChaosPerTurn',
        'ResCityPowerRequired'
    ]

    def __init__(self, name: str):
        super().__init__(name, self.resource_names[name])
        if name in self.icon_overrides:
            self.icon = self.icon_overrides[name]
        else:
            self.icon = self.display_name.lower()

    @cached_property
    def positive_is_bad(self):
        return self.name in self.positive_is_bad_overrides


class ResourceValue:
    value: int
    resource: Resource

    def __init__(self, resource: Resource | None, value: int):
        self.resource = resource
        self.value = value

    @classmethod
    def parse(cls, resource_value: str) -> 'ResourceValue':
        resource, value = resource_value.split(',')
        return cls(Resource(resource), int(value))

    def format(self, icon_only=False):
        if self.resource is None:
            return ''
        return millenniagame.parser.formatter.format_resource(self.resource, self.value, icon_only)

    def __str__(self):
        return self.format()


class Cost(ResourceValue):

    def format(self, icon_only=False):
        return millenniagame.parser.formatter.format_cost(self.resource, self.value, icon_only)

    @classmethod
    def parse(cls, cost: str) -> 'Cost':
        resource, value = cost.split(',')
        return cls(resource, int(value))


class NoCost(Cost):

    def __init__(self):
        super().__init__(None, 0)

    def format(self, icon_only=False):
        return ''


class NamedAttributeEntity(AttributeEntity, MillenniaIconMixin):
    name: str
    display_name: str

    # if no localization was found, this is set to false and the name is used as a display name
    # this attribute serves to distinct entities which have the same name and display name,
    # from entities which have no localization
    has_localized_display_name = True

    _tag_for_name: str = None
    _localization_category: str = None
    _localization_suffix: str = 'DisplayName'

    tag_to_attribute_map = {}

    def __init__(self, attributes: dict[str, any]):
        self.name = attributes['name']
        if 'display_name' not in self.extra_data_functions and 'display_name' not in attributes:
            self.extra_data_functions = self.extra_data_functions.copy()  # copy to not modify the class attribute of the subclass
            self.extra_data_functions['display_name'] = self._get_display_name

        if attributes is not None:
            self.add_attributes(attributes)

    def __str__(self):
        return self.display_name

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        if other is None:
            return False
        if isinstance(other, str):
            return other == self.display_name or other == self.name
        if hasattr(other, 'name'):
            return self.name == other.name
        else:
            return False

    def _get_display_name(self, data):
        display_name = millenniagame.parser.localize(self.name, self._localization_category, self._localization_suffix, return_none_instead_of_default=True)
        if display_name is None:
            display_name = self.name
            self.has_localized_display_name = False
        display_name = millenniagame.parser.formatter.strip_formatting(display_name, strip_newlines=True)
        return display_name

    def get_icon_image(self) -> Image.Image | None:
        """get the icon from the game assets"""
        return millenniagame.parser.unity_reader.get_entity_icon(self.name)


class Storage(ABC):
    def __init__(self, unparsed_entries: list[str]):
        if isinstance(unparsed_entries, str):
            unparsed_entries = [unparsed_entries]

        if unparsed_entries is None:
            self.unparsed_entries = None
        else:
            self.unparsed_entries = self.deduplicate(unparsed_entries)

    def deduplicate(self, unparsed_data):
        unduplicated_dict = {data.partition(',')[0]: data.partition(',')[2] for data in unparsed_data}
        unduplicated_list = [f'{key},{value}' if value != '' else key for key, value in unduplicated_dict.items()]
        return unduplicated_list

    @abstractmethod
    def get(self, tag: str):
        pass

    def has(self, tag: str):
        return self.get(tag) is not None


class Tags(Storage):

    def get(self, tag: str):
        multiple_tags = []
        for entry in self.unparsed_entries:
            if entry == tag:
                return True
            if entry.startswith(f'{tag}:'):
                return entry.partition(':')[2]
            if entry.startswith(f'{tag}-'):
                multiple_tags.append(entry.partition('-')[2])
        if len(multiple_tags) > 0:
            return multiple_tags
        else:
            return None


class Data(Storage):

    def _split_keys_by_minus(self, key, value, attributes):
        if '-' in key:
            main_key, sub_key = key.split('-', 1)
            if main_key not in attributes:
                attributes[main_key] = {}
            self._split_keys_by_minus(sub_key, value, attributes[main_key])
        else:
            attributes[key] = value

    def get(self, tag: str, first_tag_separator='-'):
        """sometimes there is no - between the tag and its first attribute. In that case first_tag_separator can be set to an empty string"""
        if not self.unparsed_entries:
            return None
        attributes = {}
        for entry in self.unparsed_entries:
            if entry == tag:
                return True
            if entry.startswith(f'{tag}:'):
                return entry.partition(':')[2]
            if entry.startswith(f'{tag},'):
                return entry.partition(',')[2]

            if entry.startswith(f'{tag}{first_tag_separator}'):
                entry = f'{tag}-' + entry.removeprefix(f'{tag}{first_tag_separator}')
                key, value = entry.split(',')
                self._split_keys_by_minus(key, value, attributes)
        if attributes:
            return attributes[tag]
        else:
            return None

    def get_as_list(self, prefix: str) -> list[list[str]]:
        """return a list of data entries which match the prefix. Each element in the list is a list.
        The last item in the list is the value (after the comma in the data) and the rest of the items
        are the part before the comma split by '-' and without the prefix"""
        results = []
        for entry in self.unparsed_entries:
            if entry.startswith(prefix):
                key, _seperator, value = entry.removeprefix(prefix).removeprefix('-').partition(',')
                result = key.split('-')
                result.append(value)
                results.append(result)
        return results

    def get_as_value_list(self, tag: str) -> list[str]:
        """return a list of data entries which match the tag followed by a comma"""
        return [entry.partition(',')[2]
                for entry in self.unparsed_entries
                if entry.startswith(f'{tag},')
                ]


class MillenniaEntity(NamedAttributeEntity):
    import_entity: str
    tags: Tags
    startingData: Data

    description: str
    infopedia: str

    tag_to_attribute_map = {'Import': 'import_entity',  # import is a reserved keyword
                            'Tag': 'tags',  # usually the attribute is called Tags, but sometimes it is Tag
                            }

    ignored_attributes = ['MapScale', 'CombatViewerData']

    _tag_for_name = 'ID'
    _localization_category = 'Entity'

    transform_value_functions = {'tags': lambda tags: Tags(
        [] if not tags else
        tags['Tag'] if 'Tag' in tags else []),
                                 'startingData': lambda data: Data(
                                     [] if not data else
                                     data['Data'] if 'Data' in data else [])
                                 }

    extra_data_functions = {'description': lambda data: millenniagame.parser.formatter.strip_formatting_and_effects_from_description(
        millenniagame.parser.localize(data['name'], 'Entity', 'DetailText', default='')),
                            'infopedia': lambda data: millenniagame.parser.localize(data['name'], 'Entity', 'InfopediaText', default='')}

    @cached_property
    def cost(self) -> Cost:
        return self.calculate_cost('ConstructionCost')

    def calculate_cost(self, data_tag: str):
        cost = self.startingData.get(data_tag)
        if cost is None:
            return NoCost()
        if len(cost) > 1:
            raise Exception('More than one cost is not supported')
        res, value = list(cost.items())[0]
        return Cost(res, value)

    @cached_property
    def upgrade_line_tiers(self) -> dict[str, int]:
        upgrade_lines = self.startingData.get_as_list('UpgradeLine')
        return {line[0]: int(line[1]) for line in upgrade_lines}

    @cached_property
    def upgrades(self):
        upgrades = set()
        for line in self.upgrade_line_tiers:
            tier = self.upgrade_line_tiers[line]
            possible_upgrades = [entity for entity in millenniagame.parser.entities.values() if
                                 line in entity.upgrade_line_tiers
                                 and entity.upgrade_line_tiers[line] >= tier + 1
                                 and entity.has_localized_display_name  # assume unlocalized units dont exist
                                 ]

            while possible_upgrades:
                next_tier_upgrades = {upgrade for upgrade in possible_upgrades if upgrade.upgrade_line_tiers[line] == tier + 1}
                if len(next_tier_upgrades) > 0:
                    upgrades.update(next_tier_upgrades)
                    break
                else:
                    tier += 1
                if tier > 20:
                    raise Exception(f'Reached tier 20 without finding upgrades from the same tier in "{self.display_name}"')
        return sorted(upgrades, key=lambda upgrade: upgrade.display_name)

    @cached_property
    def unlocked_by(self):
        # TODO: other ways to unlock
        result = [tech for tech in (
                list(millenniagame.parser.technologies.values()) +
                [age for age in millenniagame.parser.ages.values()] +
                list(millenniagame.parser.domain_technologies.values()) +
                [deck for deck in millenniagame.parser.domain_decks.values()] +
                [card for deck in millenniagame.parser.event_cards.values() for card in deck.values()] +
                [reward for faction in millenniagame.parser.factions.values() for reward in faction.rewards.values()] +
                list(millenniagame.parser.megaproject_stages.values())
        ) if self.name in tech.unlock_names]
        if self.name == 'B_PARTHENON':  # TODO: find a better way to discover or present this information
            result.append(millenniagame.parser.ages['TECHAGE3_HEROES'])
        return sorted(result, key=lambda tech: tech.display_name)

    @cached_property
    def spawned_by(self):
        result = [tech for tech in (list(millenniagame.parser.technologies.values()) + [age for age in millenniagame.parser.ages.values()] + list(
            millenniagame.parser.domain_technologies.values()) + [card for deck in millenniagame.parser.event_cards.values() for card in deck.values()] +
                                    list(millenniagame.parser.unit_actions.values()))
                  if self.name in tech.spawns
                  # filter out things without a display name, because they are either not used or triggered by another effect in which
                  # case that other effect is already listed
                  and tech.has_localized_display_name]
        spawn_powers = [power for power in millenniagame.parser.domain_powers.values() if self.name in power.spawns]
        filtered_powers = list(spawn_powers)
        for power in spawn_powers:
            for linked_power in power.all_linked_powers_recursive:
                if linked_power in filtered_powers:
                    filtered_powers.remove(linked_power)
        result.extend(filtered_powers)

        if self.name == 'B_RELIGION_BIRTHPLACE':  # hardcoded via AReligionInfo.cCreateReligionStartingBuildingEntity
            for power in millenniagame.parser.domain_powers.values():
                if power.effectType == 'CET_ReligionCreate':
                    result.append(power)
        return result

    @cached_property
    def notes(self) -> list[str]:
        return self.get_notes()

    def get_notes(self, ignored_data: list[str] = [], ignored_tags: list[str] = [], ignored_unit_actions: list[str] = [],
                  ignored_data_with_default_values: dict[str, list[str]] = {}) -> list[str]:
        parser = millenniagame.parser
        notes = []
        for entry in self.startingData.get_as_list(''):
            tag = entry.pop(0)
            value = entry.pop()
            if tag in ['DefaultBonusValue',
                       'OutpostImprovementRestrictionTag',  # TODO: this one might be useful
                       'UpkeepCategory', 'ConstructionCost', 'EntityPrefab', 'EntityAudioEvent', 'UpgradeLine', 'ImprovementSort', 'FilterAge',
                       'SourceOverlayImageName', 'SourceOverlayTooltip', 'HelpTopicOnBuild', 'ReligionRenameFormat',
                       'CVAttachment', 'IdleAnim',
                       ] or tag.startswith('Goods') or tag.startswith('Res') or tag.startswith('Workable') or tag.startswith('ConvertGoods') or tag.startswith(
                'AI'):
                continue
            if tag in ignored_data:
                continue
            if tag in ignored_data_with_default_values and value in ignored_data_with_default_values[tag]:
                continue
            else:
                note = self._get_note_from_data(tag, value, entry, ignored_unit_actions)
                if note is None:
                    print(f'Notice: Unhandled data "{tag}" ({entry}) in "{self.name}": {value}')
                    notes.append(f'<pre>{"-".join([tag] + entry)}: {value}</pre>')
                elif note == '':
                    pass
                elif isinstance(note, list):
                    notes.extend(note)
                else:
                    notes.append(note)

        if hasattr(self, 'actionCards') and self.actionCards:
            for card in self.actionCards.find_all('Card'):
                if card not in [
                    'UNITACTIONS-STANDARD_TOWNBUILDINGWORK',  # I think this is just the setup that workers can work on improvements
                    # STANDARD_RESOURCEGENERATOR is only used for capital, homeland and religious birthplace. I'm not sure what it does. Maybe it allows
                    # gathering goods from the tile of the capital, but I have never seen a resource on that tile
                    'UNITACTIONS-STANDARD_RESOURCEGENERATOR',
                ]:
                    notes.append(f'{{{{Card|{card}}}}}')

        # TODO: parse tags (e.g. RequireReligion )
        for tag in self.tags.unparsed_entries:
            if (tag in ['Building', 'CityBuilding', 'CityBuildingConstructed', 'Improvement',
                        'VentureCapitalists', 'SpartansFortifications', 'University', 'TrainingCamp', 'AquaticBuilding', 'SultanBuilding',
                        'MilitaryBasePresent', 'Housing', 'GreatLibrary', 'Palace',
                        'ImprovedByNets',
                        'ReligionNameOverride', 'GovernmentCapital', 'Capital', 'Homeland',
                        'HideInBuildingMenu', 'ItemizeYieldTooltipBuffs',
                        'CanBeSieged', 'HasCityAttack', 'AirliftDestination', 'IgnoreTerrainWorkerCode', 'NeutralAttackTarget',
                        'NoWorkerAssignmentOnCreation',
                        # 'UpkeepCategory', 'ConstructionCost', 'EntityPrefab', 'EntityAudioEvent', 'UpgradeLine', 'ImprovementSort', 'FilterAge',
                        # 'SourceOverlayImageName', 'SourceOverlayTooltip', 'HelpTopicOnBuild', 'ReligionRenameFormat'
                        ] or tag.startswith('AI') or tag.startswith('CapitalAge') or tag.startswith('Tooltip') or tag.startswith('BuildRequirement')
                    or tag.startswith('ImprovementCategory')  # improvement category might be useful to sort them
                    or tag.endswith('TownBonus') or (tag.endswith('Present') and ':' not in tag)
                    or 'sound' in tag.lower()
            ):
                continue
            if tag in ignored_tags:
                continue
            else:
                note = self._get_note_from_tag(tag)
                if note is None:
                    # print(f'Notice: Unhandled tag "{tag}" in "{self.display_name}"')
                    # notes.append(f'<pre>{tag}</pre>')
                    pass
                elif note == '':
                    pass
                elif isinstance(note, list):
                    notes.extend(note)
                else:
                    notes.append(note)
        return notes

    def get_notes_for_card_play(self, card, target='self', when: str = None):
        if target == 'self':
            target = f'on this {self.get_class_name_as_wiki_page_title().lower()}'
        return CardBaseClass.get_notes_for_card_play(card, target, when)

    def _get_note_from_data(self, tag, value, entry, ignored_unit_actions):
        """subclasses can override this to handle other data. return None in case it is not handled and an empty string to ignore the data"""
        parser = millenniagame.parser
        formatter = parser.formatter
        if tag in parser.misc_game_data:
            return f'{parser.misc_game_data[tag]}: {value}'
        elif f'{tag}-{value}' in parser.misc_game_data:
            return parser.misc_game_data[f'{tag}-{value}']
        elif tag.startswith('Stat'):
            # stats with other localizations are already handled via misc_game_data above
            # we cant use append "-".join(entry) in general, because it would pull a bunch of wrong localizations
            if f'{tag}-{"-".join(entry)}' in parser.misc_game_data:
                localisation = parser.misc_game_data[f'{tag}-{"-".join(entry)}']
            else:
                localisations = {
                    'StatDeployedProsperity': 'Vassal prosperity per turn when deployed',
                    'StatOrgDamageFactor': 'Morale damage factor',
                    'StatUnrestGenerationInEnemyTerritory': 'Unrest generation in enemy territory',
                }
                if tag in localisations:
                    localisation = localisations[tag]
                elif tag == 'StatDeployedVassalIntegration':
                    return ''  # seems to be unused. Instead StatVassalIntegration seems to be the vassal integration per turn when deployed
                else:
                    return None
            return f'{localisation}: {value}'
        elif tag == 'NeedAdjust':
            return f'{parser.needs[entry[0]]}: {value}'
        elif tag == 'CountLimit':
            return f'Limit {value} per {entry[0]}'
        elif tag == 'RequiredRegionLevel':
            return f'Required region level: {value}'
        elif tag in ['CityAction', 'UseAction']:
            if value != 'NONE' and value not in ignored_unit_actions:
                if tag == 'UseAction':
                    return f'Enables action: {parser.unit_actions[value].get_wiki_link_with_icon()}'
                else:
                    return f'Enables action: {parser.tile_actions[value].get_wiki_link_with_icon()}'
            else:
                return ''
        elif tag == 'CityAttackStrength':
            return f'Capital attack strength: {value}'
        elif tag == 'CityBuildingDefenders':
            return f'Provides defensive unit: {parser.units[value]}'
        elif tag == 'ObsoleteAge':
            return f'Obsolete in age: {value}'
        elif tag == 'PopulationCost':
            return '{{icon|population}} Population cost: ' + value
        elif tag == 'CombatMod':
            value = f'{Decimal(value):%}'
            modifier_loc = formatter.localize_combat_mod(entry)
            if modifier_loc:
                return f'{modifier_loc}: {value}'
            else:
                return None
        elif tag == 'TriggerOnSelfBuild':
            return self.get_notes_for_card_play(value)
        elif tag == 'TriggerOnUnitBuilt':
            return self.get_notes_for_card_play(value, target='on the new unit', when='When a new unit is built in this region')
        elif tag == 'TriggerOnTurnStart':
            return self.get_notes_for_card_play(value, target='on this', when='At the start of each turn')
        elif tag == 'TriggerOnSelfKilled':
            if value in ['UNITACTIONS-SETTLER_KILLED', 'UNITACTIONS-ENVOY_KILLED', 'UNITACTIONS-ENGINEER_KILLED', 'UNITACTIONS-MERCHANT_KILLED',
                         'UNITACTIONS-UTILITYSHIP_KILLED', 'UNITACTIONS-MEGAWAREHOUSE_KILLED', 'HORDE-KHAN_DEATH',
                         'TECHAGE10_VICTORYARCHANGEL-WEAPONSLAB_ONSELFKILLEDTRIGGER', 'TECHAGE10_VICTORYARCHANGEL-RADIATIONLAB_ONSELFKILLEDTRIGGER',
                         'TECHAGE10_VICTORYARCHANGEL-LASERSATELLITE_ONSELFKILLEDTRIGGER', 'UNITACTIONS-OCEANSETTLER_KILLED']:
                # these just undo buffs or reduce the spawning cost again
                return ''
            if value == 'UNITACTIONS-MOTHERSHIP_KILLED':
                return f'When killed: Spawn {parser.map_tiles["MT_MOTHERSHIPWRECKAGE"].get_wiki_link_with_icon()} on the tile'
        else:
            return None

    def _get_note_from_tag(self, tag):
        """subclasses can override this to handle other tag. return None in case it is not handled and an empty string to ignore the tag"""
        parser = millenniagame.parser
        formatter = parser.formatter
        if tag == 'RequireReligion':
            return 'Requires [[religion]]'
        elif tag.startswith('RequiredBuildingTag:'):
            building_tag = tag.removeprefix('RequiredBuildingTag:')
            return f'Requires {formatter.join_with_comma_and_or([building.get_wiki_link() for building in parser.buildings.values() if building.tags.has(building_tag)])}'
        elif tag.startswith('RequiredImprovementTag:'):
            improvement_tag = tag.removeprefix('RequiredImprovementTag:')
            return f'Requires {formatter.join_with_comma_and_or([improvement.get_wiki_link() for improvement in parser.improvements.values() if improvement.tags.has(improvement_tag)])}'
        elif tag == 'RelocateOnPlayerOwnerChange':
            return 'Relocate when owner changes'
        elif tag.startswith('DataLinkAction:'):
            action = tag.split(',')[1]
            return f'{{{{DataLinkAction|{action}}}}}'
        elif tag == 'HasAlignmentDecay':
            if self.startingData.has('StatAlignmentDecayValue'):
                return ''
            else:
                return 'In Age of the Singularity:\n** AI Alignment Decay: -2'
        elif tag in ['LaserShield']:
            return f'<pre>{tag}</pre>'
        elif tag.startswith('TypeDLC'):
            dlc_name = tag.removeprefix('Type')
            dlc = parser.dlcs[dlc_name]
            return f'Needs {dlc.get_wiki_icon()}'
        else:
            # can be used for testing new tags
            # loc = parser.localize(tag, 'Game-Tag', return_none_instead_of_default=True)
            # if loc is not None:
            #     cards = parser.get_cards_which_use_tag(tag)
            #     if cards:
            #         return f'{tag}: {loc}; used in {", ".join(card.get_wiki_link_with_icon() + ";".join(payloads) for card, payloads in cards)}'
            return None


class ProductionChain:
    source_goods: 'Goods'
    source_amount: int
    result_goods: 'Goods'
    result_amount: int

    def __init__(self, source_goods, source_amount, result_goods, result_amount):
        self.source_goods = source_goods
        self.source_amount = source_amount
        self.result_goods = result_goods
        self.result_amount = result_amount

    @classmethod
    def parse(cls, data: list) -> 'ProductionChain':
        source_goods, source_amount, result_goods, result_amount = data
        source_goods = millenniagame.parser.goods[source_goods]
        source_amount = int(source_amount)
        result_goods = millenniagame.parser.goods[result_goods]
        result_amount = int(result_amount)
        return cls(source_goods, source_amount, result_goods, result_amount)

    def format(self):
        return f'{self.source_goods.get_wiki_icon()} {self.source_amount} {self.source_goods} → {self.result_goods.get_wiki_icon()} {self.result_amount} {self.result_goods}'


class BuildingBaseClass(MillenniaEntity):
    @cached_property
    def non_work_production(self):
        return self._get_production_texts(include_workable=False)

    def _get_production_texts(self, include_non_workable=True, include_workable=True):
        production = []
        production_data_list = []
        if include_workable:
            for data_entry in self.startingData.get_as_list('Workable'):
                if data_entry[0].startswith('GoodsSpecial') or data_entry[0].startswith('Res'):
                    production_data_list.append(data_entry)
        if include_non_workable:
            for data_entry in self.startingData.get_as_list(''):
                if data_entry[0].startswith('GoodsSpecial') or data_entry[0].startswith('Res'):
                    production_data_list.append(data_entry)
        for workable_data in production_data_list:
            type_name = workable_data.pop(0)
            value = workable_data.pop()
            if type_name == 'GoodsSpecial':
                _tile_production, gathering_type = workable_data
                assert _tile_production == 'TileProduction'
                loc = millenniagame.parser.localize(gathering_type, 'Goods-Special-TileProduction', 'DisplayName')
                gather_goods = [f'{tile.display_name}: {gather.amount} {gather.goods.display_name}' for tile in
                                list(millenniagame.parser.terrains.values()) + list(millenniagame.parser.map_tiles.values()) for gather in tile.gathers
                                if gather.name == gathering_type and tile.has_localized_display_name]
                gather_goods = list(dict.fromkeys(gather_goods))  # remove duplicates
                if len(gather_goods) > 0:
                    text = f'{{{{hover box|{loc}|{", ".join(gather_goods)}}}}}'
                else:
                    text = loc
                if int(value) != 1:
                    text = f'{value}× {text}'
                production.append(text)
            elif type_name.startswith('Res'):
                production.append(millenniagame.parser.formatter.format_resource(type_name, value))
            else:
                raise Exception(f'unknown production data: {type_name}, {workable_data}, {value}')
        for chain in self.get_production_chains(include_non_workable, include_workable):
            production.append(chain.format())
        for goods, value in self.get_goods_productions(include_non_workable, include_workable).items():
            production.append(f'{goods.get_wiki_icon()} {value} {goods}')

        return production

    def get_production_chains(self, include_non_workable=True, include_workable=True) -> list[ProductionChain]:
        prefixes = []
        if include_workable:
            prefixes.append('WorkableConvertGoods')
        if include_non_workable:
            prefixes.append('ConvertGoods')
        result = []
        for prefix in prefixes:
            for data in self.startingData.get_as_list(prefix):
                result.append(ProductionChain.parse(data))
        return result

    def get_goods_productions(self, include_non_workable=True, include_workable=True) -> dict['Goods', int]:
        prefixes = []
        if include_workable:
            prefixes.append('WorkableGoods')
        if include_non_workable:
            prefixes.append('Goods')
        productions = {}
        for prefix in prefixes:
            starting_data = [a for a in self.startingData.get_as_list(prefix) if a[0] != 'Special']
            for goods, value in starting_data:
                productions[millenniagame.parser.goods[goods]] = value
        return productions


class Building(BuildingBaseClass):
    pass

    def get_wiki_page_name(self) -> str:
        return 'Buildings'


class CityProject(MillenniaEntity):
    portrait: str

    def get_icon_image(self) -> Image.Image | None:
        """get the icon from the game assets"""
        return millenniagame.parser.unity_reader.get_entity_portrait(self.portrait)

    def get_wiki_page_name(self) -> str:
        return 'Buildings'

    @cached_property
    def effect(self) -> str:
        for resource, value in self.startingData.get_as_list('Generate'):
            if resource.endswith('Cost'):
                cost = millenniagame.parser.formatter.format_resource('ResCityProduction', value, cost=True)
            else:
                income = millenniagame.parser.formatter.format_resource(resource, value)
        return f'{income} per {cost}'


class Improvement(BuildingBaseClass):

    @cached_property
    def is_outpost_improvement(self):
        return self.tags.has('OutpostImprovement')

    @cached_property
    def is_outpost_specialization(self):
        return self.tags.has('OutpostCore')

    @cached_property
    def terrains(self) -> list['Terrain']:
        terrains = []
        terrain_requirement = self.tags.get('BuildRequirementTerrain')
        if terrain_requirement is not None:
            for terrain_name in terrain_requirement:
                terrains.append(millenniagame.parser.terrains[terrain_name])
        return terrains

    @cached_property
    def build_requirements(self):
        requirements = []
        locations = list(millenniagame.parser.terrains.values())
        locations.extend(millenniagame.parser.map_tiles.values())

        tag_requirements = self.tags.get('BuildRequirementTag')
        if tag_requirements is not None:
            for tag_requirement in tag_requirements:
                if tag_requirement in ['OpenTerrain', 'CultivatedPlantationGood']:
                    requirements.append(f'{{{{#lst:Improvements|{tag_requirement}}}}}')
                else:
                    for location in locations:
                        if location.tags.has(tag_requirement.removeprefix('+')):
                            requirements.append(location)
            # requirements.extend(tag_requirements)

        requirements.extend(self.terrains)

        tile_requirement = self.tags.get('BuildRequirementTile')
        if tile_requirement is not None:
            for tile_name in tile_requirement:
                requirements.append(millenniagame.parser.map_tiles[tile_name])

        adjacent_requirement = self.tags.get('BuildRequirementMovementTypeAdjacent')
        if adjacent_requirement is not None:
            for tile_name in adjacent_requirement:
                if tile_name == 'MT_Land':
                    tile_name = 'walkable land'
                requirements.append(f'Adjacent to {tile_name}')

        adjacent_requirement = self.tags.get('BuildRequirementAdjacentTag')
        if adjacent_requirement is not None:
            for tile_name in adjacent_requirement:
                if tile_name == 'LandmarkNatural':
                    tile_name = 'landmark'
                requirements.append(f'Adjacent to {tile_name}')
        return requirements

    @cached_property
    def category(self) -> str|None:
        categories = self.tags.get('ImprovementCategory')
        if categories is None:
            return None
        elif len(categories) > 1:
            raise Exception(f'Too many improvement categories for {self.name}')
        else:
            return categories[0]

    @cached_property
    def work_production(self):
        return self._get_production_texts(include_non_workable=False)

    def get_wiki_page_name(self) -> str:
        if self.is_outpost_improvement or self.is_outpost_specialization:
            return 'Region'
        else:
            return 'Improvements'

    def _get_note_from_tag(self, tag):
        parser = millenniagame.parser
        if tag in ['AetherImprovement', 'Computers', 'Docks', 'EducationBuilding', 'Factory', 'Farms', 'Modernization', 'OutpostCore', 'Pyramids', 'ReligiousBuilding', 'Scribes', 'TradePost', 'Trash', 'WeaponSmith']:
            return parser.localize(tag, 'Game-Tag').removesuffix('s')
        fixed_texts = {
            'Furnace': 'Furnace type',
            'StandardOutpostImprovement': 'Standard outpost improvement',
            'CastleOutpostImprovement': 'Castle outpost improvement',
            'ColonyOutpostImprovement': 'Colony outpost improvement',
        }
        if tag in fixed_texts:
            return fixed_texts[tag]
        return super()._get_note_from_tag(tag)


class TileOverlay(Improvement):
    pass


class MapTile(MillenniaEntity):
    revealHiddenData: Data = Data([])

    def __init__(self, attributes: dict[str, any]):
        self.extra_data_functions = self.extra_data_functions.copy()  # copy to not modify the class attribute of the superclass
        self.transform_value_functions['revealHiddenData'] = lambda data: Data([] if not data else data['Data'] if 'Data' in data else [])
        super().__init__(attributes)

    def get_wiki_filename_prefix(self) -> str:
        return 'Goods'

    def get_wiki_filename(self) -> str:
        if self.tags.has('CityOfGoldTile'):
            goods_name = self.startingData.get_as_list('GoodsProduction')[0][1]
            goods = millenniagame.parser.goods[goods_name]
            return f'Goods {goods}.png'
        elif not self.tags.has('BonusTile'):
            return ''
        else:
            return super().get_wiki_filename()

    def get_icon_image(self) -> Image.Image | None:
        """get the icon from the game assets"""
        if self.tags.has('ResourceIcon'):
            return millenniagame.parser.unity_reader.get_image_resource(f'ui/icons/Goods{self.tags.get("ResourceIcon")}-icon')
        else:
            return None

    def get_wiki_page_name(self) -> str:
        page_map = {'MT_CITYCENTER': 'Region',
                    'MT_NEUTRAL_TOWN': 'Minor Nation',
                    'MT_ROGUEAIFACTORY': 'Age 10',
                    }
        if self.name in page_map:
            return page_map[self.name]
        elif self.tags.has('BonusTile'):
            return 'Tiles'
        else:
            return 'Landmarks'

    @cached_property
    def gathers(self) -> list['Gather']:
        return [Gather(name, millenniagame.parser.localize(name, 'Goods-Special-TileProduction', 'DisplayName'), millenniagame.parser.goods[goods], amount) for
                name, goods, amount in self.startingData.get_as_list('GoodsProduction') + self.revealHiddenData.get_as_list('GoodsProduction')]


class UnitType:
    tag: str
    display_name: str
    wiki_page: str

    def __init__(self, tag: str, display_name: str, wiki_page: str):
        self.tag = tag
        self.display_name = display_name
        self.wiki_page = wiki_page


unit_types = {
    'NonCombatant': UnitType('NonCombatant', 'Non-Combatants', 'Civilian'),
    'Barbarian': UnitType('Barbarian', 'Barbarian units', 'Barbarians'),
    'NavalTarget': UnitType('NavalTarget', 'Naval units', 'Navy'),
    'AirUnit': UnitType('AirUnit', 'Air units', 'Airforce'),
    'Militia': UnitType('Militia', 'Militia units', 'Army'),
    'TypeDefenses': UnitType('TypeDefenses', 'Defenses', 'Army'),
    'Megafauna': UnitType('Megafauna', 'Megafauna', 'Barbarians'),
    'Unit': UnitType('Unit', 'Land units', 'Army'),  # there is no tag for land units, so we assume that all remaining units are land units
    'TILEHARVEST': UnitType('TILEHARVEST', 'Harvesting units', 'Civilian'),  # special handling
    'SETTLER': UnitType('SETTLER', 'Settlers', 'Civilian'),  # special handling
}


class Unit(MillenniaEntity):
    unit_icon: str  # it seems to be only used in the outliner
    portrait: str  # the icon which is used in most places

    upkeep: Cost
    command: int
    health: int
    movement: int
    attack: int
    defense: int
    targetPriority: int
    revealRadius: int
    unrestSuppression: int

    tag_to_attribute_map = {'Import': 'import_entity',  # import is a reserved keyword
                            'Tag': 'tags',  # usually the attribute is called Tags, but sometimes it is Tag
                            'Icon': 'unit_icon',
                            }

    def __init__(self, attributes: dict[str, any]):
        super().__init__(attributes)
        for stat in ['StatHealth', 'StatCommand', 'StatMovement', 'StatAttack', 'StatDefense', 'StatTargetPriority', 'StatUnrestSuppression', 'RevealRadius']:
            value = self.startingData.get(f"{stat}")
            if value is not None:
                value = int(value)
            self.__setattr__(convert_xml_tag_to_python_attribute(stat.removeprefix('Stat')), value)
        self.upkeep = self.calculate_cost('Upkeep')

    @cached_property
    def primary_type(self) -> UnitType:
        if self.startingData.has('UseAction-100,UNITACTIONS-TILEHARVEST_BEGIN'):
            return unit_types['TILEHARVEST']
        elif self.startingData.has('UseAction-100,UNITACTIONS-OCEANSETTLER_BUILDOCEANCITY') or self.startingData.has(
                'UseAction-100,UNITACTIONS-SETTLER_BUILDCITY'):
            return unit_types['SETTLER']
        else:
            return unit_types[self.get_first_matching_tag(list(unit_types.keys()))]

    def get_first_matching_tag(self, tags: list[str]):
        for tag in tags:
            if self.tags.has(tag):
                return tag
        return ''

    def get_icon_image(self) -> Image.Image | None:
        """get the icon from the game assets"""
        return millenniagame.parser.unity_reader.get_entity_portrait(self.portrait)

    @cached_property
    def notes(self) -> list[str]:
        return self.get_notes([
            'StatCommand', 'StatCommandMax', 'StatHealth', 'StatHealthMax', 'StatMovement', 'StatMovementMax',
            'StatAttack', 'StatDefense', 'StatTargetPriority', 'StatUnrestSuppression', 'RevealRadius', 'Upkeep',
            'UnitMemberPrefab', 'UnitMemberPrefabLocked',
        ],
            ignored_unit_actions=['UNITACTIONS-STANDARD_MARKNOTIDLE', 'UNITACTIONS-STANDARD_GUARDTOGGLE', 'UNITACTIONS-STANDARD_ATTEMPTMULTITURNMOVE',
                                  'UNITACTIONS-STANDARD_RAZE', 'UNITACTIONS-STANDARD_TRANSPORTLOAD', 'UNITACTIONS-STANDARD_AIRLIFT',
                                  'UNITACTIONS-STANDARD_KILLSELF'],
            ignored_tags=['CheckIdle', 'ProvideVisibility', 'TrainableUnit', 'Combatant', 'Unit', 'WaterMovement', 'NavalTarget', 'NonCombatant',
                          'ShipTest', 'DiscoveryNaval', 'DefenderTrackStatusFromCombatResult',
                          'TypeProjectile',  # seems to have no effect. maybe it is for the combat viewer
                          ],
            ignored_data_with_default_values={'StatOrgDamageFactor': ['1', '1.0'],
                                              # 'StatUnrestGenerationInEnemyTerritory': ['1'],
                                              'RazeValueMultiplier': ['1', '1.0'],
                                              'StatCombatXPMax': ['40'],  # currently no unit has a different value, but city defenders dont have the value
                                              })

    def _get_note_from_data(self, tag, value, entry: list[str], ignored_unit_actions):
        parser = millenniagame.parser
        formatter = parser.formatter
        if tag == 'LeaderPromotionType':
            return f'{parser.misc_game_data[tag]}: {parser.units[value]}'
        if tag == 'UpgradeResource':
            return f'Upgrading costs {formatter.format_resource_without_value(value)}'
        if tag == 'UpkeepRemovePriority':
            return f'This unit gets disbanded with high priority({value}) if its upkeep can\'t be paid'
        if tag == 'LeaderRetireValue':
            return f'[[Leader retire value]]: {value}'
        if tag == 'DeployedGoods':
            goods = parser.goods[entry[0]]
            return f'Production when deployed: {goods.get_wiki_icon()} {{{{green|{value}}}}} {goods.display_name}'
        if tag == 'TileHarvestTag':
            where, harvest_tag = value.split('-')
            tiles = [tile.get_wiki_link_with_icon() for tile in parser.get_entities_by_tag(harvest_tag, parser.map_tiles)]
            return f'Can harvest {" and ".join(tiles)}'
        if tag == 'TileHarvestProductionCode':
            production_type = parser.localize(value, 'Goods-Special-TileProduction', 'DisplayName')
            return f'Harvests via {production_type}'
        if tag == 'TriggerOnLocalImprovementBuilt':
            card = parser.all_cards[value]
            return f'Execute {card.get_wiki_link_with_icon()} when an improvement on this tile is constructed'


        return super()._get_note_from_data(tag, value, entry, ignored_unit_actions)

    def _get_note_from_tag(self, tag):
        parser = millenniagame.parser
        formatter = parser.formatter

        if tag.startswith('Type') or tag in [
            'ShallowWater', 'AirUnit', 'Barbarian', 'Scout', 'Cultist', 'Daimyo',  # unit types which don't start with type
            'AirBomber', 'Automata', 'CombatTower', 'CombatWall', 'EarlySea', 'Explorer', 'Knight', 'Leader', 'Mercenary', 'Militia', 'Raider', 'Steampunk',
            'WaterTransport', 'CreateImportRoute', 'PreGunpowder',
            'DestroyAtEndOfCombat'
            # 'RogueAI',  already displayed from the data 'NeutralSubtype,5' which has the same localization
        ]:
            if tag.startswith('TypeDLC'):
                return super()._get_note_from_tag(tag)
            else:
                return parser.localize(tag, 'Game-Tag').removesuffix('s')

        fixed_texts = {
            'CombatTargetingLowestHealth': 'Targets enemy with lowest health',
            'EnterPeacefulTerritory': 'Can move into foreign territory without a treaty',
            'GameDataKillAtZero-ActionCharges': 'Disbands after using up action charges',
            'JaguarBuff': f'Can be promoted to {parser.units["UNIT_JAGUAR"].get_wiki_link_with_icon()} when having {parser.domain_technologies["WARRIORPRIESTS-JAGUAR"].get_wiki_link_with_icon()}',
            'NeutralCampSpawnPlacer': 'Spawns barbarian camps',
            'CombatTargetingRandom': 'Chooses targets randomly during combat',
        }
        if tag in fixed_texts:
            return fixed_texts[tag]
        for ignored_prefix in ['GameDataTooltip', 'CombatType', 'CombatAttackType', 'TagAIBehavior', 'TagAILimitType', 'TagAIIgnoreLimitType', 'WeightUnitBy']:
            if tag.startswith(ignored_prefix):
                return ''
        attack_round_tags = {'ActInNavalBombardRound': 'naval bombard round', 'ActInNavalDefenseRound': 'naval defense round',
                             'ActInAirCombatRounds': 'air combat rounds', 'ActInBombingRound': 'air bombing round'}
        defense_round_tags = {'AirDefenseTarget': 'air defense round', 'AirToAirTarget': 'air fighters round',
                              'AirInterceptionTarget': 'air interception round',
                              # 'NavalTarget': 'naval defense round'  # seems to be unused, because there are no attackers in that round
                              }
        if tag in attack_round_tags:
            return f'Only attacks in the {attack_round_tags[tag]} during a battle'
        if tag == 'ActInAirDefenseRound':
            return 'Also attacks in the air defense round during a battle'
        if tag == 'AirTargetingOnly':
            return 'Can not be attacked in the naval bombards or default rounds of a battle'
        if tag == 'CanAttackNavalTargets':
            return 'Can attack naval targets'
        return super()._get_note_from_tag(tag)

    def get_wiki_page_name(self) -> str:
        return self.primary_type.wiki_page

    @cached_property
    def actions(self) -> list['UnitAction']:
        return [millenniagame.parser.unit_actions[action_name] for number, action_name in self.startingData.get_as_list('UseAction') if action_name != 'NONE' and action_name != 'UNITACTIONS-BOMBER_STRATEGICBOMBING_TOGGLE']


class TownSpecialization(MillenniaEntity):

    def get_wiki_filename(self) -> str:
        return ''

    def get_wiki_page_name(self) -> str:
        return 'Region'


class InfopediaTopicType(NamedAttributeEntity):
    _localization_category = 'Info-TopicType'
    _localization_suffix = None


class InfopediaTopic(NamedAttributeEntity):
    topicType: InfopediaTopicType
    text: str
    techLock: str = None
    achievementLock: str = None

    # TODO: write generic handling for this
    transform_value_functions = {'topicType': lambda type_str: millenniagame.parser.infopedia_topic_types[type_str]}

    _tag_for_name = 'TopicID'
    _localization_category = 'Info-Topic'
    _localization_suffix = 'Title'

    @cached_property
    def text(self):
        """
        the formatted wikitext for this topic

        don't call this function while creating entities, because the formatting might need them(e.g. to create links)
        """
        return millenniagame.parser.formatter.convert_to_wikitext(millenniagame.parser.localize(self.name, 'Info-Topic', 'MainText'))


@dataclass
class Unlock:
    unlocked_entity: NamedAttributeEntity | str
    custom_effect_text: str = None
    conditions: str = None
    target: str = None
    type: str = None

    @cached_property
    def entity_name(self):
        if hasattr(self.unlocked_entity, 'name'):
            return self.unlocked_entity.name
        else:
            return str(self.unlocked_entity)

    def get_effect_text(self, prefix='Unlocks '):
        if self.custom_effect_text is not None:
            return self.custom_effect_text
        else:
            type_text = f'{self.type} ' if self.type else ''
            if not prefix and type_text.startswith('the '):
                # "the culture power X" looks ugly in lists which only mention the name, but it is needed if the text says "Unlocks the culture power X"
                type_text = type_text.removeprefix('the ')
            target_text = f' for {self.target}' if self.target else ''
            conditions_text = f' if {self.conditions}' if self.conditions else ''
            if hasattr(self.unlocked_entity, 'get_wiki_link_with_icon'):
                name = self.unlocked_entity.get_wiki_link_with_icon()
            else:
                name = str(self.unlocked_entity)
            return f'{prefix}{type_text}{name}{target_text}{conditions_text}'

    def add_condition(self, condition):
        if isinstance(condition, list) and len(condition) == 1:
            condition = condition[0]
        if self.conditions is None:
            self.conditions = condition
        else:
            self.conditions += condition

class CardBaseClass(NamedAttributeEntity):
    tags: Tags = Tags([])
    choices: Tree
    description: str
    deck_name: str
    deck: 'Deck' = None
    executionType: str
    subtype: str
    prereqs: Tree = None
    duration: int = None

    _tag_for_name = 'ID'
    _localization_category = None
    _localization_suffix = 'CardTitle'

    tag_to_attribute_map = {'CardTags': 'tags'}
    transform_value_functions = {'tags': lambda card_tags: Tags(
        [] if not card_tags else
        card_tags['Tags']['Tag'] if 'Tags' in card_tags and card_tags['Tags'] and 'Tag' in card_tags['Tags'] else
        card_tags['Tag'] if 'Tag' in card_tags else [])}

    extra_data_functions = {'description': lambda data: millenniagame.parser.formatter.strip_formatting(
        millenniagame.parser.localize(data['name'], localization_suffix='CardText', default=''))}

    def get_wiki_page_name(self) -> str:
        page = super().get_wiki_page_name()
        if page == 'Card base class':
            page = 'List of events'
        return page

    def get_wiki_filename(self) -> str:
        file = super().get_wiki_filename()
        if file.startswith('Card base class'):
            return ''
        else:
            return file

    @cached_property
    def choice_localisations(self):
        result = []
        for choice_number, choice in enumerate(self.choices.find_all('ACardChoice')):
            loc_key = f'{self.name}-Choice-{choice.get_or_default("ChoiceID", str(choice_number))}'
            result.append(millenniagame.parser.localize(loc_key, return_none_instead_of_default=True))
        return result

    @cached_property
    def unlock_names(self) -> list[str]:
        return [unlock.entity_name for unlock in self.unlocks]

    @cached_property
    def unlocks(self):
        unlocks = []
        self.get_effects(collected_unlocks=unlocks)
        return unlocks

    def get_unlock_list(self, prefix='Unlocks ') -> list[str]:
        return [unlock.get_effect_text(prefix) for unlock in self.unlocks]

    def traverse_effects(self, effect_type: str, get_data_from_effect: Callable[[Tree], str | None]):
        """go through all the effects recursively
        call get_data_from_effect for effects which match effect_type
        return a list of the return values of get_data_from_effect. Return values which are None are skipped"""
        result = []
        if not self.choices:
            return []
        for effects in self.choices.find_all_recursively('ACardEffect'):
            if not isinstance(effects, list):
                effects = [effects]
            for effect in effects:
                if 'EffectType' not in effect:
                    continue
                if effect['EffectType'] == effect_type:
                    data = get_data_from_effect(effect)
                    if data is not None:
                        result.append(data)
                elif effect['EffectType'] == 'CE_PlayCard':
                    if effect['Payload'] in millenniagame.parser.all_cards and effect['Payload'] != self.name:  # avoid effects which call themselves
                        result.extend(millenniagame.parser.all_cards[effect['Payload']].traverse_effects(effect_type, get_data_from_effect))
        return result

    @cached_property
    def spawns(self) -> list[str]:
        return (self.traverse_effects('CE_SpawnEntity', lambda effect: effect['Payload'].split(',')[1]) +
                self.traverse_effects('CE_UpgradeUnit', lambda effect: effect['Payload']))

    @staticmethod
    def _get_entity_by_name(name):
        if name.startswith('DomainSpecialization,'):
            return millenniagame.parser.domain_decks[name.removeprefix('DomainSpecialization,')]
        else:
            return millenniagame.parser.all_entities[name]

    @cached_property
    def other_effects(self) -> list[str]:
        return self.get_effects(include_unlocks=False)

    def get_effects(self, include_unlocks=False, recursive=False, group_by_choice=False, collected_unlocks: list[Unlock]=None):
        if collected_unlocks is None:
            collected_unlocks = []
        results = {}
        if not self.choices:
            return results
        for i, choice in enumerate(self.choices.find_all('ACardChoice')):
            new_unlocks = []
            effects = self.get_effects_for_choice(choice, include_unlocks, new_unlocks)
            # if include_unlocks:
            #     effects = [unlock.get_effect_text() for unlock in unlocks] + effects
            # if collected_unlocks is None:
            #     unlocks = []
            # effects = self.get_effect_text_for_choice(choice, include_unlocks, recursive)
            if self.duration is not None:
                if effects:
                    effects = [f'Apply the following effects for {self.duration} turns:', effects]
                for unlock in new_unlocks:
                    unlock.add_condition(f'(for {self.duration} turns)')
            if not self.choice_requirements_apply_to_card:
                requirement_trees = list(choice.find_all_recursively('ACardRequirement'))
                if len(requirement_trees) > 0:
                    requirements = self.get_requirement_texts(requirement_trees)
                    for unlock in new_unlocks:
                        for requirement in requirements:
                            unlock.add_condition(requirement)
                    if len(requirements) == 1:
                        match = re.match(r'^At least (.*) \(This requirement is used as the cost\)$', requirements[0])
                        if match:
                            effects = [f'Pay {match.group(1)}<ref name=is_cost>This effect is not selectable if the cost can\'t be paid</ref>'] + effects
                        else:
                            effects = [f'If {requirements[0]}:', effects]
                    else:
                        effects = ['If:', requirements, 'then:', effects]

            results[i] = effects
            collected_unlocks.extend(new_unlocks)
        if group_by_choice:
            return results
        else:
            return [effect for effects in results.values() for effect in effects]

    @cached_property
    def choice_requirements_apply_to_card(self):
        choices = list(self.choices.find_all('ACardChoice'))
        if len(choices) == 1:
            return True
        else:
            return False

    def get_effects_for_choice(self, choice: Tree, include_unlocks: bool, collected_unlocks: list[Unlock]):
        results = []
        prev_effect_trigger_text = None
        effects_for_current_trigger = None
        played_cards = {}
        for effects in choice.find_all_recursively('ACardEffect'):
            if not isinstance(effects, list):
                effects = [effects]
            for effect in effects:
                payload = effect.get('Payload')
                target = effect.get('Target')
                effect_type = effect.get('EffectType')
                payload_param = effect.get('PayloadParam')
                trigger = effect.get('Trigger')
                trigger_param = effect.get('TriggerParam')
                if effect_type == 'CE_PlayCard' and target and (target.startswith('ENTTAG,') or target.startswith('ENTTYPE,')):
                    card_target = target.split(',')[1].removeprefix('+')
                    if card_target == 'B_HOMELAND':
                        card_target = 'Homeland'  # in some cases the trigger is set for the tag Homeland instead of the building
                    played_cards[payload] = card_target
                elif effect_type == 'CE_SetStringData' and payload.startswith('TriggerOnEntityCreate'):
                    create_target = payload.split('-')[1].removeprefix('+')
                    if create_target == 'B_HOMELAND':
                        create_target = 'Homeland'  # in some cases the trigger is set for the tag Homeland instead of the building
                    create_card = payload.split(',')[1]
                    if create_card in played_cards and played_cards[create_card] == create_target:
                        # this just applies the same card if the same type of entity gets created later
                        continue

                new_unlocks = []
                effect_text = self.get_effect_text(effect_type, payload, payload_param, target, effect, include_unlocks, new_unlocks)
                assert not isinstance(effect_text, Unlock)
                for unlock in new_unlocks:
                    if trigger:
                        unlock.add_condition(self._get_trigger_text(trigger, trigger_param))
                    collected_unlocks.append(unlock)

                if effect_text is None:
                    print(f'Unhandled effect type {effect_type} with payload "{payload}"')
                    results.append(pformat(effect.dictionary))
                elif effect_text == '':
                    pass  # empty effects are ignored
                else:
                    if trigger:
                        trigger_text = self._get_trigger_text(trigger, trigger_param)
                        if trigger_text == prev_effect_trigger_text:
                            effects_for_current_trigger.append(effect_text)
                            continue
                        if not isinstance(effect_text, list):
                            effect_text = [effect_text]
                        effects_for_current_trigger = effect_text
                        prev_effect_trigger_text = trigger_text
                        effect_text = [f'{trigger_text}:', effect_text]
                    else:
                        effects_for_current_trigger = None
                        prev_effect_trigger_text = None
                    if isinstance(effect_text, list):
                        results.extend(effect_text)
                    else:
                        results.append(effect_text)

        return results

    def _get_trigger_text(self, trigger, trigger_param):
        if not trigger:
            return None
        if trigger == 'CT_ExpeditionResult' and trigger_param == 'SUCCESS':
            trigger_text = 'If the expedition was successful'
        elif trigger == 'CT_ExpeditionResult' and trigger_param == 'FAILURE':
            trigger_text = f'If the expedition failed'
        elif trigger == 'CT_Random':
            chance = trigger_param.split(',')[0]
            trigger_text = f'{chance}% chance for'
        else:
            trigger_text = f'Unknown trigger {trigger} with param {trigger_param}'
        return trigger_text

    @cached_property
    def all_effects(self):
        """unlocks and other effects together"""
        return self.get_effects(include_unlocks=True, recursive=True)

    def format_effect_target(self, target: str, capitalize=False, ignore_default_targets=False):
        parser = millenniagame.parser

        if target.startswith('ENTTYPE,') and target.removeprefix('ENTTYPE,') in parser.all_entities:
            entity = parser.all_entities[target.removeprefix('ENTTYPE,')]
            target_text = entity.get_wiki_link_with_icon()
        elif target.startswith('ENTTAG,'):
            tag = target.removeprefix('ENTTAG,')
            target_text = parser.formatter.format_tag(tag)
            if target_text == '':
                target_text = f'<tt>{target}</tt>'
        elif target.startswith('LOC,TILERADIUS,'):
            radius = target.removeprefix('LOC,TILERADIUS,')
            target_text = f'tiles within a radius of {radius}'
        elif target == 'LOC,EXECLOC':
            target_text = 'this location'
        elif target == 'LOC,EXPEDITION':
            target_text = 'this expedition'
        elif target == 'ENT,REQTARGET':
            target_text = 'remembered entity'
        elif target.startswith('ENT,FINDTAGLOCRAD'):
            _, _, tag, location, radius = target.split(',')
            if location == 'EXECLOC':
                location = 'this location'
            elif location == 'STARTINGLOC':
                location = 'the starting location'
            elif location == 'EXTERNALTARGET':
                location = 'the selected target'
            if radius == '0':
                radius = 'at'
            elif radius == '1':
                radius = 'next to'
            else:
                radius = f'within {radius} tiles of'
            target_text = f'{parser.formatter.format_tag(tag)} {radius} {location}'
        elif target == 'REGION':
            target_text = 'region'
        elif target == 'PLAYER,ALLPLAYERS':
            target_text = 'all players'
        elif target.startswith('PLAYER,ALLPLAYERSBYDIPLOMATICRELATIONSHIP:'):
            target_type = target.removeprefix('PLAYER,ALLPLAYERSBYDIPLOMATICRELATIONSHIP:')
            if target_type.startswith('!'):
                target_bool = 'FALSE'
                target_type = target_type.removeprefix('!')
            else:
                target_bool = 'TRUE'
            target_text = f'all {parser.localize(target_type + "," + target_bool, "UI-Req").lower()} players'
        elif target.startswith('PLAYER,ALLPLAYERSBYGAMEDATA:'):
            target_text = f'players which have the game data <tt>{target.removeprefix("PLAYER,ALLPLAYERSBYGAMEDATA:")}</tt>'
        elif target.startswith('PLAYER,LOCOWNER'):
            target_text = f'the owner of this location'
        elif target == 'PLAYER':
            if ignore_default_targets:
                return ''
            else:
                target_text = 'player'
        else:
            target_text = f'<tt>{target}</tt>'

        if target_text.startswith('<tt>'):
            return target_text
        else:
            if capitalize and not target_text.startswith('['):
                target_text = target_text.capitalize()
            if target_text.lower() == target.lower():
                comment = ''
            else:
                comment = f'<!-- {target} -->'
            return f'{target_text}{comment}'

    def _handle_unlock_effect(self, unlock: Unlock, include_unlocks: bool, collected_unlocks: list[Unlock] | None):
        if collected_unlocks is not None:
            collected_unlocks.append(unlock)
        if include_unlocks:
            return unlock.get_effect_text()
        else:
            return ''

    def get_effect_text(self, effect_type: str, payload: str, payload_param: str | None, target: str, effect: Tree, include_unlocks=True, collected_unlocks: list[Unlock]=None):
        parser = millenniagame.parser
        match effect_type:
            case 'CE_None':
                return ''
            case 'CE_AdjustGameData':
                name, operation, value = payload.split(',')
                if payload_param and payload_param.startswith('BuffDecay'):
                    decay_text = f'(decays by {payload_param.split(":")[1]} per turn)'
                else:
                    decay_text = ''
                if name.startswith('Workable'):
                    name_attribute = 'Work: '
                    name = name.removeprefix('Workable')
                else:
                    name_attribute = ''

                if name.startswith('Res'):
                    # for simple increase/reduce we can use format_resource to get a concise formatting with icon, red/green and plus/minus
                    # but if the value is a variable like #REWARD_XPGAIN_VALUE, it would not work so well. TODO: improve the formatting for variables
                    if operation in ['ADD', 'SUB'] and parser.formatter.is_number(value):
                        if Decimal(value) == 0:
                            return ''
                        if operation == 'SUB':
                            value = f'-{value}'
                        return self._prefix_target(target, f'{name_attribute}{parser.formatter.format_resource(name, value, add_plus=True)}{decay_text}')
                    else:
                        name = parser.formatter.format_resource_without_value(name)
                elif name.startswith('TerrainExpansionCostFactor-'):
                    terrain = parser.terrains[name.removeprefix('TerrainExpansionCostFactor-')]
                    name = f'[[TerrainExpansionCostFactor]] for {terrain.get_wiki_link_with_icon()}'
                elif name.startswith('ConsumeGoodBonus-'):
                    tag, goods_name, *resource_name = name.split('-')
                    resource_name = '-'.join(resource_name)  # faith has an extra -
                    goods = parser.goods[goods_name]
                    res = parser.formatter.format_resource_without_value(resource_name)
                    name = f'Bonus {res} from {goods.get_wiki_link_with_icon()}'
                elif name.startswith('CulturePowerUnlock-'):
                    power_name = name.removeprefix('CulturePowerUnlock-')
                    if power_name not in parser.domain_powers:
                        print(f'Ignoring unlock for non-existing power {power_name}')
                        return ''
                    power = parser.domain_powers[power_name]
                    if int(value) == 1 and operation in ['ADD', 'SET']:
                        if power.is_culture_power():
                            return self._handle_unlock_effect(Unlock(power, type='the {{icon|culture}} power', target=self.format_effect_target(target, ignore_default_targets=True)), include_unlocks, collected_unlocks)
                        else:
                            return self._handle_unlock_effect(Unlock(power, type=f'the {power.get_domain_icon()} power', target=self.format_effect_target(target, ignore_default_targets=True)), include_unlocks, collected_unlocks)
                    elif (int(value) == 0 and operation == 'SET') or (int(value) == 1 and operation == 'SUB'):
                        return self._prefix_target(target, f'Disables the culture power {power.get_wiki_link_with_icon()}')
                elif name == 'DiplomacyLocked' and operation in ['ADD', 'SET'] and value == '1':
                    return self._prefix_target(target, 'Disable diplomacy')
                elif name == 'AirUnitsUnlocked' and operation == 'SET' and value == '1':
                    return ''  # It is just used to keep track if air units are available to the player(e.g. to show air unit capacity in tooltips)
                elif name.removeprefix('#') in parser.misc_game_data:
                    name = parser.misc_game_data[name.removeprefix('#')]
                    if operation == 'SET' and value == '1':
                        if name.lower().startswith('unlocks'):
                            return self._handle_unlock_effect(Unlock(re.sub(r'^[Uu]nlocks?\s*:?', r'', name)), include_unlocks, collected_unlocks)
                        else:
                            return self._prefix_target(target, name)
                elif name == 'TileExpeditionChance-{CurrentPlayer}':
                    name = 'success chance'
                    value = f'{Decimal(value):%}'
                elif name.startswith('CombatMod-'):
                    value = f'{Decimal(value):%}'
                    name = parser.formatter.localize_combat_mod(name.split('-')[1:])
                elif name == 'DataVersion':
                    return ''  # seems to be used to track save game versions
                else:
                    name = f'<tt>{name}</tt>'
                if value.removeprefix('#') in parser.misc_game_data:
                    value = parser.misc_game_data[value.removeprefix('#')]
                elif value.startswith('SPECIALVAL'):
                    _, val_type, radius, tag, valuekey = value.split(':')
                    if val_type in ['ENTITYTAGRADIUS', 'TERRAINTAGRADIUS', 'TILETAGRADIUS']:
                        effects_with_value = []
                        for entity_value, entities in unsorted_groupby([entity for entity in parser.get_entities_by_tag(tag) if entity.startingData.get(valuekey)], key=lambda entity: entity.startingData.get(valuekey)):
                            effects_with_value.append(f'{entity_value} for each {"/".join([entity.get_wiki_link_with_icon() for entity in entities])} within {radius} tiles')
                        value = ', '.join(effects_with_value)
                match operation:
                    case 'ADD':
                        effect_text = f'Increase {name_attribute}{name} by {value}{decay_text}'
                    case 'SUB':
                        effect_text = f'Reduce {name_attribute}{name} by {value}{decay_text}'
                    case 'MUL':
                        effect_text = f'Multiply {name_attribute}{name} by {value}{decay_text}'
                    case 'DIV':
                        effect_text = f'Divide {name_attribute}{name} by {value}{decay_text}'
                    case 'SET':
                        effect_text = f'Set {name_attribute}{name} to {value}{decay_text}'
                    case _:
                        effect_text = f'{operation} {name_attribute}{name} by {value}{decay_text}'
                return self._prefix_target(target, effect_text)
            case 'CE_SpawnEntity':
                entity_type, entity_name = payload.split(',')
                target_name = target.removeprefix('LOC,ENTTYPELOC,')
                match target_name:
                    case 'B_CAPITAL':
                        location = ' in a capital'
                    case 'B_HOMELAND':
                        location = ' in the homeland'
                    case _:
                        if target_name in parser.all_entities:
                            location = f' on a {parser.all_entities[target_name]}'
                        else:
                            location = f' on {self.format_effect_target(target_name)}'
                if 'TargetLimit' in effect:
                    count = f' {effect["TargetLimit"]}'
                else:
                    count = ''
                if entity_name in parser.all_entities:
                    entity_string = parser.all_entities[entity_name].get_wiki_link_with_icon()
                else:
                    entity_string = entity_name
                if payload_param:
                    parameters = f' with parameters <tt>{payload_param}</tt>'
                else:
                    parameters = ''
                if 'ExtraTargetParam' in effect:
                    parameters += f' and <tt>{effect["ExtraTargetParam"]}</tt>'
                return f'Spawns{count} {entity_string}{location}{parameters}'
            case 'CE_UpgradeUnit':
                entity_name = payload
                if target == 'ENT,EXEC':
                    old_entity = 'this unit'
                elif target.startswith('ENTTAGATLOC,'):
                    old_entity = target.split(',')[1]
                else:
                    return None  # unhandled

                if 'TargetLimit' in effect:
                    count = f' {effect["TargetLimit"]}'
                else:
                    count = ''
                if entity_name in parser.all_entities:
                    entity_string = parser.all_entities[entity_name].get_wiki_link_with_icon()
                else:
                    entity_string = entity_name
                return f'Upgrades{count} {old_entity} to {entity_string}'
            case 'CE_AddCard':
                pass
            case 'CE_AddCardsByTag':
                source_deck, tag = payload.split(',')
                if source_deck in list(parser.domain_decks.keys()) + list(parser.ages.keys()) and tag in ['+AddToBarbarianDeck',
                                                                                                          '+AddToChaosDeck',
                                                                                                          '+AddToExploreDeck',
                                                                                                          '+AddToInnovationDeck',
                                                                                                          '+UniversalAddToBarbarianDeck',
                                                                                                          '+UniversalAddToChaosDeck',
                                                                                                          '+UniversalAddToExploreDeck',
                                                                                                          '+UniversalAddToInnovationDeck']:
                    return ''  # this is kind of a default effect
                else:
                    return f'Add cards with the tag {tag.removeprefix("+")} from the deck {source_deck} to the deck {target}'
            case 'CE_DebugLog':
                pass
            case 'CE_DestroyEntity':
                if payload_param:
                    params = f' with the parameters <tt>{payload_param}</tt>'
                else:
                    params = ''
                return f'Destroy entity {target}{params}'
            case 'CE_DestroyRegion':
                pass
            case 'CE_PlayCard':
                if 'HELP_TURN' in payload:
                    return ''
                else:
                    if target is None:
                        target_text = ''
                    else:
                        target_text = f' on {self.format_effect_target(target)}'
                    when = None
                    if payload_param and payload_param.startswith('TurnDelay'):
                        delay = payload_param.removeprefix('TurnDelay:')
                        when = f'After {delay} turns'

                    # get notes first even if they are not used so that unlocks get collected
                    play_notes = CardBaseClass.get_notes_for_card_play(payload, target_text, when, include_unlocks, collected_unlocks, target, parent_effect=self)
                    if payload in parser.played_cards_from_tech:
                        return f'{{{{Card|{payload}}}}}'
                    else:
                        return play_notes
            case 'CE_DrawAndPlay':
                pass
            case 'CE_SetStringData':
                string, value = payload.split(',')
                match string:
                    case 'TransportEntityType':
                        return f'Set water transport type to {parser.units[value].get_wiki_link_with_icon()}'
                    case 'TransportLoadTerrainType':
                        return f'Allow transports to move through: {{{{#lst:Research|{value.removeprefix("+")}}}}}'
                    case 'CurrentAge':
                        return ''  # only used in start effects of ages where it is obvious
                    case 'LeaderPromotionType':
                        if value == 'DELETE':
                            return 'Disables promotion to leader'
                        else:
                            return f'{parser.misc_game_data[string]}: {parser.units[value]}'
                    case _:
                        formatted_string = f'<tt>{string}</tt>'
                        if value in millenniagame.parser.all_entities:
                            value_text = millenniagame.parser.all_entities[value].get_wiki_link_with_icon()
                        elif string.startswith('AgeSunset-'):
                            return ''  # sunset effects are not executed at that moment and instead happen when the age ends
                        elif string.startswith('PrefabAppend:'):
                            return ''  # changes map graphics
                        elif string.startswith('ProjectStage-'):
                            return ''  # sets stages and attempts in stages
                        elif string.startswith('BuildHelperHintTag-') or string.startswith('BuildHelperHintType-'):
                            return ''  # used for categories in the build helper
                        elif string.startswith('ActiveMegaproject'):
                            return f'Activate the {parser.megaprojects[value].get_wiki_link()}'
                        else:
                            value_text = f'<tt>{value}</tt>'

                        if string in parser.misc_game_data:
                            formatted_string = parser.misc_game_data[string]
                            if formatted_string.startswith('replaces'):
                                return f'{formatted_string.capitalize()} by {value_text}'
                        return f'Set {formatted_string} to {value_text}'
                pass
            case 'CE_Tooltip':
                if not isinstance(payload, str):
                    # @TODO: remove this workaround for broken tooltip in TECHAGE7_VICTORYHARMONY-StateReligionOffice-Tooltip
                    #  that tooltip has two Payload elements instead of one Payload and one PayloadParam element
                    payload = payload[0]
                if payload.endswith('LineBreak'):
                    return ''
                tooltip = parser.formatter.strip_formatting(parser.localize(payload, default=''))
                if payload_param and payload_param.startswith('FormatParam:'):
                    tooltip_parameter = payload_param.removeprefix('FormatParam:')
                    tooltip = tooltip.replace('{0}', tooltip_parameter)

                if tooltip:
                    return f'Tooltip: {parser.formatter.quote(tooltip.strip())}'
                else:
                    return ''
            case 'CE_PlaySound':
                return ''
            case 'CE_RevealTiles':
                if target == 'ENTTAG,ALLPLAYERS-LandmarkQuest':
                    target_text = 'all quests'
                elif target == 'ENTTAG,ALLPLAYERS-LandmarkNatural':
                    target_text = 'all landmarks'
                else:
                    target_text = self.format_effect_target(target)
                return f'Reveal all tiles within a radius of {payload} from {target_text}'
            case 'CE_PlayFX':
                return ''
            case 'CE_GatherResources':
                pass
            case 'CE_CreateTile':
                tile = parser.map_tiles[payload]
                if payload_param:
                    params = f' with the parameters <tt>{payload_param}</tt>'
                else:
                    params = ''
                return self._prefix_target(target, f'Create {tile.get_wiki_link_with_icon()}{params}')
            case 'CE_Special':
                match payload.split(','):
                    case ['REMOVEBLACKMAP']:
                        return parser.localize('Card-RemoveBlackmap-Tooltip')
                    case ['ACTIONCOMPLETE']:
                        return parser.localize('Card-Action-Complete')
                    case ['ADOPTRELIGION', 'NONE']:
                        return self._prefix_target(target, 'Remove state religion')
                    case ['APPLYFACTIONREWARDS']:
                        return ''  # the rewards are specified and described elsewhere
                    case ['BORDEREXPAND', value]:
                        return self._prefix_target(target, f'Gain {ResourceValue.parse("ResCityExpansionPoints," + value)}')
                    case ['CHECKINTEGRATION', 'SUCCESS']:
                        return self._prefix_target(target, parser.formatter.convert_to_wikitext(parser.localize('Game-Misc-VassalizeMinor')))
                    case ['EXPEDITIONCOMPLETE'] if target == 'LOC,EXPEDITION':
                        return f'Complete expedition'
                    case ['EXPEDITIONRESET'] if target == 'ENT,EXEC':
                        return f'Reset expedition'
                    case ['EXPEDITIONRESOLVE'] if target == 'ENT,EXEC':
                        return f'Determine if the expedition was successful'
                    case [
                            'REFRESHECON'  # recalculates economy data
                         ] | [
                            'CHECKDEFCONALERT', _  # shows or hides an alert
                         ] | [
                            'RELEASESUPPRESSEDHELPALERTS'
                         ]:
                        return ''
            case 'CE_UnlockContent':
                return self._handle_unlock_effect(Unlock(self._get_entity_by_name(payload)), include_unlocks, collected_unlocks)
            case 'CE_ResearchTech':
                if payload.endswith('-BASE'):  # new age
                    age = parser.ages[payload.removesuffix('-BASE')]
                    return f'Advance to the {age.get_wiki_link_with_icon()}'
            case 'CE_ChooseAge':
                # happens  in the age startup, so we don't need an icon or link
                return self._prefix_target(target, f'Change age to {parser.formatter.quote(parser.ages[payload.removesuffix("-BASE")])}')
            case 'CE_RevealHiddenTile':
                if payload == 'MT_COPPER':
                    return ''  # doesnt exist anymore
                return f'Reveal hidden good {parser.map_tiles[payload].get_wiki_link_with_icon()}'
                pass
            case 'CE_RebuildVisuals':
                return ''
            case 'CE_BorderVision':
                return ''  # this just recalculates the border vision after it was changed
            case 'CE_AssignSpecialization':
                return f'Change government to {parser.domain_decks[payload].get_wiki_link_with_icon()}'
            case 'CE_RemoveSpecialization':
                return ''  # removes the current government. Only used before applying a new one, so we don't need to show it
            case 'CE_RefillCultureMeter':
                pass
            case 'CE_ShowDialog':
                return ''
            case 'CE_AdjustPopulation':
                if 'TargetLimit' in effect:
                    limit = f' {effect["TargetLimit"]}'
                else:
                    limit = ''
                return f'Add {payload} population to{limit} {target}'
                pass
            case 'CE_PlayerMessage':
                pass
            case 'CE_DiplomaticRelationship':
                if payload.startswith('PLAYERS_ALL,'):
                    target_loc = 'all players'
                    relationship = payload.partition(',')[2]
                else:
                    relationship, _, second_payload_parameter = payload.partition(',')
                    assert second_payload_parameter == '{CurrentPlayer}', f'unexpected payload parameter {second_payload_parameter}'
                    target_loc = self.format_effect_target(target)
                relationship_loc = parser.localize(relationship, 'Game-Misc-DiplomaticRelationship').lower()
                if '\n' in relationship_loc:
                    # strip formatting and additional descriptions in other lines
                    relationship_loc = parser.formatter.strip_formatting(relationship_loc.split('\n')[0])
                return f'Change diplomatic relationship with {target_loc} to {relationship_loc}'
            case 'CE_MovementTypeOverride':
                terrain, _land = payload.split(',')
                return f'Allow movement through {parser.terrains[terrain].get_wiki_link_with_icon()}'
            case 'CE_RecalculateMoveCosts':
                return ''  # this just recalculates the movement cost after it was changed
            case 'CE_AddHelpTopic':
                return ''
                pass
            case 'CE_InvokePower':
                pass
            case 'CE_RemoveBuffs':
                pass
            case 'CE_SpawnLandmark':
                if payload.count(',') == 2:
                    category, min_radius, max_radius = payload.split(',')
                elif ',' not in payload:
                    category = payload
                    min_radius = max_radius = 0
                category_locs = {
                    'QuestZero': 'Quest 0',
                    'QuestOne': 'Quest I',
                    'QuestTwo': 'Quest II',
                    'CityOfGold': 'City of Gold',
                }
                if category in category_locs:
                    category = category_locs[category]
                else:
                    category = f'<tt>{category}</tt>'
                param, spawn_count = payload_param.split(',')[0].split(':')
                assert param == 'SpawnCount'
                if target == 'PLAYER,ALLPLAYERS':
                    target = 'For each player: '
                else:
                    target = self._prefix_target(target, '')
                return f'{target}Spawn up to {spawn_count} {category} landmark(s) between {min_radius} and {max_radius} tiles of a city or outpost'
            case 'CE_ClearAlert':
                pass
            case 'CE_CreateAlert':
                return ''  # just shows an alert
            case 'CE_DataAlert':
                return ''  # counter to show crisis charges in the UI
            case 'CE_UnitDeploy':
                pass
            case 'CE_MessageDialog':
                return ''
            case 'CE_ProxyTechInfo':
                return ''
            case 'CE_PlayerTreaty':
                pass
            case 'CE_AdjustReligion':
                return self._prefix_target(target, f'Increase religion by {payload}')
            case 'CE_FakeConvertUnits':
                pass
            case 'CE_ChangeTerrain':
                terrain = parser.terrains[payload]
                return self._prefix_target(target, f'Change to {terrain.get_wiki_link_with_icon()}')
            case 'CE_ApplyDamage':
                if payload_param == 'CanKillUnits:false':
                    note = ' (the unit is not killed)'
                else:
                    note = ''
                return self._prefix_target(target, f'Apply {payload} damage{note}')
            case 'CE_RebuildLighting':
                return ''  # graphical effects
            case 'CE_UnlockEntityInfopedia':
                return ''  # just adds it to the infopedia
            case 'CE_UnlockInfopedia':
                return ''  # just adds it to the infopedia
            case 'CE_BulkPlayerUpdate':
                return ''  # used to temporary halt updating player data and resume it later

    @cached_property
    def requirements(self) -> list[str]:
        return self.get_requirements()

    def get_requirements(self, ignored_tag_requirements: list[str] = None) -> list[str]:
        result = []
        if self.choice_requirements_apply_to_card and 'ACardChoice' in self.choices:
            result.extend(self.get_requirement_texts(self.choices.find_all_recursively('ACardRequirement'), ignored_tag_requirements))
        if self.prereqs:
            result.extend(self.get_requirement_texts(self.prereqs.find_all_recursively('Requirement'), ignored_tag_requirements))

        if hasattr(self, 'is_age_advance') and self.is_age_advance:
            # add section tags for transclusion to the special age requirements(but not for the generic number-of-techs requirement(TechRequirement)
            result = [f'<section begin=requirements_{self.advance_to_age.display_name.lower().replace(" ", "_")} />{req}<section end=requirements_{self.advance_to_age.display_name.lower().replace(" ", "_")} />' for req in result]
        if self.tags.has('TechRequirement'):
            reqs = self.tags.get('TechRequirement').split(',')
            if reqs[0] == 'SpecialRequirement-CountTechsWithReq':
                age = millenniagame.parser.ages[reqs[1].removesuffix('-BASE')]
                count = reqs[2]
                result.append(f'At least {count} {age} technologies')
        if self.tags.has('RequiresDLC'):
            for dlc_tag in self.tags.get('RequiresDLC'):
                dlc = millenniagame.parser.dlcs[dlc_tag]
                result.append(f'DLC {dlc.get_wiki_link_with_icon()} is active')
        return result

    def get_requirement_texts(self, requirements: Iterator[Tree], ignored_tag_requirements: list[str] = None):
        results = []
        for requirement in requirements:
            if requirement is None:  # empty Requirement block
                continue
            req = requirement.get('Req')
            if req is None:
                print(f'Requirement section in {self.name} can\'t be parsed:')
                pprint(requirement.dictionary)
                continue
            target = requirement.get('Target')
            req_type = requirement.get('ReqType')
            add_to_entity_buffer = requirement.get_or_default('AddToEntityBuffer', False)
            req_text = self.get_requirement_text(req_type, req, target, requirement, ignored_tag_requirements)
            if req_text is None:
                print(f'Unhandled req type {req_type} with req "{req}"')
                pprint(requirement.dictionary)
                results.append(pformat(requirement.dictionary))
            elif req_text == '':
                pass  # get_requirement_text passes an empty string for reqs which should be ignored
            else:
                if add_to_entity_buffer:
                    req_text += '(this entity is remembered for the effects)'
                results.append(req_text)
        return results

    def _prefix_target(self, target: str, text, any_target=False):
        if target is None or not any_target and target in ['PLAYER',
                                                           'ENT,EXEC',  # I think this is the entity for which the effect gets executed
                                                           None,
                                                           ]:
            return text
        target_text = self.format_effect_target(target, capitalize=not any_target)
        if any_target:
            target_text = f'Any {target_text}'
        return f'{target_text}: {text}'

    def get_requirement_text(self, req_type: str, req: str, target: str, requirement: Tree, ignored_tag_requirements: list[str] = None) -> str | None:
        parser = millenniagame.parser
        match req_type:
            case 'CR_EntityTagCount' | 'CR_EntityTypeCount' | 'CR_GameData' | 'CR_GameDataAny' | 'CR_GameDataTotal':
                if req_type == 'CR_GameDataAny':
                    any_target = True
                else:
                    any_target = False
                name, operation, value = req.split(',')
                # TODO: unify approach of 'what' handling between effects and requirements
                if req_type == 'CR_EntityTagCount':
                    what = parser.formatter.convert_to_wikitext(parser.localize(name, 'Game-Tag', default=f'<tt>{name}</tt>'))
                elif req_type.startswith('CR_GameData') and name.removeprefix('#') in parser.misc_game_data:
                    what = parser.misc_game_data[name.removeprefix('#')]
                elif name in parser.all_entities:
                    what = parser.all_entities[name].get_wiki_link_with_icon()
                elif name.startswith('Res'):
                    what = parser.formatter.format_resource_without_value(name)
                elif name.startswith('IsAgeSetter') and operation == 'EQ':
                    age = parser.ages[name.removeprefix('IsAgeSetter-')]
                    if int(value) == 0:
                        neg = " ''not''"
                    else:
                        neg = ''
                    return f'the {self.format_effect_target(target)} was{neg} the first to enter the {age.get_wiki_link_with_icon()}'
                elif name == '#STARTBONUS_DELAYEDUNIT' and operation == 'EQ':
                    return 'the appropriate starting bonus has been selected'
                else:
                    what = f'<tt>{name}</tt>'
                if 'IsCost' in requirement and requirement['IsCost'].upper() == 'TRUE':
                    cost_message = f' (This requirement is used as the cost)'
                else:
                    cost_message = ''
                if req_type == 'CR_GameData' and value.removeprefix('#') in parser.misc_game_data:
                    value = parser.misc_game_data[value.removeprefix('#')]
                if operation == 'BOOL_TRUE':
                    return self._prefix_target(target, f'{what} is true{cost_message}')
                if operation == 'BOOL_FALSE':
                    return self._prefix_target(target, f'{what} is false{cost_message}')
                if operation == 'NEQ':
                    return self._prefix_target(target, f"Does ''not'' have {value} {what}{cost_message}", any_target)
                operation = {'EQ': '',
                             'GT': 'More than ',
                             'GTE': 'At least ',
                             'LT': 'Less than ',
                             'LTE': 'At most '}[operation]
                return self._prefix_target(target, f'{operation}{value} {what}{cost_message}', any_target)
            case 'CR_Worker':
                pass
            case 'CR_Location':
                if target == 'LOC,EXECLOC':
                    target_loc = f'this location'
                elif target == 'LOC,EXTERNALTARGET':
                    target_loc = 'selected location'
                else:
                    target_loc = f'<tt>{target}</tt>'
                match req.split(','):
                    case ['TERRAINTAG', tag]:
                        if tag == '[PLAYER:TransportLoadTerrainType]':
                            return f'Terrain at {target_loc} is a type through which which water transports can move'
                        else:
                            return f'Terrain at {target_loc} is one of the following: {", ".join(t.get_wiki_link_with_icon() for t in parser.get_terrains_by_tag(tag))}'
                    case ['TERRAINTAGADJACENT', tag]:
                        return f'Terrain adjacent to {target_loc} is one of the following: {", ".join(t.get_wiki_link_with_icon() for t in parser.get_terrains_by_tag(tag))}'
                    case ['RIVER', 'TRUE']:
                        return f'A river is next to {target_loc}'
                    case ['HASSTACKSPACE', 'TRUE', _player]:
                        return f'Army at {target_loc} is not full'
                    case ['ISVASSAL', 'TRUE']:
                        return f'{target_loc} is a vassal'
                    case ['ISVASSAL', 'FALSE']:
                        return f'{target_loc} is ''not'' a vassal'
                    case ['REGIONTYPE', 'OUTPOST', 'TRUE']:
                        return f'{target_loc} is an outpost'
                    case ['REGIONTYPE', 'OUTPOST', 'FALSE']:
                        return f"{target_loc} is ''not'' an outpost"
                    case ['SUBREGION', 'TRUE']:
                        return f'{target_loc} is a vassal ''or'' outpost'
                    case ['SUBREGION', 'FALSE']:
                        return f"{target_loc} is ''not'' a vassal ''nor'' an outpost"
                    case ['TERRITORY', tag]:
                        return f'{target_loc} is {parser.localize(tag, "UI-Req")}'
                    case ['TILE', 'EMPTY_OR_HIDDEN']:
                        return f'{target_loc} is empty or has a hidden good'
                    case ['TILEDIST', 'LTE', distance]:
                        return f'Distance to {target_loc} is at most {distance}'
                    case ['BORDERDIST', 'GTE', distance]:
                        return f'Distance between {target_loc} and a nations border is at least {distance}'
                pass
            case 'CR_Entity':
                pass
            case 'CR_DomainSpec':
                if req.startswith('GOV'):
                    return self._prefix_target(target, f'Government is {parser.governments[req].get_wiki_link_with_icon()}')
                else:
                    return self._prefix_target(target, f'Has {parser.national_spirits[req].get_wiki_link_with_icon()}')
            case 'CR_CheckTag':
                tag = req.removeprefix('+')
                if ignored_tag_requirements and tag in ignored_tag_requirements:
                    return ''
                what = parser.formatter.convert_to_wikitext(parser.localize(tag, 'Game-Tag', default=f'<tt>{tag}</tt>'))
                return self._prefix_target(target, f'Is a {what}<!-- tag {req} -->')
            case 'CR_Region':
                if req == '!IDLE':
                    # if requirement.get_or_default('AddToEntityBuffer', False):
                    return self._prefix_target(target, f'Owns a region which is constructing a building')
                pass
            case 'CR_DiplomaticRelationship':
                relation_type, op = req.split(',')
                if op == 'TRUE':
                    is_loc = 'Is'
                    have_loc = 'Has'
                elif op == 'FALSE':
                    is_loc = 'Is not'
                    have_loc = 'Does not have'
                else:
                    print(f'Unknown op "{op}" for CR_DiplomaticRelationship')
                    return None
                relation_locs = {'DR_Alliance': f'{is_loc} allied with',
                                 'DR_Hostile': f'{is_loc} hostile towards',
                                 'DR_OpenBorders': f'{have_loc} open borders with',
                                 'DR_Peace': f'{is_loc} at peace with',
                                 'DR_War': f'{is_loc} at war with', }
                return f'{relation_locs[relation_type]} {self.format_effect_target(target)}'

            case 'CR_DiplomaticRelationshipValue':
                pass
            case 'CR_ChosenAge':
                condition, age_number = req.split(',')
                if condition == 'NONE':
                    return self._prefix_target(target, f"Has ''not'' reached age {age_number} yet")
                elif condition == 'ANY':
                    return self._prefix_target(target, f"Has reached at least age {age_number}")
                elif condition.removesuffix('-BASE') in parser.ages:
                    return self._prefix_target(target, f"Is or was in the {parser.ages[condition.removesuffix('-BASE')].display_name}")
            case 'CR_Player':
                if req == 'HasReligion,ANY:TRUE':
                    return self._prefix_target(target, 'Has a state religion')
                pass
            case 'CR_Tech':
                if ',' in req:
                    tech_name, op = req.split(',')
                else:
                    tech_name = req
                    op = 'TRUE'
                tech = parser.all_cards[tech_name].get_wiki_link_with_icon()
                if op == 'TRUE':
                    return f'{tech}'
                elif op == 'FALSE':
                    return f"Does ''not'' have {tech}"
            case 'CR_AI':
                pass
            case 'CR_Locked':
                msg = parser.misc_game_data[f'CR_Locked-{req}']
                return f'{{{{icon|no}}}} Disabled with the message {parser.formatter.quote(msg)}'

    @staticmethod
    def get_notes_for_card_play(card, target_text: str = None, when: str = None, include_unlocks=True, collected_unlocks: list[Unlock]=None, target: str = None, parent_effect=None) -> list[str]:
        if target_text and not target_text.startswith(' '):
            target_text = f' {target_text}'
        if when:
            when_text = f'{when}, '
        else:
            when_text = ''
        notes = []
        if card in [
            'UNITACTIONS-STANDARD_TOWNBUILDINGWORK',  # I think this is just the setup that workers can work on improvements
            # STANDARD_RESOURCEGENERATOR is only used for capital, homeland and religious birthplace. I'm not sure what it does. Maybe it allows
            # gathering goods from the tile of the capital, but I have never seen a resource on that tile
            'UNITACTIONS-STANDARD_RESOURCEGENERATOR',
        ]:
            return []

        if card == 'PLAYERACTIONS-DIFFICULTY_PER_AGE':
            return ['If the player is an AI, [[difficulty]] bonuses are applied']
        card_obj = millenniagame.parser.all_cards[card]
        # card_effects = card_obj.get_effects(include_unlocks=True, recursive=True)
        new_unlocks = []
        if parent_effect == card_obj:  # to avoid infinite recursion
            card_effects = ''
        else:
            card_effects = card_obj.get_effects(include_unlocks=include_unlocks, recursive=True, collected_unlocks=new_unlocks)

        if card_effects:
            if card_obj.has_localized_display_name:
                # card_name = f'{millenniagame.parser.formatter.quote(card_obj.display_name)}<!-- {card} -->'
                card_name = f'{millenniagame.parser.formatter.quote(card_obj.display_name)}(<tt>{card}</tt>)'
            else:
                card_name = f'<tt>{card}</tt>'
            if target and target.startswith('ENTTAG,'):
                requirements = card_obj.get_requirements(ignored_tag_requirements=[target.removeprefix('ENTTAG,').removeprefix('+')])
            else:
                requirements = card_obj.requirements
            if requirements:
                notes.append(f'{when_text}If the following requirements are met:')
                notes.append(requirements)
                notes.append(f'then play the card {card_name}{target_text}:')
                for unlock in new_unlocks:
                    unlock.add_condition(requirements)
                notes.append(card_effects)
            else:
                # notes.append(f'{when_text}Play card {card_name}{target_text}:')
                if when_text:
                    target_text = re.sub(r'^ on ', 'for ', target_text)
                else:
                    target_text = millenniagame.parser.formatter.uc_first(target_text.removeprefix(' on '))
                if len(when_text + target_text) > 0:
                    notes.append(f'{when_text}{target_text}<!-- Play card {card} -->:')
                    notes.append(card_effects)
                else:
                    # inline the effect, because we have no details
                    notes.extend(card_effects)

        if collected_unlocks is not None:
            collected_unlocks.extend(new_unlocks)
        return notes


class Deck(NamedAttributeEntity):
    cards: dict[str, CardBaseClass]


class DomainSpecialization(Deck):
    description: str
    infopedia: str
    resource: Resource
    base_tech: 'TechnologyBaseClass'
    technologies: dict[str, 'TechnologyBaseClass']

    _localization_category: str = 'DomainSpecialization'

    extra_data_functions = {'description': lambda data: millenniagame.parser.formatter.strip_formatting(
        millenniagame.parser.localize(data['name'], 'DomainSpecialization', 'DetailsText', default='')),
                            'infopedia': lambda data: millenniagame.parser.localize(data['name'], 'Info-Topic', 'MainText', default='')}

    def __init__(self, attributes: dict[str, any]):
        super().__init__(attributes)
        self.base_tech = self.cards[f'{self.name}-AUTOMATIC']
        self.technologies = {name: card for name, card in self.cards.items() if
                             isinstance(card, (NationalSpiritTech, GovernmentTech)) and card != self.base_tech}

    def get_icon_image(self) -> Image.Image | None:
        """get the icon from the game assets"""
        return millenniagame.parser.unity_reader.get_image_resource(f'ui/icons/nationalspirit/NSIconSmall-{self.name}')

    def get_small_image(self) -> Image.Image | None:
        """get the icon from the game assets"""
        return millenniagame.parser.unity_reader.get_image_resource(f'ui/icons/nationalspirit/NSIcon-{self.name}')

    def get_image(self) -> Image.Image | None:
        """get the big image from the game assets"""
        return millenniagame.parser.unity_reader.get_image_resource(f'ui/icons/nationalspirit/NSPortrait-{self.name}')

    def get_wiki_image_filename(self) -> str:
        """Filename for the big image"""
        return f'{self.get_wiki_filename_prefix()} portrait {self.display_name}.png'

    def get_wiki_small_image_filename(self) -> str:
        """Filename for the small image"""
        return super().get_wiki_filename()

    def get_wiki_icon_filename(self) -> str:
        """Filename for the white icon image"""
        return f'{self.get_wiki_filename_prefix()} icon {self.display_name}.png'

    def get_wiki_filename(self) -> str:
        """Use the small image as the default icon"""
        return self.get_wiki_small_image_filename()

    @cached_property
    def unlock_names(self) -> list[str]:
        return self.base_tech.unlock_names

    @property
    def spawns(self) -> list[str]:
        return self.base_tech.spawns


class NationalSpirit(DomainSpecialization):
    base_tech: 'NationalSpiritTech'
    technologies: dict[str, 'NationalSpiritTech']
    age: int

    def __init__(self, attributes: dict[str, any]):
        super().__init__(attributes)
        for card in self.cards.values():
            card.national_spirit = self

    def get_wiki_page_name(self) -> str:
        return 'National spirits'

    def get_wiki_icon(self, size: str = '24px', link='self') -> str:
        return f'{{{{backedIcon|{self.display_name}}}}}'


class Government(DomainSpecialization):
    age: int
    tier: int

    _localization_category: str = 'DomainSpecialization'

    def __init__(self, attributes: dict[str, any]):
        super().__init__(attributes)
        for card in self.cards.values():
            card.government = self

    def get_wiki_page_name(self) -> str:
        return 'Government'

    def get_wiki_icon(self, size: str = '24px', link='self') -> str:
        return f'{{{{backedIcon|{self.display_name}|government}}}}'


class TechnologyBaseClass(CardBaseClass):
    ages: list['Age']

    def __init__(self, attributes: dict[str, any]):
        self.ages = []
        super().__init__(attributes)


class Technology(TechnologyBaseClass):

    @cached_property
    def cost(self) -> int:
        return int(self.tags.get('TechCostBase'))

    @cached_property
    def is_age_advance(self):
        return self.tags.has('AgeAdvance')

    @cached_property
    def advance_to_age(self) -> 'Age':
        for effects in self.choices.find_all_recursively('ACardEffect'):
            if not isinstance(effects, list):
                effects = [effects]
            for effect in effects:
                if effect['EffectType'] == 'CE_ResearchTech':
                    return millenniagame.parser.ages[effect['Payload'].removesuffix('-BASE')]

    def get_wiki_filename(self) -> str:
        if self.is_age_advance:
            return self.advance_to_age.get_wiki_filename()
        return super().get_wiki_filename()

    def get_icon_image(self) -> Image.Image | None:
        """get the icon from the game assets"""
        return millenniagame.parser.unity_reader.get_card_icon(self.name, 'techs')

    def get_wiki_page_name(self) -> str:
        return 'Research'


class AgeBaseTech(TechnologyBaseClass):
    def get_wiki_page_name(self) -> str:
        return self.ages[0].get_wiki_page_name()

    def get_wiki_filename_prefix(self) -> str:
        return 'Age'


class Age(Deck):
    base_tech: AgeBaseTech
    technologies: dict[str, Technology]
    other_cards: dict[str, CardBaseClass]
    infopedia: str

    _localization_suffix = 'AgeTitle'

    extra_data_functions = {
        'infopedia': lambda data: millenniagame.parser.localize(data['name'] + '-BASE', 'Info-Topic', 'MainText', default='')}

    @cached_property
    def order(self) -> int:
        return int(self.base_tech.tags.get('AgeTech'))

    @cached_property
    def type(self) -> str:
        for typ in ['CrisisAge', 'VictoryAge', 'VariantAge']:
            if self.base_tech.tags.has(typ):
                return typ
        return 'DefaultAge'

    @cached_property
    def type_loc(self) -> str:
        return {'DefaultAge': 'Standard Age',
                'CrisisAge': 'Crisis Age',
                'VictoryAge': 'Victory Age',
                'VariantAge': 'Variant Age',
                }[self.type]

    def get_icon_image(self) -> Image.Image | None:
        """get the small square image from the game assets. It is in the advance techs, but I dont know if it is shown ingame"""
        for tech in millenniagame.parser.technologies.values():
            if tech.is_age_advance and tech.advance_to_age == self:
                return tech.get_icon_image()

    def get_image(self) -> Image.Image | None:
        """get the big image from the game assets"""
        return millenniagame.parser.unity_reader.get_image_resource(self.base_tech.tags.get('AgeImage').lower())

    def get_wiki_icon_filename(self) -> str:
        return f'{self.display_name} icon.png'

    def get_wiki_page_name(self) -> str:
        # if self.order > 2:
        return f'Age {self.order}'
        # else:
        #     return 'Ages'

    @cached_property
    def unlock_names(self) -> list[str]:
        return self.base_tech.unlock_names

    @property
    def spawns(self) -> list[str]:
        return self.base_tech.spawns

    @property
    def tags(self):
        return self.base_tech.tags


class NationalSpiritTech(TechnologyBaseClass):
    layer: int
    national_spirit: NationalSpirit

    @cached_property
    def cost(self) -> Cost:
        cost = self.tags.get('PurchaseCost')
        if cost is None:
            return NoCost()
        if len(cost) > 1:
            raise Exception('More than one cost is not supported')
        res, value = cost[0].split(':')
        return Cost(res, value)

    def get_wiki_icon(self, size: str = '24px') -> str:
        return self.national_spirit.get_wiki_icon(size)

    def get_wiki_page_name(self) -> str:
        return self.national_spirit.get_wiki_page_name()


class GovernmentTech(TechnologyBaseClass):
    layer: int
    government: Government

    @cached_property
    def cost(self) -> Cost:
        cost = self.tags.get('PurchaseCost')
        if cost is None:
            return NoCost()
        if len(cost) > 1:
            raise Exception('More than one cost is not supported')
        res, value = cost[0].split(':')
        return Cost(res, value)

    def get_wiki_icon(self, size: str = '24px') -> str:
        return ''

    def get_wiki_page_name(self) -> str:
        return self.government.get_wiki_page_name()


class Goods(NamedAttributeEntity):
    chain: str
    consumeValues: list  # TODO: parsing
    tags: Tags = None

    _tag_for_name = 'ID'
    _localization_category = 'Goods'

    transform_value_functions = {'tags': lambda tags: Tags(tags['Tag']),
                                 'consumeValues': lambda values: [ResourceValue.parse(entry) for entry in (
                                     values['ConsumeValue'] if isinstance(values['ConsumeValue'], list) else [values['ConsumeValue']])]
                                 }

    def is_same_or_matches_tag(self, other: 'Goods') -> bool:
        if self == other:
            return True
        elif type(other) != Goods:
            # other is a subclass, so let them decide
            return other.is_same_or_matches_tag(self)
        else:
            return False

    def get_icon_image(self) -> Image.Image | None:
        """get the icon from the game assets"""
        return millenniagame.parser.unity_reader.get_image_resource(f'ui/icons/Goods{self.name}-icon')

    @cached_property
    def produced_in(self) -> list[BuildingBaseClass]:
        # TODO: include gathering and other ways to gain goods
        # if self.name.startswith('TradeGood'):
        #     sources.append('[[Import]]')
        sources = []
        for building in list(millenniagame.parser.buildings.values()) + list(millenniagame.parser.improvements.values()):
            if self in building.get_goods_productions():
                sources.append(building)
            else:
                for chain in building.get_production_chains():
                    if chain.result_goods == self:
                        sources.append(building)
        return list(dict.fromkeys(sources))  # de-duplicate without changing the order

    @cached_property
    def used_in(self) -> list[BuildingBaseClass]:
        # TODO: include gathering and other ways to gain goods
        # if self.name.startswith('TradeGood'):
        #     users.append('[[Import]]')
        users = []
        for building in list(millenniagame.parser.buildings.values()) + list(millenniagame.parser.improvements.values()):
            for chain in building.get_production_chains():
                if self.is_same_or_matches_tag(chain.source_goods):
                    users.append(building)
        return list(dict.fromkeys(users))  # de-duplicate without changing the order

    @cached_property
    def made_from(self) -> ['Goods']:
        sources = []
        for building in list(millenniagame.parser.buildings.values()) + list(millenniagame.parser.improvements.values()):
            for chain in building.get_production_chains():
                if self.is_same_or_matches_tag(chain.result_goods):
                    sources.append(chain.source_goods)
        return list(dict.fromkeys(sources))  # de-duplicate without changing the order

    @cached_property
    def converted_to(self) -> ['Goods']:
        result_goods = []
        for building in list(millenniagame.parser.buildings.values()) + list(millenniagame.parser.improvements.values()):
            for chain in building.get_production_chains():
                if self.is_same_or_matches_tag(chain.source_goods):
                    result_goods.append(chain.result_goods)
        return list(dict.fromkeys(result_goods))  # de-duplicate without changing the order


class GoodsTag(Goods):

    def __init__(self, name, goods: list[Goods]):
        super().__init__({'name': name})
        self.goods = goods
        self.display_name = '/'.join(goods.display_name for goods in self.goods)

    def get_wiki_icon(self, size: str = '24px') -> str:
        return '/'.join(goods.get_wiki_icon(size) for goods in self.goods)

    def get_wiki_link(self) -> str:
        return '/'.join(goods.get_wiki_link() for goods in self.goods)

    def get_wiki_link_with_icon(self) -> str:
        if self.name == 'PlantationGood':
            return '{{#lst:Research|plantationGood}}'  # TODO: generalize
        else:
            return super().get_wiki_link_with_icon()

    def is_same_or_matches_tag(self, other: 'Goods') -> bool:
        for goods in self.goods:
            if goods == other:
                return True

        return False


class DomainPower(NamedAttributeEntity):
    iconName: str = None
    domain: str  # TODO parse domain
    effectType: str
    cost: Cost = None
    params: Data
    cooldown: int = None
    tags = Tags([])

    _tag_for_name = 'ID'
    _localization_category = 'Game-Culture'

    transform_value_functions = {'cost': Cost.parse,
                                 'params': lambda params: Data(params['Param'])}

    def is_culture_power(self):
        return self.cost is None

    def get_icon_image(self) -> Image.Image | None:
        """get the icon from the game assets"""
        if self.iconName:
            return millenniagame.parser.unity_reader.get_image_resource(f'ui/icons/culture powers/{self.iconName}-icon')
        else:
            return None

    @cached_property
    def description(self):
        description = millenniagame.parser.localize(self.name, 'Game-Culture', 'PowerTooltip')
        description = re.sub(r'^<size.*?><b>' + re.escape(self.display_name) + r'</b></size>\n*<i>[^<]* (Culture|Domain) Power</i>\n*', '', description)
        return millenniagame.parser.formatter.convert_to_wikitext(description)

    def get_domain_icon(self):
        if self.domain == 'DomainSpecial':
            return 'Special'  # I don't think there is an icon for them
        else:
            return '{{icon|' + self.domain.removeprefix('Domain').lower() + '}}'

    def get_domain_name_and_icon(self):
        return '{{icon|' + self.domain.removeprefix('Domain').lower() + '}} ' + self.domain.removeprefix('Domain')

    def get_wiki_page_name(self) -> str:
        if self.is_culture_power():
            return 'Culture'
        else:
            return 'Domains'

    @cached_property
    def spawns(self):
        result = []
        match self.effectType:
            case 'CET_SpawnUnit':
                result.append(self.params.get('SpawnUnitType'))
            case 'CET_PlayCard':
                card_name = self.params.get('CardName')
                if card_name in millenniagame.parser.all_cards:
                    result.extend(millenniagame.parser.all_cards[card_name].spawns)
                else:
                    print(f'Warning: "{self.name}" tried to play non-existing card "{card_name}"')
        for power in self.linked_powers:
            result.extend(power.spawns)
        return result

    @cached_property
    def linked_powers(self) -> list['DomainPower']:
        return [
            millenniagame.parser.domain_powers[power_name] for power_name in self.params.get_as_value_list('LinkedPower')
            if power_name in millenniagame.parser.domain_powers
        ]

    @cached_property
    def all_linked_powers_recursive(self) -> set['DomainPower']:
        result = set()
        for power in self.linked_powers:
            result.add(power)
            result.update(power.all_linked_powers_recursive)
        return  result


class Landmark(NamedAttributeEntity):

    category: str
    params: Data = Data([])

    _tag_for_name = 'ID'
    _localization_category: str = 'Landmark'

    transform_value_functions = {'params': lambda params: Data(params['Param'] if params and 'Param' in params else [])}

    @cached_property
    def terrains(self) -> list['Terrain']:
        if self.params.has('Placement-TerrainType'):
            return [millenniagame.parser.terrains[self.params.get('Placement-TerrainType')]]
        terrains = []
        if self.params.has('Placement-TerrainTag'):
            for _, tag in self.params.get_as_list('Placement-TerrainTag'):
                terrains.extend(millenniagame.parser.get_terrains_by_tag(tag))
        return terrains

@dataclass
class Gather:
    name: str
    display_name: str
    goods: Goods
    amount: int


class Terrain(NamedAttributeEntity):
    dataValues: Data
    tags: Tags
    minimapColor: str
    mapGenColor: str
    workerEntryPrefab: str
    moveCost: int = 10
    expansionCost: Decimal
    terrainDefenseBonus: Decimal = Decimal(1.0)

    # several UI related data is ignored

    _tag_for_name = 'ID'
    _localization_category = 'Game-Terrain'
    _localization_suffix = None

    transform_value_functions = {'tags': lambda tags: Tags(tags['Tag']),
                                 'dataValues': lambda params: Data(params['Data'])
                                 }

    def __init__(self, attributes: dict[str, any]):
        super().__init__(attributes)
        if self.dataValues.has('MoveCost'):
            self.moveCost = int(self.dataValues.get('MoveCost'))
        self.expansionCost = Decimal(self.dataValues.get('ExpansionCost'))
        if self.dataValues.has('TerrainDefenseBonus'):
            self.terrainDefenseBonus = Decimal(self.dataValues.get('TerrainDefenseBonus'))

    @cached_property
    def foraging(self) -> list[str]:
        results = [millenniagame.parser.formatter.format_resource(resource, value) for
                resource, value in self.dataValues.get_as_list('TileData:Workable')
                if float(value) != 0]
        for card in millenniagame.parser.all_cards.values():
            foraging_effects = card.traverse_effects('CE_AdjustGameData', lambda effect: effect['Payload'] if effect['Payload'].startswith('WorkableBonusResource') else None)
            conditional_effects = []
            for effect in foraging_effects:
                _, resource, tag, operator, value = re.split('[-,]', effect)
                assert(operator == 'ADD')
                if self.tags.has(tag.removeprefix('+')):
                    conditional_effects.append(millenniagame.parser.formatter.format_resource(resource, value, add_plus=True))
            if len(conditional_effects) > 0:
                results.append(f'With {card.get_wiki_link()}:')
                results.append(conditional_effects)
        return results

    @cached_property
    def gathers(self) -> list[Gather]:
        return [Gather(name, millenniagame.parser.localize(name, 'Goods-Special-TileProduction', 'DisplayName'), millenniagame.parser.goods[goods], amount) for
                name, goods, amount in self.dataValues.get_as_list('TileData:GoodsProduction')]

    @cached_property
    def potential_goods(self):
        return [tile for tag in self.tags.unparsed_entries
                if tag in millenniagame.parser.terrain_tags_to_bonus_tiles
                for tile in millenniagame.parser.terrain_tags_to_bonus_tiles[tag]]

    @cached_property
    def potential_landmarks(self):
        return [landmark for landmark in millenniagame.parser.landmarks.values() if self in landmark.terrains]

    @cached_property
    def improvements(self):
        return [improvement for improvement in millenniagame.parser.improvements.values() if self in improvement.terrains]

    def get_icon_image(self) -> Image.Image | None:
        """get the icon from the game assets"""
        # small icon; not actually used on the wiki, because it uses big icons which were uploaded manually
        return millenniagame.parser.unity_reader.get_image_resource(f'terrain/{self.name}-HEXICON')

    def get_wiki_page_name(self) -> str:
        return 'Tiles'

    @property
    def startingData(self):
        return self.dataValues

    @cached_property
    def is_land(self) -> bool:
        return self.tags.has('Land')

    @cached_property
    def allows_movement(self) -> bool:
        return self.tags.has('LandMovement') or self.tags.has('WaterMovement') or self.name in [
            'TT_DEEPFOREST', 'TT_JUNGLE',  # they allow movement through the scouting tech
        ]

    @cached_property
    def allows_town(self) -> bool:
        return self.is_land and self.allows_movement


class Action(CardBaseClass):
    cardSpriteName: str = None

    def get_icon_image(self) -> Image.Image | None:
        """get the icon from the game assets"""
        if self.cardSpriteName:
            return millenniagame.parser.unity_reader.get_image_resource(self.cardSpriteName)
        else:
            return None


class UnitAction(Action):

    extra_data_functions = {'description': lambda data: millenniagame.parser.localize(data['name'], localization_suffix='Tooltip', default='')}

    @cached_property
    def units(self) -> list[Unit]:
        """Units which have this action per default"""
        return [unit for unit in millenniagame.parser.units.values() if self in unit.actions]

    def is_real_unit_action(self):
        # some unit actions are just helpers which are called by other effects. These don't usually have a display name
        # We can't check it with self.has_localized_display_name, because some actions which dont have a display name get one via overrides,
        # but these are not real unit actions either and they should not get an icon or be linked
        return (self.name + '-CardTitle') in millenniagame.parser.unity_reader.localizations

    def get_wiki_link(self) -> str:
        if self.is_real_unit_action():
            return super().get_wiki_link()
        else:
            return self.display_name

    def get_wiki_icon(self, size: str = '24px', link='self') -> str:
        if self.is_real_unit_action():
            return super().get_wiki_icon(size, link)
        else:
            return ''


class PlayerAction(Action):
    pass


class TileAction(Action):

    def get_wiki_filename_prefix(self):
        return 'Unit action'


class Need(NamedAttributeEntity):
    _tag_for_name: str = 'ID'
    _localization_category: str = 'Game-GameData-Misc-NeedTarget'
    _localization_suffix: str = None

    # TODO: take the icon from the GameDataKey
    gameDataKey: str

    targetValueKey: str
    scaleTarget: str
    minimumThreshold: str
    floorSatisfaction: float
    evaluateKeySpecialNotation: bool
    thresholds: Tree
    enableByPlayerData: str


class GameValue(NamedAttributeEntity):
    base: float
    comment: str = ''

    _tag_for_name: str = 'Name'
    _localization_category: str = 'Game-GameData-Misc-GameVal'
    _localization_suffix: str = 'Base'
    tag_to_attribute_map = {'#comment': 'comment'}

    def __init__(self, attributes: dict[str, any]):
        original_name = attributes['name']
        attributes['name'] = original_name.removeprefix('#')  # so that localisation works
        super().__init__(attributes)
        self.name = original_name

    @staticmethod
    def handle_comment(comment):
        if isinstance(comment, list):
            comment = '\n'.join(comment)
        comment = re.sub(r'<Base>.*?</Base>', '', comment)
        return comment

    transform_value_functions = {'comment': handle_comment}


class StartupBonus(NamedAttributeEntity):
    description: str

    extra_data_functions = {'description': lambda data: millenniagame.parser.localize(data['name'], localization_suffix='Tooltip', default='')}

    @cached_property
    def transclude_section_name(self):
        return f'starting_bonus_{self.name.removeprefix("TECHAGE1-STARTUPBONUS-")}'


class NameTable(NamedAttributeEntity):
    tableType: str
    names: Tree

    _localization_category = 'UI-MainMenu-NationBuilder'
    _localization_suffix = None
    _tag_for_name = 'ID'

    @cached_property
    def localized_names(self):
        return sorted([millenniagame.parser.localize(name.strip('$'), self.name) for name in self.names.find_all('Name')])


class Nation(NamedAttributeEntity):
    playerName: str
    nationName: str
    cityNameCollection: NameTable
    townNameCollection: NameTable
    flag: str
    personality: str
    personality_loc: str
    personality_description: str
    startupBonuses: list[StartupBonus]

    transform_value_functions = {
        'startupBonuses': lambda startupBonuses: [millenniagame.parser.startup_bonuses[bonus] for bonus in startupBonuses.find_all('StartupBonus')],
        'cityNameCollection': lambda cityNameCollection: millenniagame.parser.name_tables[cityNameCollection],
        'townNameCollection': lambda townNameCollection: millenniagame.parser.name_tables[townNameCollection],
        }
    extra_data_functions = {
        'personality_loc': lambda data: millenniagame.parser.localize(data['personality'], 'Game-Personality'),
        'personality_description': lambda data: millenniagame.parser.localize(data['personality'], 'Game-Personality', 'Full'),
    }

    _localization_category = 'NationName'
    _localization_suffix = None
    _tag_for_name = 'ConfigID'

    def get_wiki_filename(self) -> str:
        if self.name == 'rome':
            return 'Flag Rome.png'
        return f'{self.flag.replace("Flags", "Flag")}.png'

    def get_icon_image(self) -> Image.Image | None:
        """get the flag from the game assets"""
        return millenniagame.parser.unity_reader.get_image_resource(f'misc/flags/{self.flag}')


class FactionReward(CardBaseClass):

    faction: 'Faction'
    tier: int

    @cached_property
    def threshold(self) -> int:
        return int(self.tags.get('FactionThreshold'))

    def get_wiki_page_name(self) -> str:
        return 'Factions'

    def get_wiki_filename(self) -> str:
        return ''


class Faction(NamedAttributeEntity):

    # tier -> Reward dict; tier is 1, 2, 3
    rewards: dict[int, FactionReward]

    _localization_category = 'Game-Faction'

    def __init__(self, attributes: dict[str, any]):
        self.rewards = {}
        super().__init__(attributes)

    def get_wiki_filename(self) -> str:
        return ''


class MegaProjectStage(NamedAttributeEntity):
    _localization_suffix = 'TITLE'
    _tag_for_name = 'StageID'

    project: 'MegaProject'
    iconName: str
    factionRewardFirst: int
    factionRewardSecond: int
    stageCard: CardBaseClass

    transform_value_functions = {'stageCard': lambda card_name: millenniagame.parser.all_cards[card_name]}

    @cached_property
    def _localization_category(self):
        return f'Megaprojects-{self.project.name}'

    @cached_property
    def unlock_names(self) -> list[str]:
        return [unlock.entity_name for unlock in self.unlocks]

    @cached_property
    def unlocks(self):
        return self.stageCard.unlocks

    def get_icon_image(self) -> Image.Image | None:
        """get the icon from the game assets"""
        return millenniagame.parser.unity_reader.get_image_resource(f'UI/Icons/{self.iconName}-ICON')

    def get_wiki_filename_prefix(self) -> str:
        return 'Megaproject'

    def get_wiki_page_name(self) -> str:
        return 'Megaprojects'


class MegaProject(NamedAttributeEntity):
    _tag_for_name = 'ProjectID'
    _localization_suffix = 'Title'
    _localization_category = 'UI-Megaprojects'
    stages: list[MegaProjectStage]

    def get_wiki_page_name(self) -> str:
        return 'Megaprojects'


class DLC(NamedAttributeEntity):

    def get_wiki_filename_prefix(self) -> str:
        return 'DLC'

    def get_wiki_link_target(self):
        return self.display_name

    def get_wiki_icon(self, size: str = '', link='self') -> str:
        if size:
            size = '|' + size
        return f'{{{{icon|{self.display_name.lower()}{size}}}}}'


@dataclass
class CardUsage:
    name: str
    card: CardBaseClass
    """this card applies the effect"""
    entities: list[MillenniaEntity]
    """entities which use this Card"""


@dataclass
class CardUsageWithTarget(CardUsage):
    target: str
    """usually PLAYER"""


@dataclass
class DataLinkAction(CardUsageWithTarget):
    value_type: str
    """if this value in the target changes, the data link gets recalculated"""

    @cached_property
    def effects(self) -> list[str]:
        return self.card.get_effects()

    @cached_property
    def tooltips(self) -> list[str]:
        return [effect.removeprefix('Tooltip: ') for effect in self.effects if isinstance(effect, str) and effect.startswith('Tooltip: ')]
