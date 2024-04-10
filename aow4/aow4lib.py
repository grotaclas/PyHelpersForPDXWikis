from functools import cached_property
from typing import Optional

from aow4.game import aow4game
from common.paradox_lib import NameableEntity, IconEntity


class Ability(IconEntity):
    description: str = ''

    # TODO: remove this after all abilities have been added to the wiki
    abilities_in_template = [
        '10_hp', '12_hp', '4_hp', '6_hp', '8_hp', 'all-round_awareness', 'amphibious', 'animal',
        'animate_flora_horned_god', 'archons_smite_blessed_soul', 'arctic_walk', 'astral_blessing_astral_keeper',
        'astral_membrane', 'astral_pull_astral_siphoner', 'astral_pursuit_flow_serpent', 'astral_refuge',
        'astral_torrent', 'attuned_cast_spellbreaker', 'attunement_star_blades', 'awaken_sun_priest',
        'banner_smite_bannerman', 'barbed_webs_vampire_spider_matriarch', 'battle_mage_unit',
        'beacon_of_hope_blessed_soul', 'behind_you!_gremlin', 'berserk', 'berserkers_rage', 'bless_chaplain',
        'blight_immunity', 'blight_resistance_2', 'blight_resistance_4', 'blight_resistance_6', 'blight_resistance_8',
        'blight_weakness_2', 'blight_weakness_4', 'blinding_gale_autumn_fairy', 'blooming_life_summer_fairy',
        'boat_ballista_ballista_warship', 'bolstering', 'bolster_undead_necrotic_spire', 'bolt_of_judgment_inquisitor',
        'bone-shattering_howl_karagh', 'budding_strength_spring_fairy', 'bulwark_standard_bannerman',
        'butchers_cut_butcher_ogre', 'caretaker', 'carrion_feed_carrion_bird', 'caustic_eruption_caustic_worm',
        'cavalry', 'celestial', 'chaos_brand_balor', 'chaotic_rebuke', 'charge_resistance', 'charge_strike_bone_golem',
        'charge_strike_dark_warrior', 'charge_strike_gargoyle', 'charge_strike_goretusk_piglet',
        'charge_strike_lesser_storm_spirit', 'charge_strike_nightmare', 'charge_strike_phoenix',
        'charge_strike_ram_warship', 'charge_strike_shock_unit', 'charge_strike_unicorn', 'charge_strike_war_hound',
        'charge_strike_young_caustic_worm', 'civilian', 'conjure_animal_wildspeaker', 'conjure_runestone_fire_giant',
        'consume_chaos_chaos_eater', 'consume_corpse_bone_golem', 'convert_lightbringer',
        'crushing_anguish_corrupt_soul', 'cull_the_weak', 'cycles_end_druid_of_the_cycle', 'dark_rites',
        'dark_stalwart', 'dark_surge_dark_knight', 'death_explosion', 'defense_mode', 'defense_mode_protective_wall',
        'defense_mode_shield_wall', 'defense_mode_turn_to_stone', 'defense_mode_warding', 'demolisher',
        'demoralizing_heavy_charge_tyrant_knight', 'desolate_walk', 'detonate_and_devastate_devastator_sphere',
        'devourer_of_spells', 'devour_mind_mage_bane', 'disassemble', 'displacement',
        'divine_beacons_grace_divine_beacon', 'divine_vengeance_shrine_of_smiting', 'dormant_guardian',
        'dormant_radiant_light', 'dormant_seeking_missiles', 'dormant_shield_of_light', 'draconic_rage', 'dragon',
        'drenching_phase_tide_spirit', 'drink!_brewer_ogre', 'earthquake_smash_rock_giant',
        'earth_tremor_earthshatter_engine', 'electrifying_arc_evoker', 'elemental', 'elite_medal_damage',
        'elite_medal_defense', 'elite_medal_evasion', 'elite_medal_mythic', 'elite_medal_resistance', 'elusive',
        'embolden_allies_eagle_rider', 'enfeebling_howl_white_wolf', 'enhancing_symbiosis_nimu', 'entangle_living_vine',
        'entwine_entwined_scourge', 'ethereal', 'evolve', 'expedited_movement_(underground)',
        'explosive_phase_magma_spirit', 'exposing_light_awakener', 'faithful', 'farsight', 'feudal_training', 'fey',
        'fiend', 'fierce', 'fiery_rebirth', 'fiery_wake', 'fighter_unit', 'finger_of_death_reaper', 'fire_aura',
        'fire_breath_fire_dragon', 'fire_immunity', 'fire_resistance_10', 'fire_resistance_2', 'fire_resistance_4',
        'fire_resistance_6', 'fire_weakness_2', 'fire_weakness_3', 'fire_weakness_4', 'fire_weakness_6', 'first_strike',
        'flamestrike_pyromancer', 'floating', 'flying', 'forbidden_tome_lost_wizard', 'forest_camouflage',
        'freezing_blast_white_witch', 'freezing_burst_lesser_snow_spirit', 'freezing_burst_snow_spirit',
        'freezing_phase_snow_spirit', 'frenzy', 'frost_aura', 'frost_breath_frost_dragon', 'frost_resistance_10',
        'frost_resistance_2', 'frost_resistance_3', 'frost_resistance_4', 'frost_resistance_6', 'frost_weakness_2',
        'frost_weakness_4', 'frost_weakness_6', 'frozen_web_ice_spider', 'frozen_web_ice_spider_matriarch',
        'gilded_strike_golden_golem', 'golden_curse', 'golden_retaliation', 'grant_defense_steelshaper',
        'great_bolt_bolt_repeater', 'great_bolt_bolt_repeater_tower', 'greater_corpse_consumption_reaper',
        'greater_farsight', 'greater_phase_lost_wizard', 'healing_prayer_chaplain', 'healing_roots',
        'healing_sap_entwined_protector', 'heat_of_the_revel_skald', 'heavy_charge_strike_berserker',
        'heavy_charge_strike_caustic_worm', 'heavy_charge_strike_dark_knight', 'heavy_charge_strike_earth_titan',
        'heavy_charge_strike_fire_giant', 'heavy_charge_strike_ghost_ship', 'heavy_charge_strike_goretusk_matriarch',
        'heavy_charge_strike_karagh', 'heavy_charge_strike_knight', 'heavy_charge_strike_phase_beast',
        'heavy_charge_strike_rock_giant', 'heavy_charge_strike_storm_giant', 'heavy_charge_strike_storm_spirit',
        'heavy_charge_strike_warbreed', 'heavy_shield', 'hindering_blizzard_winter_fairy', 'hopelessness',
        'hyper-awareness', 'ice_veil', 'immobilized', 'immobilizing_phase_stone_spirit', 'incinerate_magma_spirit',
        'infiltrate', 'inspiring_defense_bastion', 'inspiring_killer', 'inspiring_presence', 'intimidating_aura',
        'invigorate_war_shaman', 'jump_hunter_spider', 'jump_hunter_spider_matriarch', 'land_movement', 'large_target',
        'launch_ballista', 'launch_ballista_tower', 'launch_catapult_tower', 'launch_onager', 'launch_trebuchet',
        'legend_medal_brawler', 'legend_medal_critical', 'legend_medal_eagle_eye', 'legend_medal_evoker',
        'legend_medal_exalted_defense', 'legend_medal_exalted_resistance', 'legend_medal_killing_momentum',
        'legend_medal_retaliation', 'legend_medal_sprint', 'life_from_death', 'lightning_resistance_2',
        'lightning_resistance_4', 'lightning_resistance_6', 'lightning_strike_storm_giant', 'lightning_weakness_2',
        'lightning_weakness_4', 'lightning_weakness_6', 'low_maintenance', 'magic_blast_amplification_pylon',
        'magic_blast_astral_keeper', 'magic_blast_chaplain', 'magic_blast_deep-sea_nimu',
        'magic_blast_druid_of_the_cycle', 'magic_blast_fire_runestone', 'magic_blast_necromancer', 'magic_blast_nymph',
        'magic_blast_shrine_of_smiting', 'magic_blast_soother', 'magic_blast_spring_fairy', 'magic_blast_steelshaper',
        'magic_blast_summer_fairy', 'magic_blast_sun_priest', 'magic_blast_war_shaman', 'magic_blast_wildspeaker',
        'magic_bolts_arcanist', 'magic_bolts_astral_wisp', 'magic_bolts_autumn_fairy', 'magic_bolts_awakener',
        'magic_bolts_banshee', 'magic_bolts_chaos_eater', 'magic_bolts_elya', 'magic_bolts_entwined_scourge',
        'magic_bolts_evoker', 'magic_bolts_lesser_magma_spirit', 'magic_bolts_lightbringer', 'magic_bolts_lost_wizard',
        'magic_bolts_magma_spirit', 'magic_bolts_mystic_projection', 'magic_bolts_pyromancer',
        'magic_bolts_spellbreaker', 'magic_bolts_swamp_troll', 'magic_bolts_thunderbird', 'magic_bolts_transmuter',
        'magic_bolts_warlock', 'magic_bolts_watcher', 'magic_bolts_white_witch', 'magic_bolts_winter_fairy',
        'magic_origin', 'maternal_rage', 'melee_mage', 'melee_single_strike_astral_siphoner', 'melee_strike_',
        'melee_strike_anvil_guard', 'melee_strike_arcane_guard', 'melee_strike_astral_serpent', 'melee_strike_balor',
        'melee_strike_bastion', 'melee_strike_blessed_soul', 'melee_strike_bone_dragon', 'melee_strike_bone_wyvern',
        'melee_strike_brewer_ogre', 'melee_strike_butcher_ogre', 'melee_strike_carrion_bird',
        'melee_strike_copper_golem', 'melee_strike_corrupt_soul', 'melee_strike_dawn_defender',
        'melee_strike_daylight_spear', 'melee_strike_defender', 'melee_strike_dire_penguin',
        'melee_strike_dread_spider_hatchling', 'melee_strike_dread_spider_matriarch', 'melee_strike_eagle_rider',
        'melee_strike_entwined_protector', 'melee_strike_entwined_thrall', 'melee_strike_fire_dragon',
        'melee_strike_fire_wyvern', 'melee_strike_floral_stinger', 'melee_strike_flow_serpent',
        'melee_strike_frost_dragon', 'melee_strike_frost_wyvern', 'melee_strike_gremlin', 'melee_strike_grimbeak_crow',
        'melee_strike_halberdier', 'melee_strike_hunter_spider', 'melee_strike_hunter_spider_matriarch',
        'melee_strike_ice_spider', 'melee_strike_ice_spider_matriarch', 'melee_strike_inferno_hound',
        'melee_strike_inferno_puppy', 'melee_strike_inquisitor', 'melee_strike_iron_golem',
        'melee_strike_iron_golem_assistant', 'melee_strike_kraken', 'melee_strike_kraken_spawn',
        'melee_strike_lesser_snow_spirit', 'melee_strike_lesser_stone_spirit', 'melee_strike_lesser_tide_spirit',
        'melee_strike_mage_bane', 'melee_strike_magma_spirit', 'melee_strike_mirror_mimic', 'melee_strike_night_guard',
        'melee_strike_nimu', 'melee_strike_peasant_pikeman', 'melee_strike_phantasm_warrior',
        'melee_strike_plague_serpent', 'melee_strike_polearm_unit', 'melee_strike_reaper', 'melee_strike_river_troll',
        'melee_strike_shield_unit', 'melee_strike_skeleton', 'melee_strike_skirmisher_unit', 'melee_strike_snow_spirit',
        'melee_strike_spellshield', 'melee_strike_spirit_hawk', 'melee_strike_spirit_wolf', 'melee_strike_stone_spirit',
        'melee_strike_stormscale_serpent', 'melee_strike_sunderer', 'melee_strike_tide_spirit', 'melee_strike_townsman',
        'melee_strike_vampire_spider_hatchling', 'melee_strike_vampire_spider_matriarch', 'melee_strike_warg',
        'melee_strike_warrior', 'melee_strike_white_wolf', 'melee_strike_wind_rager', 'melee_strike_zealot',
        'melee_strike_zombie', 'mending_awakening_sun_priest', 'mimic_mirror_mimic', 'mind_strike_living_fog',
        'mythic_unit', 'natural_regeneration', 'naval_unit', 'nimu_soothing_deep-sea_nimu', 'outpost_builder',
        'overdraw_crossbow_arbalest', 'overheat_phoenix', 'pack_hunter', 'pass_through', 'petrify_transmuter',
        'phase_banshee', 'phase_phase_beast', 'phase_unicorn', 'plague_spores_swamp_troll', 'plant',
        'poison_breath_bone_dragon', 'poison_needle_entwined_thrall', 'poisonous_spores_floral_stinger', 'polearm_unit',
        'polearm_weapon', 'power_cleave_warbreed', 'primal_strike', 'protective_symbiosis_deep-sea_nimu',
        'provide_sanctuary_healing_spire', 'psychic_gaze_watcher', 'pull_of_the_deep_kraken', 'quake_stone_spirit',
        'quill_hide', 'quillshot_razorback', 'raise_undead_necromancer', 'ranged_unit', 'razor_net_river_troll',
        'reclaiming_bolt_horned_god', 'restart_the_cycle_druid_of_the_cycle', 'revitalize_nymph', 'rock_camouflage',
        'rune_of_retaliation', 'sap_strength_entwined_scourge', 'scout_unit', 'scrying_eye', 'seduce_nymph',
        'seismic_slam_earth_titan', 'shadow', 'shattering_refuge_astral_serpent', 'shepherd_of_the_wilds',
        'shield_bash_warrior', 'shield_defense', 'shield_unit', 'shocking_phase_storm_spirit', 'shock_unit',
        'shoot_bow_archer', 'shoot_bow_dusk_hunter', 'shoot_bow_fury', 'shoot_bow_glade_runner',
        'shoot_bow_lightseeker', 'shoot_bow_outrider', 'shoot_bow_pathfinder', 'shoot_bow_pursuer', 'shoot_bow_scout',
        'shoot_bow_scout_unit', 'shoot_bow_zephyr_archer', 'shoot_crossbow_arbalest', 'shoot_crossbow_houndmaster',
        'shoot_crossbow_pioneer', 'siege_breaker', 'siegecraft', 'skirmisher_unit', 'slippery', 'slowed',
        'song_of_carnage_skald', 'song_of_revelry_skald', 'soothing_breeze_soother', 'soothing_standard_bannerman',
        'spawn_hatchling_dread_spider_matriarch', 'spawn_hatchling_vampire_spider_matriarch', 'spell_amplification',
        'spell_channeling', 'spider', 'spirit_beacon', 'spirit_resistance_2', 'spirit_resistance_4',
        'spirit_weakness_2', 'spirit_weakness_4', 'spirit_weakness_6', 'stand_together', 'star_purge_spellbreaker',
        'statically_charged', 'status_effect_immunity', 'status_effect_immunity_morale',
        'strengthen_undead_necromancer', 'strength_from_steel_steelshaper', 'strike_gold_golden_golem',
        'stunning_flash_spellshield', 'summon_ghost_ghost_ship', 'sundering_curse_warlock', 'sunder_the_earth_balor',
        'support_unit', 'swamp_camouflage', 'swift', 'tail_swipe_bone_dragon', 'tail_swipe_fire_dragon',
        'tail_swipe_frost_dragon', 'taunt_anvil_guard', 'tempestuous_smash_storm_giant', 'tentacle_vortex_kraken',
        'terrifying_aura', 'terrifying_gorging_karagh', 'throw_boulder_rock_giant', 'throw_sunderer',
        'thunderclap_thunderbird', 'tidal_wave_tide_spirit', 'tiny', 'totem_of_the_wild', 'tower',
        'trackers_mark_glade_runner', 'troll_natural_regeneration', 'truesight', 'twin_awakening_awakener', 'undead',
        'underground_camouflage', 'universal_camouflage', 'unleash_the_beast_wildspeaker', 'unleash_the_hounds',
        'unstoppable_juggernaut', 'vengeful_flames', 'violent_gorging_goretusk_matriarch', 'volcanic_smash_fire_giant',
        'wail_of_the_banshee_banshee', 'wail_of_the_lost_ghost_ship', 'watchful', 'water_camouflage', 'water_movement',
        'web_dread_spider_matriarch', 'web_hunter_spider', 'web_hunter_spider_matriarch', 'whirlwind_wind_rager',
        'wild_eruption_horned_god', 'wind_barrier', 'zeal', 'zephyr_shot_zephyr_archer', ]

    def get_wiki_link(self) -> str:
        if self.name in self.abilities_in_template:
            return f'{{{{Ability|Dotted|{self.name}}}}}'
        else:
            return f'[[List of abilities#{self.name}|{self.display_name}]]<!-- {{{{Ability|Dotted|{self.name}}}}} -->'


class HeroSkill(IconEntity):
    category_name: str = ''
    group_name: str = ''
    level_name: str = ''
    description: str = ''
    type: str = ''
    abilities: list[Ability] = []

    def get_wiki_icon(self, size: str = '24px') -> str:
        return self.get_wiki_file_tag(size)

    def to_camel_case(self, text):
        s = text.replace("-", " ").replace("_", " ")
        s = s.split()
        if len(text) == 0:
            return text
        return ''.join(i.capitalize() for i in s)

    def get_wiki_filename(self) -> str:
        if self.type == 'signature':
            return f'Hero signature skill {self.to_camel_case(self.display_name)}.png'
        else:
            return super().get_wiki_filename()

    def get_wiki_page_name(self) -> str:
        return 'Heroes'

    @cached_property
    def tome(self) -> Optional['Tome']:
        if self.name in aow4game.parser.hero_skills_to_tome:
            return aow4game.parser.hero_skills_to_tome[self.name]
        else:
            return None


class TomeSkill:
    slug: str
    display_name: str
    tier: int
    skill_type: str
    type_desc: str
    description: str

    def __init__(self, slug: str, display_name: str, tier: int, skill_type: str, type_desc: str, description: str):
        self.slug = slug
        self.display_name = display_name
        self.tier = tier
        self.skill_type = skill_type
        self.type_desc = type_desc
        self.description = description

    @cached_property
    def object(self):
        if self.skill_type == 'spell':
            if self.slug in aow4game.parser.spells:
                return aow4game.parser.spells[self.slug]
            else:
                for spell in aow4game.parser.spells.values():
                    if spell.display_name == self.slug:
                        return spell

        # nothing found. create dummy object
        skill_object = IconEntity(self.slug, self.display_name)
        skill_object.icon = ''
        skill_object.description = self.description
        return skill_object

    def get_wiki_link(self) -> str:
        if self.skill_type == 'spell':
            return self.object.get_wiki_link()
        else:
            return self.display_name

class Affinity(NameableEntity):
    pass


class Tome(IconEntity):
    affinity_value: int
    affinity_type_str: str
    gameplay_description: str
    hero_skills: list[HeroSkill] = []
    lore_author: str
    lore_description: str
    passives: list
    skills: list[TomeSkill] = []
    tier: int

    @cached_property
    def affinity(self) -> Affinity | None:
        if self.affinity_type_str:
            return aow4game.parser.affinities[self.affinity_type_str]
        else:
            return None

    def get_wiki_link_target(self) -> str:
        return self.display_name

    def get_wiki_icon(self, size: str = '24px') -> str:
        return self.get_wiki_file_tag(size)

    def get_wiki_filename_prefix(self) -> str:
        if self.icon.startswith('tome'):
            return 'Tome'
        else:
            return 'Culture tome'


class Spell(IconEntity):
    spell_type: str
    tome: Tome
    tier: int
    casting_cost: str
    operation_point_cost: int
    upkeep: str = ''
    tactical: bool
    description: str
    enchantment_requisites: list[str] = []
    summoned_units: list[str] = []

    def get_wiki_icon(self, size: str = '24px') -> str:
        return self.get_wiki_file_tag(size)

    def get_wiki_page_name(self) -> str:
        if self.tactical:
            return 'Tactical spells'
        else:
            return 'Strategic spells'
