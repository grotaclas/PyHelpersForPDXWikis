import re

from common.paradox_parser import Tree
from eu5.event_target import EventTarget
from eu5.game import eu5game
from eu5.script_docs_data import triggers_from_script_docs


class Trigger(Tree):
    triggers_from_script_docs = triggers_from_script_docs

    scripted_triggers: set[str] = None
    scripted_lists_triggers: set[str] = None
    all_triggers: set[str] = None

    # this comes from the json conversion in rakaly
    comparison_operators = {'LESS_THAN', 'LESS_THAN_EQUAL', 'GREATER_THAN', 'GREATER_THAN_EQUAL', 'EXACT', 'EQUAL', 'NOT_EQUAL', 'EXISTS'}

    @classmethod
    def get_all_triggers(cls) -> set[str]:
        """includes scripted triggers and comparsion operators"""
        if cls.scripted_triggers is None or cls.all_triggers is None:
            cls.scripted_triggers = set(eu5game.parser.scripted_triggers.keys())
            cls.scripted_lists_triggers = {
                trigger
                for scripted_list in eu5game.parser.scripted_lists.values()
                for trigger in scripted_list.triggers
            }
            cls.all_triggers = cls.scripted_triggers | cls.scripted_lists_triggers | cls.triggers_from_script_docs | cls.comparison_operators | {op.lower() for op in cls.comparison_operators}
        return cls.all_triggers

    @classmethod
    def _get_script_keys_without_event_targets(cls, script:Tree) -> set[str]:
        script_keys = set()
        for key, value in script:
            key_without_parameters = re.split('[(:]', key.lower())[0]
            if key_without_parameters not in cls.get_all_triggers() and EventTarget.could_be_event_target(key):
                if isinstance(value, Tree):
                    script_keys.update(cls._get_script_keys_without_event_targets(value))
            elif '.' in key and key.split('.')[-1] in cls.get_all_triggers():
                script_keys.add(key.split('.')[-1])
            else:
                script_keys.add(key_without_parameters)
        return script_keys

    @classmethod
    def could_be_trigger(cls, script: Tree) -> bool:
        script_keys = cls._get_script_keys_without_event_targets(script)
        triggers_in_script_keys = script_keys & cls.get_all_triggers()
        return len(triggers_in_script_keys) == len(script_keys)
