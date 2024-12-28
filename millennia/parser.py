import copy
import operator
import warnings
import xml.etree.ElementTree as ET
from typing import TypeVar, Type, Callable

import xmltodict

from common.paradox_parser import Tree
from millennia.millennia_lib import *
from millennia.unity_reader import UnityReaderMillennia

NE = TypeVar('NE', bound=NamedAttributeEntity)


class MillenniaParser:
    # allows the overriding of localization strings
    localizationOverrides = {
        # avoid duplicate names
        'TECHAGE10_VICTORYCOLONYSHIP-REPEATABLE-CardTitle': 'Technological Advancements (Repeatable, Age of Departure)',
        'TECHAGE10_VICTORYARCHANGEL-REPEATABLE-CardTitle': 'Technological Advancements (Repeatable, Age of Archangels)',
        'TECHAGE10_VICTORYTRANSCENDENCE-REPEATABLE-CardTitle': 'Technological Advancements (Repeatable, Age of Transcendence)',

        'Game-Culture-DiplomacyHireMercenaries-DisplayName': 'Hire Mercenaries (Age of Monuments)',
        'Game-Culture-WarfareMercenariesHireMercenaries-DisplayName': 'Hire Mercenaries (Mercenaries national spirit)',

        'UNITACTIONS-ARTIST_CULTURAL_MOVEMENT-CardTitle': 'Cultural Movement (Artist)',
        'UNITACTIONS-CELEBRITY_CULTURAL_MOVEMENT-CardTitle': 'Cultural Movement (Celebrity)',
        'UNITACTIONS-MOTHERSHIP_RANDOMEFFECT-CardTitle': 'Random effect of the [[Alien Mothership]] at the start of a turn',
        'UNITACTIONS-INVADER_RAZEGOODTILE-CardTitle': '[[Alien invader]] razing a bonus tile',
        'UNITACTIONS-DOCK_SPAWNUTILITY-CardTitle': 'Building the first [[dock]]',

        'Entity-UNIT_ALIENINVADER_NAVY-DisplayName': 'Alien Invader (Navy)',
        'Entity-UNIT_BATTLESHIP_DEFENDER-DisplayName': 'Battleship (City Defender)',

        'TECHAGE7_CRISISOLDONES-REPEATABLE-CardTitle': 'Beckon The Old Ones (Repeatable)',  # original has linebreaks
        'UI-Megaprojects-SPACERACE-Title': 'Space Race',  # the more common wording

        # originals have : and icons and html formatting
        'UNITACTIONS-MERCHANT_DEPLOY_FOREIGN-CardTitle': 'Deploy Wealth',
        'UNITACTIONS-ALCHEMIST_GATHERARCANA-CardTitle': 'Gather Arcana',
        'Goods-Special-TileProduction-ANYBONUS-DisplayName': 'Gather (any bonus goods)',
        'Game-Tag-Town': 'Towns',
    }

    def __init__(self):
        self.unparsed_attributes_for_import = {}
        self.all_parsed_entities = {}
        self.cards_which_use_tag = {}

    @cached_property
    def unity_reader(self) -> UnityReaderMillennia:
        return UnityReaderMillennia()

    def localize(self, key: str, localization_category: str = None, localization_suffix: str = None,
                 default: str = None, return_none_instead_of_default=False) -> str | None:
        """localize the key from the english millennia localization files

        if the key is not found, the behavior depends on return_none_instead_of_default:
            if it is true, None is returned
            if it is false, the default is returned unless it is None in which case the key is returned
        """
        if default is None:
            default = key

        if localization_category is not None:
            key = f'{localization_category}-{key}'

        if localization_suffix is not None:
            key = f'{key}-{localization_suffix}'

        if key in self.localizationOverrides:
            return self.localizationOverrides[key]
        else:
            if return_none_instead_of_default and key not in self.unity_reader.localizations:
                return None
            else:
                return self.unity_reader.localizations.get(key, default)

    def localize_upgrade_line(self, upgrade_line: str) -> str:
        loc = self.localize(upgrade_line, 'Game-UpgradeLine-UpgradeLine')
        loc = self.formatter.strip_formatting(loc)
        return loc.removeprefix('Upgrade Line: ')

    @cached_property
    def formatter(self):
        from millennia.text_formatter import MillenniaWikiTextFormatter
        return MillenniaWikiTextFormatter()

    def parse_nameable_entities(self, entity_class: Type[NE], filename, resource_folder: str = 'text',
                                element_selector: str = '.') -> dict[str, NE]:
        result = {}
        for entry in self.get_resource_xml(filename, resource_folder).findall(element_selector):
            attributes = {}
            name = ''
            for attribute in entry:
                if attribute.tag == entity_class._tag_for_name:
                    name = attribute.text
                    attributes['name'] = name
                else:
                    attributes[self.map_xml_tag_to_python_attribute(attribute.tag, entity_class)] = attribute.text
            if name:
                obj = entity_class(attributes)
                result[name] = obj
            else:
                print(f'Ignoring unamed entity "{attributes}"')
        return result

    @staticmethod
    def xml_postprocessor(path, key, value):
        """turn dicts into Tree"""
        if isinstance(value, dict):
            value = Tree(value)
        return key, value

    def parse_nameable_entities_with_xmltodict(self, xml_tag: str, filename: str, resource_folder: str = 'text',
                                               default_entity_class=None, tag_for_name: str = None, process_comments=False) -> dict[str, NamedAttributeEntity]:
        result = {}
        entries = []

        if tag_for_name is None:
            if default_entity_class is None:
                raise Exception('Either tag_for_name must not be none or there must be a default_entity_class which has the attribute _tag_for_name')
            else:
                tag_for_name = default_entity_class._tag_for_name

        for relevant_element in Tree(xmltodict.parse(self.unity_reader.text_asset_resources[resource_folder][filename],
                                                     postprocessor=self.xml_postprocessor,
                                                     process_comments=process_comments)
                                     ).find_all_recursively(xml_tag):
            if isinstance(relevant_element, list):
                entries.extend(relevant_element)
            else:
                entries.append(relevant_element)

        # store data so that it can be imported. It has to be done in a separate loop, because sometimes
        # the imported entity comes later in the file
        for entry in entries:
            if tag_for_name in entry:   # no name tag usually means that this is a pure import
                self.unparsed_attributes_for_import[entry[tag_for_name]] = entry

        for entry in entries:
            name = None
            if tag_for_name in entry:
                if entry[tag_for_name] in [
                    'UNIT_DEBUGSCOUT',  # debugging unit in GameEntities.txt which imports UNIT_SCOUT from ages/TECHAGE1-Entities.txt
                    'B_TOWN',  # not sure what to do with this
                    'FAKE_ENTITY_PLAYERSTART',
                ]:
                    continue
                while 'Import' in entry:  # to deal with imports which have an import as well
                    import_entry = copy.deepcopy(self.unparsed_attributes_for_import[entry['Import']])
                    del entry['Import']
                    import_entry.update(entry)
                    entry = import_entry

                if default_entity_class:
                    entity_class = default_entity_class
                else:
                    entity_class = self.determine_class(entry[tag_for_name], xml_tag, entry)
                if not entity_class:
                    # skip unhandled stuff
                    continue
                obj = self.create_entity(entity_class, tag_for_name, entry)
                if obj:
                    name = obj.name
                    self.all_parsed_entities[name] = obj
                    self.unparsed_attributes_for_import[name] = entry
                else:
                    name = ''
            else:
                # no name tag usually means that this is a pure import
                if 'Import' in entry and len(entry) == 1:  # pure import
                    name = entry['Import']
                    if name in self.all_parsed_entities:
                        obj = self.all_parsed_entities[name]
                    else:
                        # the imports are not necessarily loaded before, so we have to use a lazy loading to load them later
                        obj = LazyObject(self.all_parsed_entities, name)
            if name:
                result[name] = obj
            else:
                print(f'Ignoring unamed entity "{entry}"')
                continue
        return result

    def create_entity(self, entity_class: Type[NE], tag_for_name: str, data: Tree) -> NE|None:
        attributes = {}
        name = ''
        for key, value in data:
            if key == tag_for_name:
                name = value
                attributes['name'] = name
            else:
                attributes[self.map_xml_tag_to_python_attribute(key, entity_class)] = value
        if name:
            return entity_class(attributes)
        else:
            return None

    @cached_property
    def entities(self) -> dict[str, MillenniaEntity]:
        result = {}

        for folder, files in self.unity_reader.text_asset_resources.items():
            for filename in files:
                if filename.lower().endswith('entities') or filename.lower() == 'maptiles':
                    result.update(self. parse_nameable_entities_with_xmltodict('EntityInfo', filename, folder, tag_for_name='ID'))
        return result

    @staticmethod
    def determine_class(name: str, tag_name: str, attributes: Tree) -> type[NamedAttributeEntity] | None:
        if tag_name == 'EntityInfo':
            tags = attributes['Tags']['Tag']
        elif tag_name == 'ACard':
            try:
                tags = attributes['CardTags']['Tags']['Tag']
            except (TypeError, KeyError):  # one of the xml elements doesn't exist
                tags = []
        else:
            raise Exception(f'Unimplemented tag "{tag_name}"')
        if isinstance(tags, str):
            tags = [tags]
        tag_class_map = {
            'AgeBaseTech': AgeBaseTech,
            'Unit': Unit,
            'Barbarian': Unit,
            'CityBuilding': Building,
            'Improvement': Improvement,
            'TownSpec': TownSpecialization,
            'Overlay': TileOverlay,
            'CityProject': CityProject,
            'MapTile': MapTile,
        }

        for tag, cls in tag_class_map.items():
            if tag in tags:
                return cls

        if tag_name == 'ACard':
            for tag in tags:
                if 'Layer' in attributes:
                    if tag.startswith('PurchaseCost-ResDomainGovernment') or tag == 'DomainResource:ResDomainGovernment':
                        return GovernmentTech
                    elif tag.startswith('PurchaseCost') or tag.startswith('DomainResource'):
                        return NationalSpiritTech
                elif tag.startswith('FactionThreshold'):
                    return FactionReward
            if 'Subtype' not in attributes or attributes['Subtype'] != 'CST_Tech':
                return CardBaseClass
            else:
                return Technology
        else:
            raise Exception(f'No class found for "{name}"')

    def get_resource_xml(self, filename: str, resource_folder: str = 'text') -> ET.Element:
        root = ET.XML(self.unity_reader.text_asset_resources[resource_folder][filename])
        return root

    @cached_property
    def infopedia_topic_types(self) -> dict[str, InfopediaTopicType]:
        topic_types = {}
        for entry in self.get_resource_xml('Infopedia'):
            type_id = entry.find('TopicType').text
            if type_id not in topic_types:
                topic_types[type_id] = InfopediaTopicType(attributes={'name': type_id})
        return topic_types

    @staticmethod
    def map_xml_tag_to_python_attribute(tag: str, cls: type[NamedAttributeEntity]):

        if tag in cls.tag_to_attribute_map:
            return cls.tag_to_attribute_map[tag]

        tag = convert_xml_tag_to_python_attribute(tag)

        if tag in cls.tag_to_attribute_map:
            return cls.tag_to_attribute_map[tag]
        else:
            return tag

    @cached_property
    def all_entities(self) -> dict[str, NE]:
        return dict(**self.technologies, **self.ages,
                    **self.infopedia_topics,
                    **self.entities, **self.domain_technologies, **self.domain_powers,
                    **self.unit_actions, **self.needs, **self.terrains, **self.landmarks)

    @cached_property
    def all_cards(self) -> dict[str, CardBaseClass]:
        ages_cards = {card.name: card for age in self.ages.values() for card in (list(age.other_cards.values()) + [age.base_tech])}
        domain_cards = {card.name: card for domain_deck in self.domain_decks.values() for card in domain_deck.cards.values()}
        sim_decks = {card.name: card for deck in self.sim_decks.values() for card in deck.values()}
        return dict(**sim_decks, **self.technologies, **ages_cards, **domain_cards, **self.player_actions, **self.unit_actions, **self.tile_actions)

    @cached_property
    def infopedia_topics(self) -> dict[str, InfopediaTopic]:
        # these are the entries which are directly accessible in the infopedia's misc section
        result = self.parse_nameable_entities(InfopediaTopic, 'Infopedia')

        # these entries are only available as tooltips ingame
        for loc_key in self.unity_reader.localizations:
            if loc_key.startswith('Info-Topic-CONCEPT') and loc_key.endswith('-Title'):
                topic_name = loc_key.removeprefix('Info-Topic-').removesuffix('-Title')
                if topic_name not in result:
                    result[topic_name] = InfopediaTopic({'name': topic_name, 'topicType': 'ITT_Misc'})
        return result

    @cached_property
    def buildings(self) -> dict[str, Building]:
        return {name: entity for name, entity in self.entities.items() if isinstance(entity, Building)}

    @cached_property
    def improvements(self) -> dict[str, Improvement]:
        return {name: entity for name, entity in self.entities.items() if type(entity) == Improvement and entity.name != 'IMPROVEMENT_BASE'}

    @cached_property
    def tile_overlays(self) -> dict[str, TileOverlay]:
        return {name: entity for name, entity in self.entities.items() if isinstance(entity, TileOverlay)}

    @cached_property
    def map_tiles(self) -> dict[str, MapTile]:
        return {name: entity for name, entity in self.entities.items() if isinstance(entity, MapTile)}

    @cached_property
    def units(self) -> dict[str, Unit]:
        return {name: entity for name, entity in self.entities.items() if isinstance(entity, Unit)}

    @cached_property
    def city_projects(self):
        return {name: entity for name, entity in self.entities.items() if isinstance(entity, CityProject)}

    def parse_decks_from_folder(self, top_folder, group_by_deck=False):
        # TODO: implement parsing of cards and other stuff
        result = {}
        for folder, files in self.unity_reader.text_asset_resources.items():
            if folder.startswith(top_folder):
                for filename, file_contents in files.items():
                    if filename.lower().startswith('deck'):
                        deck_name, entities = self.parse_deck_from_file(filename, folder)
                        if group_by_deck:
                            result[deck_name] = entities
                        else:
                            result.update(entities)
        return result

    def parse_deck_from_file(self, filename, folder='text', default_entity_class=None):
        entities = self.parse_nameable_entities_with_xmltodict('ACard',
                                                               filename,
                                                               resource_folder=folder,
                                                               tag_for_name='ID',
                                                               default_entity_class=default_entity_class)
        xml = xmltodict.parse(self.unity_reader.text_asset_resources[folder][filename])
        deck_name = xml['ADeck']['DeckName']
        for entity in entities.values():
            entity.deck_name = deck_name
        return deck_name, entities

    @cached_property
    def technologies(self) -> dict[str, Technology]:
        return {name: entity for age in self.ages.values() for name, entity in age.technologies.items() if isinstance(entity, Technology)}

    @cached_property
    def ages(self) -> dict[str, Age]:
        result = {}
        ages = self.parse_decks_from_folder('text/ages', group_by_deck=True)
        for name, cards in sorted(ages.items(), key=lambda item: item[0]):
            attributes = {
                'name': name,
                'base_tech': cards[f'{name}-BASE'],
                'technologies': {name: card for name, card in cards.items() if isinstance(card, Technology)},
                'other_cards': {name: card for name, card in cards.items() if not isinstance(card, (Technology, AgeBaseTech))},
            }

            age = Age(attributes)
            for card in cards.values():
                if hasattr(card, 'ages'):
                    card.ages.append(age)
                card.deck = age
            result[name] = age

        # sort ages by number and then by name so that the default ages are sorted before the variant ages
        sorted_ages = dict(sorted(result.items(), key=lambda entry: (entry[1].order, entry[0])))
        return sorted_ages

    @cached_property
    def domain_decks(self) -> dict[str, Deck]:
        result = {}
        for name, cards in self.parse_decks_from_folder('text/domains', group_by_deck=True).items():
            base_card = cards[f'{name}-AUTOMATIC']
            attributes = {'name': name, 'cards': cards, 'age': base_card.tags.get('DomainAge'), 'resource': Resource(base_card.tags.get('DomainResource'))}
            if attributes['resource'].name == 'ResDomainGovernment':
                cls = Government
                attributes['tier'] = base_card.tags.get('DomainTier')
            else:
                cls = NationalSpirit
            result[name] = cls(attributes)
            for card in cards.values():
                card.deck = result[name]
        return result

    @cached_property
    def domain_technologies(self):
        return {name: card for deck in self.domain_decks.values() for name, card in deck.technologies.items()}

    @cached_property
    def national_spirits(self) -> dict[str, NationalSpirit]:
        return {name: deck for name, deck in self.domain_decks.items() if isinstance(deck, NationalSpirit)}

    @cached_property
    def governments(self) -> dict[str, Government]:
        return {name: deck for name, deck in self.domain_decks.items() if isinstance(deck, Government)}

    @cached_property
    def goods(self) -> dict[str, Goods]:
        goods = self.parse_nameable_entities_with_xmltodict('GoodsInfo', 'GoodsInfo', default_entity_class=Goods)
        tags_to_goods = {}
        for good in goods.values():
            if good.tags:
                for tag in good.tags.unparsed_entries:
                    if tag not in tags_to_goods:
                        tags_to_goods[tag] = []
                    tags_to_goods[tag].append(good)
        for tag, goods_list in tags_to_goods.items():
            goods[f'+{tag}'] = GoodsTag(tag, goods_list)
        return goods

    @cached_property
    def domain_powers(self) -> dict[str, DomainPower]:
        return self.parse_nameable_entities_with_xmltodict('CulturePower', 'CulturePowers',
                                                           default_entity_class=DomainPower)

    @cached_property
    def landmarks(self):
        return self.parse_nameable_entities_with_xmltodict('Landmark', 'Landmarks', default_entity_class=Landmark)

    @cached_property
    def terrains(self) -> dict[str, Terrain]:
        return self.parse_nameable_entities_with_xmltodict('ATerrainType', 'TerrainTypes', default_entity_class=Terrain)

    def get_terrains_by_tag(self, tag: str) -> list[Terrain]:
        return self.get_entities_by_tag(tag, self.terrains)

    def get_entities_by_tag(self, tag: str, entities: list[MillenniaEntity] | dict[str, MillenniaEntity] = None) -> list[MillenniaEntity]:
        """search entities for entities with a given tag. If entities is None, self.all_entities is searched"""
        tag = tag.removeprefix('+')
        if entities is None:
            entities = self.all_entities

        if isinstance(entities, dict):
            entities = list(entities.values())
        return [entity for entity in entities if hasattr(entity, 'tags') and entity.tags.has(tag)]

    @cached_property
    def unit_actions(self) -> dict[str, UnitAction]:
        return self.parse_deck_from_file('UnitActions', default_entity_class=UnitAction)[1]

    @cached_property
    def player_actions(self) -> dict[str, PlayerAction]:
        return self.parse_deck_from_file('PlayerActions', default_entity_class=PlayerAction)[1]

    @cached_property
    def tile_actions(self) -> dict[str, UnitAction]:
        return self.parse_deck_from_file('TileActions', default_entity_class=TileAction)[1]

    @cached_property
    def misc_game_data(self) -> dict[str, str]:
        """effects which have a localization in Game-GameData-Misc"""
        overrides = {
            'TotalStrengthVsTopRivalRatio': '[[Power]] compared to the strongest rival Nation',  # add link
            'StatVassalIntegration': 'Vassal integration per turn when deployed',  # add "per turn when deployed"
            'StateReligionPopulationFrac': 'fraction of the population follows the state religion',  # original talks about worldwide population, but that seems to be wrong if the target is a region
            'Population': 'population',  # originally says "A Capital's Population", but the A does not fit into sentences and capital is more misleading than useful
        }
        result = {
            'AiWarehouseTownBonusValue': 'AI Warehouse Town Adjacency Bonus',  # no default localization
        }
        for loc_key, loc_text in self.unity_reader.localizations.items():
            key = None
            if loc_key.startswith('Game-GameData-Misc-'):
                key = loc_key.removeprefix('Game-GameData-Misc-')
            if loc_key.startswith('Game-Misc-'):
                key = loc_key.removeprefix('Game-Misc-')
            if loc_key.startswith('Game-GameData-Misc-GameVal-'):
                key = loc_key.removeprefix('Game-GameData-Misc-GameVal-')
            if loc_key.startswith('Game-Stat-'):
                key = 'Stat' + loc_key.removeprefix('Game-Stat-')
                if key.startswith('StatCrisis'):
                    loc_text = f'{{{{icon|{key}}}}} {loc_text}'
            if key:
                if key in overrides:
                    final_text = overrides[key]
                else:
                    final_text = self.formatter.convert_to_wikitext(loc_text).strip()
                if key in result:
                    print(f'Warning overriding misc data text for "{key}"(from {loc_key}). Old text was "{result[key]}". New text is "{final_text}"')
                result[key] = final_text
                if key.endswith('-Base') and key.removesuffix('-Base') not in result:
                    result[key.removesuffix('-Base')] = final_text

        return result

    @cached_property
    def needs(self) -> dict[str, Need]:
        return self.parse_nameable_entities_with_xmltodict('ANeedInfo', 'NeedInfo', default_entity_class=Need)

    @cached_property
    def sim_decks(self):
        return self.parse_decks_from_folder('text/simdecks', group_by_deck=True)

    @cached_property
    def event_cards(self) -> dict[str, dict[str, CardBaseClass]]:
        decks = {}
        for deck_name in self.sim_decks:
            tag = f'AddTo{deck_name.capitalize()}Deck'
            decks[deck_name] = {name: card for name, card in self.all_cards.items() if
                                card.tags.has(f'Universal{tag}') or card.tags.has(tag) or card.deck_name == deck_name}

        return decks

    @cached_property
    def innovation_cards(self) -> dict[str, CardBaseClass]:
        return {name: card for name, card in self.all_cards.items() if card.tags.has('UniversalAddToInnovationDeck') or card.tags.has('AddToInnovationDeck') or card.deck_name == 'INNOVATION'}

    @cached_property
    def chaos_cards(self) -> dict[str, CardBaseClass]:
        return {name: card for name, card in self.all_cards.items() if card.tags.has('UniversalAddToChaosDeck') or card.tags.has('AddToChaosDeck') or card.deck_name == 'CHAOS'}

    @cached_property
    def game_values(self) -> dict[str, GameValue]:
        return self.parse_nameable_entities_with_xmltodict('GameValue', 'GameValues', default_entity_class=GameValue, process_comments=True)

    @cached_property
    def startup_bonuses(self) -> dict[str, StartupBonus]:
        result = {}
        for entry in self.get_resource_xml('StartupBonuses'):
            for child_entry in entry:
                bonus = StartupBonus({'name': child_entry.text})
                result[bonus.name] = bonus
        return result

    @cached_property
    def nations(self) -> dict[str, Nation]:
        return self.parse_nameable_entities_with_xmltodict('APlayerSetupState', 'NationConfigs', default_entity_class=Nation)

    @cached_property
    def name_tables(self) -> dict[str, Nation]:
        return self.parse_nameable_entities_with_xmltodict('AEntityNameTableState', 'Names', default_entity_class=NameTable)

    @cached_property
    def factions(self) -> dict[str, Faction]:
        effect_payloads = []
        for card in self.all_cards.values():
            effect_payloads.extend(card.traverse_effects('CE_SetStringData', lambda effect: effect['Payload'] if effect['Payload'].startswith('FactionReward') else None))

        results = {}
        for payload in effect_payloads:
            reward_name, card_name = payload.removeprefix('FactionReward-').split(',')
            faction_name, tier = reward_name.split('-')
            tier = int(tier) + 1
            if faction_name in results:
                faction = results[faction_name]
            else:
                faction = Faction({'name': faction_name})
                results[faction_name] = faction

            faction_reward = self.all_cards[card_name]
            faction_reward.faction = results[faction_name]
            faction_reward.tier = tier
            faction_reward.display_name = f'{faction.display_name} faction reward {tier}'
            faction.rewards[tier] = faction_reward

        return results

    @cached_property
    def megaprojects(self) -> dict[str, MegaProject]:
        megaprojects = self.parse_nameable_entities_with_xmltodict('AMegaprojectInfo', 'Megaprojects', default_entity_class=MegaProject)
        for project in megaprojects.values():
            parsed_stages = []
            for stage_data in project.stages.find_all('Stage'):
                stage_data['project'] = project
                parsed_stages.append(self.create_entity(MegaProjectStage, MegaProjectStage._tag_for_name, stage_data))
            project.stages = parsed_stages
        return megaprojects

    @cached_property
    def megaproject_stages(self) -> dict[str, MegaProjectStage]:
        return {stage.name: stage for project in self.megaprojects.values() for stage in project.stages}

    def get_cards_which_use_tag(self, tag):
        if tag not in self.cards_which_use_tag:
            cards = []
            for card in self.all_cards.values():
                result = []
                if 'ACardChoice' in card.choices:
                    a = card.choices.find_all_recursively('ACardRequirement')
                    result.extend(a)
                if card.prereqs:
                    b = card.prereqs.find_all_recursively('Requirement')
                    result.extend(b)
                for requirement in result:
                    if requirement and requirement.get('ReqType') == 'CR_EntityTagCount' and requirement.get('Req', '').startswith(f'{tag},'):
                        cards.append((card, [pformat(requirement.dictionary)]))
                payloads = card.traverse_effects('CE_PlayCard',
                                                 lambda effect: effect.get('Payload') if re.fullmatch(f'ENTTAG,\+?{tag}', effect.get('Target', '')) else None)
                if payloads:
                    cards.append((card, payloads))
            self.cards_which_use_tag[tag] = cards
        return self.cards_which_use_tag[tag]

    @staticmethod
    def _is_standard_resource_layer(layer: Tree):
        for tag in layer.find_all_recursively('Tag'):
            if tag == 'StandardResource':
                return True
        return False

    @cached_property
    def terrain_tags_to_bonus_tiles(self) -> dict[str, list[MapTile]]:
        result = {}
        for layer in Tree(xmltodict.parse(self.unity_reader.text_asset_resources['text/biomes']['StandardBiome'],
                                          postprocessor=self.xml_postprocessor)).find_all_recursively('Layer'):
            if self._is_standard_resource_layer(layer):
                for _, entry in layer['Entries']:
                    if entry['EntryType'] != 'BDE_TILE':
                        continue
                    map_tile = self.map_tiles[entry['Data']]
                    for _, tag in entry['RequiredTerrainTags']:
                        tag = tag.removeprefix('+')
                        if tag not in result:
                            result[tag] = []
                        result[tag].append(map_tile)
        return result

    @cached_property
    def dlcs(self) -> dict[str, DLC]:
        """find DLCs by localisation, because their other configuration is hardcoded

        the returned dict has each DLC twice, once with the LCC_ prefix and once without it, but they both use the same DLC object
        which does not use the prefix in its name """
        dlcs = {}
        for loc_key, loc_text in self.unity_reader.localizations.items():
            if loc_key.startswith('UI-ContentCodeDisplayName-'):
                name = loc_key.removeprefix('UI-ContentCodeDisplayName-').removeprefix('LCC_')
                display_name = self.formatter.strip_formatting(loc_text)
                dlc = DLC({'name': name, 'display_name': display_name})
                dlcs[name] = dlc
                dlcs[f'LCC_{name}'] = dlc
        return dlcs

    @cached_property
    def data_link_actions(self) -> dict[str, DataLinkAction]:
        actions = {}
        for entity in self.all_entities.values():
            if hasattr(entity, 'tags') and entity.tags.has('DataLinkAction'):
                target_value, link_card_name = entity.tags.get('DataLinkAction').split(',')
                target, value_type = target_value.split(':')
                if link_card_name in actions:
                    action = actions[link_card_name]
                    assert action.target == target
                    assert action.value_type == value_type
                    action.entities.append(entity)
                else:
                    card = self.all_cards[link_card_name]
                    actions[link_card_name] = DataLinkAction(link_card_name, card, [entity], target, value_type)

        return actions

    @cached_property
    def played_cards_from_tech(self) -> dict[str, CardUsageWithTarget]:
        actions = {}
        for card in self.technologies.values():
            for played_card, target in card.traverse_effects('CE_PlayCard', lambda effect: (effect.get('Payload'), effect.get('Target'))):
                if played_card in actions:
                    action = actions[played_card]
                    assert action.target == target
                    action.entities.append(card)
                else:
                    actions[played_card] = CardUsageWithTarget(played_card, self.all_cards[played_card], [card], target)

        return actions

    @cached_property
    def action_cards(self) -> dict[str, CardUsage]:
        actions = {}
        for entity in self.all_entities.values():
            if hasattr(entity, 'actionCards') and entity.actionCards:
                for card_name in entity.actionCards.find_all('Card'):
                    if card_name in actions:
                        action = actions[card_name]
                        action.entities.append(entity)
                    else:
                        card = self.all_cards[card_name]
                        actions[card_name] = CardUsage(card_name, card, [entity])
        return actions


class LazyObject:

    _wrapped = None
    _is_init = False

    def __init__(self, all_parsed_entities, name):
        # Assign using __dict__ to avoid the setattr method.
        self.__dict__['_all_parsed_entities'] = all_parsed_entities
        self.__dict__['_name'] = name
        self.__dict__['_delayed_assignments'] = {}

    def _setup(self):
        self._wrapped = self._all_parsed_entities[self._name]
        for name, value in self._delayed_assignments.items():
            setattr(self._wrapped, name, value)
        self._is_init = True

    def _can_be_setup(self):
        return self._name in self._all_parsed_entities

    def new_method_proxy(func):
        """
        Util function to help us route functions
        to the nested object.
        """
        def inner(self, *args):
            if not self._is_init:
                self._setup()
            return func(self._wrapped, *args)
        return inner

    def __setattr__(self, name, value):
        # These are special names that are on the LazyObject.
        # every other attribute should be on the wrapped object.
        if name in {"_is_init", "_wrapped"}:
            self.__dict__[name] = value
        elif not self._is_init and not self._can_be_setup():
            self._delayed_assignments[name] = value
        else:
            if not self._is_init:
                self._setup()
            setattr(self._wrapped, name, value)

    def __delattr__(self, name):
        if name == "_wrapped":
            raise TypeError("can't delete _wrapped.")
        if not self._is_init:
                self._setup()
        delattr(self._wrapped, name)

    __getattr__ = new_method_proxy(getattr)
    __bytes__ = new_method_proxy(bytes)
    __str__ = new_method_proxy(str)
    __bool__ = new_method_proxy(bool)
    __dir__ = new_method_proxy(dir)
    __hash__ = new_method_proxy(hash)
    __class__ = property(new_method_proxy(operator.attrgetter("__class__")))
    __eq__ = new_method_proxy(operator.eq)
    __lt__ = new_method_proxy(operator.lt)
    __gt__ = new_method_proxy(operator.gt)
    __ne__ = new_method_proxy(operator.ne)
    __getitem__ = new_method_proxy(operator.getitem)
    __setitem__ = new_method_proxy(operator.setitem)
    __delitem__ = new_method_proxy(operator.delitem)
    __iter__ = new_method_proxy(iter)
    __len__ = new_method_proxy(len)
    __contains__ = new_method_proxy(operator.contains)
