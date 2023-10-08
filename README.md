**PyHelpersForPDXWikis** is a tool to parse the game files of Victoria 3 and generate tables and other information from
them and add it to the wiki. The current version generates the output as txt files, but future versions will allow
automatically uploading to the wiki. It can also parse json files with Age of Wonders 4 data.
Support for Europa Universalis IV is also planned.

The main components are:

#### ParadoxParser (common/paradox_parser.py)
parses paradox game scripts with the help of [rakaly cli](https://github.com/rakaly/cli) and turns them into
Tree objects(a wrapper around dict) and generic python types like list, str, int, float and bool

#### vic3/vic3lib.py
contains classes for many of the vic3 game entities like Country, State, Technology, Building, ProductionMethod

#### Vic3Parser (vic3/parser.py)
uses ParadoxParser to read the game files and creates vic3lib objects. These objects can be accessed as properties
of the Vic3Parser object. The parser should not be accessed via vic3game.parser so that only one instance exists

#### Vic3FileGenerator (vic3/vic3_file_generator.py)
base class for the wiki text generators. See [Usage](#Usage) for a list of them

#### Victoria3 (vic3/game.py)
the main purpose of this game object is to hold a reference to the Vic3Parser parser and other game related
information, to allow some code to work for multiple games. It can be accessed via the variable vic3game

#### aow4

Age of Wonders 4 has the same files as vic3 in its aow4 folder. Instead of rakaly, it reads json files with a data dump.

#### cs2

Cities Skylines II files are parsed with the help of UnityPy

# Installation

Clone this repository or download it as a zip from https://github.com/grotaclas/PyHelpersForPDXWikis. Then fulfill
the [dependencies](#Dependencies) and [configure](#Configuration) it.

# Dependencies

This project needs python version 3.10 or above (older versions might work as well). requirements.txt contains the
needed python modules. Currently, it is only colormath and UnityPy and leb128 for CS2, but more will follow when
automatic upload and wiki editing are added. They can be installed with pip (preferably in a [venv](https://docs.python.org/3/tutorial/venv.html)):

    python3 -m pip install -r requirements.txt

To parse the vic3 game files, the [rakaly cli](https://github.com/rakaly/cli) is used. It must be either installed somewhere
in the PATH or the location has to be configured in the settings.

For aow4, an export of the game data in json format is needed. The Age of Wonders 4 Database hosts a modified
version of the files on [their github](https://github.com/MinionsArt/aow4db/tree/main/Data) 

The pyradox folder contains a modified version of the wiki table generator
from [pyradox](https://github.com/ajul/pyradox). This is a temporary solution and will be replaced by code which is
better suited to generate the needed output without too much boilerplate.

# Configuration

Copy localsettings.py.example to localsettings.py and configure the location of the game installation(s) and rakaly for
your system. The example file describes the options.

# Usage

The wiki text can be generated as .txt files by calling one of the scripts from the vic3 folder. They either generate
all files which they support or a specific function can be specified as command line argument by removing
the `generate_` prefix from the method name. For example `python3 vic3/generate_tables.py decree_table`. The following
scripts exist currently:

#### generate_tables.py
generates many tables

#### generate_articles.py
generates the [Vickypedia](https://vic3.paradoxwikis.com/Vickypedia)

#### generate_building_tables.py
generates tables of buildings and production methods

#### aow4/generate_tables.py
currently the only script for Age of Wonders 4. Generates several tables

# Sample code
    from vic3.game import vic3game

    for tag, country in vic3game.parser.countries.items():
        print(tag, country.display_name, country.capital_state.display_name)
