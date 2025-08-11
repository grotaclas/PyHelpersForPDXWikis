from common.paradox_parser import Tree
from eu5.script_docs_data import effects_from_script_docs


class Effect(Tree):
    effects_from_script_docs = effects_from_script_docs

    @classmethod
    def could_be_effect(cls, script: Tree) -> bool:
        script_keys = set(script.keys())
        effects_in_script_keys = script_keys & cls.effects_from_script_docs
        return len(effects_in_script_keys) == len(script_keys)

    @classmethod
    def is_iterator(cls, effect: str):
        return effect in cls.effects_from_script_docs and effect.split('_')[0] in ['every', 'ordered', 'random']