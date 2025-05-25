from common.paradox_lib import GameConcept


class Eu5GameConcept(GameConcept):
    family: str = ''
    alias: list['Eu5GameConcept']
    is_alias: bool = False

    def __init__(self, name: str, display_name: str, **kwargs):
        self.alias = []
        super().__init__(name, display_name, **kwargs)


