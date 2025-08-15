import re

from common.paradox_parser import Tree
from eu5.event_target import EventTarget
from eu5.game import eu5game
from eu5.script_docs_data import effects_from_script_docs


class Effect(Tree):
    effects_from_script_docs = effects_from_script_docs

    scripted_effects: set[str] = None
    scripted_lists_effects: set[str] = None
    all_effects: set[str] = None

    @classmethod
    def get_all_effects(cls) -> set[str]:
        """includes scripted effects and lists"""
        if cls.scripted_effects is None or cls.all_effects is None:
            cls.scripted_effects = set(eu5game.parser.scripted_effects.keys())
            cls.scripted_lists_effects = {
                effect
                for scripted_list in eu5game.parser.scripted_lists.values()
                for effect in scripted_list.effects
            }
            cls.all_effects = cls.scripted_effects | cls.scripted_lists_effects | cls.effects_from_script_docs
        return cls.all_effects

    @classmethod
    def _get_script_keys_without_event_targets(cls, script:Tree) -> set[str]:
        script_keys = set()
        for key, value in script:
            key_without_parameters = re.split('[(:]', key.lower())[0]
            if key_without_parameters not in cls.get_all_effects() and EventTarget.could_be_event_target(key):
                if isinstance(value, Tree):
                    script_keys.update(cls._get_script_keys_without_event_targets(value))
            else:
                script_keys.add(key_without_parameters)
        return script_keys

    @classmethod
    def could_be_effect(cls, script: Tree) -> bool:
        script_keys = cls._get_script_keys_without_event_targets(script)
        effects_in_script_keys = script_keys & cls.get_all_effects()
        return len(effects_in_script_keys) == len(script_keys)

    @classmethod
    def is_iterator(cls, effect: str):
        return effect in cls.effects_from_script_docs and effect.split('_')[0] in ['every', 'ordered', 'random']