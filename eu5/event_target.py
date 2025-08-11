from common.paradox_parser import Tree
from eu5.script_docs_data import event_targets_from_script_docs


class EventTarget(Tree):
    event_targets_from_script_docs = event_targets_from_script_docs

    @classmethod
    def could_be_event_target(cls, key: str) -> bool:
        if '.' in key:
            for k2 in key.split('.'):
                if not cls.could_be_event_target(k2):
                    return False
            return True
        possible_event_target = key
        if ':' in possible_event_target:
            possible_event_target = possible_event_target.split(':')[0]
        if '(' in possible_event_target:
            possible_event_target = possible_event_target.split('(')[0]
        return possible_event_target.lower() in event_targets_from_script_docs
