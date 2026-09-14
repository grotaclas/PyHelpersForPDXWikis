import re
from functools import cached_property

from common.paradox_parser import Tree, TreeWithDuplicates, ParadoxParser
from eu5.event_target import EventTarget
from eu5.game import eu5game
from eu5.script_docs_data import triggers_from_script_docs

class Trigger:
    triggers_from_script_docs = triggers_from_script_docs

    _scripted_triggers: set[str] | None = None
    scripted_lists_triggers: set[str] | None = None
    all_triggers: set[str] | None = None

    # this comes from the json conversion in rakaly
    comparison_operators = {'LESS_THAN', 'LESS_THAN_EQUAL', 'GREATER_THAN', 'GREATER_THAN_EQUAL', 'EXACT', 'EQUAL', 'NOT_EQUAL', 'EXISTS'}

    @classmethod
    def get_all_triggers(cls) -> set[str]:
        """includes scripted triggers and comparison operators"""
        if cls.all_triggers is None:
            cls.scripted_lists_triggers = {
                trigger
                for scripted_list in eu5game.parser.scripted_lists.values()
                for trigger in scripted_list.triggers
            }
            cls.all_triggers = cls.get_scripted_triggers() | cls.scripted_lists_triggers | cls.triggers_from_script_docs | cls.comparison_operators | {op.lower() for op in cls.comparison_operators}
        return cls.all_triggers

    @classmethod
    def get_scripted_triggers(cls) -> set[str]:
        if cls._scripted_triggers is None:
            cls._scripted_triggers = set(eu5game.parser.scripted_triggers.keys())
        return cls._scripted_triggers

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


class TriggerBlock:

    triggers: Tree|TreeWithDuplicates

    def __init__(self, triggers: Tree|TreeWithDuplicates):
        self.triggers = triggers

    def __getattr__(self, item):
        """Pass through everything to the underlying Tree for compatibility

        @TODO: eventually self.triggers should use a different type and
         these accesses should be either implemented here or the calling code be moved here
        """
        return getattr(self.triggers, item)

    @cached_property
    def triggers_with_inlined_scripted_triggers(self) -> Tree:
        """Copy of this trigger with simple scripted triggers resolved
            scripted triggers with parameters are not supported(yet)
        """
        return self._copy_with_inlined_scripted_triggers(self.triggers)

    def _copy_with_inlined_scripted_triggers(self, tree: Tree, parent_key ='AND') -> Tree:
        ordered_pairs = []
        for key, value in tree.iterate_with_duplicates():
            if key in Trigger.get_scripted_triggers():
                contents_of_scripted_trigger = eu5game.parser.scripted_triggers[key].triggers_with_inlined_scripted_triggers
                if value is True:
                    if (
                            parent_key == 'AND' or
                            (parent_key == 'OR' and len(contents_of_scripted_trigger) < 2) or
                            parent_key in ['religion']  # implicit AND
                    ):
                        for k2, v2 in contents_of_scripted_trigger.iterate_with_duplicates():
                            ordered_pairs.append((k2, v2))
                        continue
                    elif parent_key == 'OR':
                        key = 'AND'
                        value = contents_of_scripted_trigger
                    else:
                        raise Exception(f'@TODO: implement parent "{parent_key}" in triggers_with_inlined_scripted_triggers')
                elif value is False:
                    if len(contents_of_scripted_trigger) > 1:
                        key = 'NAND'
                    else:
                        key = 'NOT'
                    value = contents_of_scripted_trigger
                else:
                    # @TODO implement inlining of complex scripted triggers
                    pass
            elif isinstance(value, Tree):
                value = self._copy_with_inlined_scripted_triggers(value, parent_key=key)

            ordered_pairs.append((key, value))
        return ParadoxParser.parse_ordered_pairs_into_tree(ordered_pairs)
