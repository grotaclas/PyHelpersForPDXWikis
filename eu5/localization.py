from pathlib import Path

from common.localization import JominiLocalizer


class Eu5Localizer(JominiLocalizer):
    # allows the overriding of localization strings
    localizationOverrides = {
        # the default is "Trade Embark/Disembark Cost" which is problematic for redirects and filenames, because of the slash
        'MODIFIER_TYPE_NAME_local_trade_embark_disembark_cost_modifier': 'Trade Embark-Disembark Cost',
        'BGP': 'Burgundy (BGP)',
        'MAM': 'Egypt (MAM)'
    }

    def __init__(self, game_installation: Path, language: str = 'english'):
        localization_files = list((game_installation / 'game' / 'main_menu' / 'localization' / language).glob(
            f'**/*_l_{language}.yml'))
        dlc_locs = list((game_installation / 'game' / 'dlc').glob(f'*/main_menu/localization/dlc/{language}/**/*_l_{language}.yml'))
        localization_files.extend(dlc_locs)

        self.localization_folder_iterator = iter(localization_files)
