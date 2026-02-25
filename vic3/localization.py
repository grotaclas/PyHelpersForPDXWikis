from pathlib import Path

from common.localization import JominiLocalizer


class Vic3Localizer(JominiLocalizer):
    # allows the overriding of localization strings
    localizationOverrides = {'recognized': 'Recognized', # there doesn't seem to be a localization for this
                             'GNI': 'Guarani (GNI)',  # there are two tags called Guarani: GNI and GRI
                             }

    def __init__(self, game_path: Path):
        self.localization_folder_iterator = (game_path / 'game' / 'localization' / 'english').glob('**/*_l_english.yml')