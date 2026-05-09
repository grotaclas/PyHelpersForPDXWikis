**PyHelpersForPDXWikis** is a tool to parse the game files of some paradox games and generate tables and other information from
them and add it to the wiki. The current version generates the output as txt files, but future versions will allow
automatically uploading to the wiki. The following games are supported:

* Age of Wonders 4(only rudimentary support for json data files)
* Cities: Skylines II
* Europa Universalis V
* Millennia
* Victoria 3

# Code structure

## Common
The module `common` contains code which is shared by multiple or all games

The main components are:

#### ParadoxParser (common/paradox_parser.py)
parses paradox game scripts with the help of [rakaly cli](https://github.com/rakaly/cli) and turns them into
Tree objects(a wrapper around dict) and generic python types like list, str, int, float and bool

#### JominiParser (common/jomini_parser.py)
higher level parsing code which is shared between eu5 and vic3, most notably the functions
`localize`, `parse_nameable_entities` and `parse_advanced_entities`

#### paradox_lib (common/paradox_lib.py)

Classes which are used by many of the games.

##### Game

The main purpose of this game object is to hold a reference to the parser and other game related information, to allow some code to work for multiple games. It can be accessed via the global variable (e.g. vic3game)

This class has basic information about the game like its name, short name, game_path (the folder where the game is installed), `major_version` (e.g. 1.2), `version` (e.g. 1.2.1), `full_version` (e.g. 1.2.1-84ef593274f81edadcf87e0acd86da157ea11a47 the last part is the code revision or whatever else the gamefiles offer to identify versions even if the version number does not change), `cachepath` (the folder where PyHelpersForPDXWikis caches data it has read from the files (for functions annotated with `@disk_cache`)).

##### PdxColor

Reads the various ways how the games define colors and has the function `get_css_color_string()` and its cached property counterpart `css_color_string` which converts the color into a format which can be used in wikitext.

##### ParsableObject

Parent class of most of the classes for game entities. The keyword arguments in the constructor set the attributes of the object. Default values and types... (TODO explain more)

##### NameableEntity

`ParsableObject` with a name and display_name. Has ordering functions, hash and string representations which use the name/display_name 

##### AttributeEntity

Counterpart to NameableEntity which is used by Millennia and Cities Skylines II

##### IconMixin

Icon handling. Many functions for wiki icon names and links. Basically used by all entity classes which have icons

## Game specific
The code for each game is in a submodule named after the game. Usually these folders have

#### game.py

Contains a class for the game which is a subclass of `common.paradox_lib.Game`.

Each of the `game.py` files has a global variable which holds a reference to the object for their game. This can be used to access the parser from anywhere and most importantly it makes sure that there is only one instance of the parser, so that the parsing is not done multiple times

#### ...lib.py

Contains classes for the game entities (e.g. Country, Technology, Building)


#### parser.py


TODO: explain

## Vic3

#### vic3/vic3lib.py
contains classes for many of the vic3 game entities like Country, State, Technology, Building, ProductionMethod

#### Vic3Parser (vic3/parser.py)
uses ParadoxParser to read the game files and creates vic3lib objects. These objects can be accessed as properties
of the Vic3Parser object. The parser should not be accessed via vic3game.parser so that only one instance exists

#### Vic3FileGenerator (vic3/vic3_file_generator.py)
base class for the wiki text generators. See [Usage](#Usage) for a list of them

#### Victoria3 (vic3/game.py)


## aow4

Age of Wonders 4 has the same files as vic3 in its aow4 folder. Instead of rakaly, it reads json files with a data dump.

## eu5

Europa Universalis V follows the same structure as vic3

## cs2

Cities Skylines II files are parsed with the help of UnityPy

## millennia

Millennia follows the same structure as vic3

# Installation

Clone this repository or download it as a zip from https://github.com/grotaclas/PyHelpersForPDXWikis. Then fulfill
the [dependencies](#Dependencies) and [configure](#Configuration) it.

# Dependencies

This project needs python version 3.10 or above (older versions might work as well). requirements.txt contains the
python modules which are needed for most games. For cs2/millennia requirements-cs2.txt/requirements-millennia.txt 
have to be used instead. requirements-flag.txt is used for (experimental) flag_helper scripts which use 
the game to screenshot flags.

They can be installed with pip (preferably in a [venv](https://docs.python.org/3/tutorial/venv.html)):

    python3 -m pip install -r requirements.txt



To parse the vic3 and eu5 game files, the [rakaly cli](https://github.com/rakaly/cli) is used. It must be either installed somewhere
in the PATH or the location has to be configured in the settings.

For aow4, an export of the game data in json format is needed. The Age of Wonders 4 Database hosts a modified
version of the files on [their github](https://github.com/MinionsArt/aow4db/tree/main/Data) 

For cs2 and millennia, the data is read from the unity assets with the help of UnityPy

The pyradox folder contains a modified version of the wiki table generator
from [pyradox](https://github.com/ajul/pyradox). This is a temporary solution and will be replaced by code which is
better suited to generate the needed output without too much boilerplate.

# Configuration

Copy localsettings.py.example to localsettings.py and configure the location of the game installation(s) and rakaly for
your system. The example file describes the options. For eu5, the language can also be changed there

# Usage

The wiki text can be generated as .txt files by calling one of the scripts from the game folders. They either generate
all files which they support or a specific function can be specified as command line argument by removing
the `generate_` prefix from the method name. For example `python3 vic3/generate_tables.py decree_table`. The following
scripts exist currently:

#### vic3/generate_tables.py
generates many tables

#### vic3/generate_articles.py
generates the [Vickypedia](https://vic3.paradoxwikis.com/Vickypedia)

#### vic3/generate_building_tables.py
generates tables of buildings and production methods

#### aow4/generate_tables.py
currently the only script for Age of Wonders 4. Generates several tables

#### eu5/generate_lua_data.py

generates most lua modules for the eu5 wiki

#### eu5/generate_tables.py

generates most tables for the eu5 wiki

#### eu5/helper.py

can generate new classes, parsers and table generators. kind of a mess. needs editing the code to use it

#### eu5/script_docs_helper.py

updates `eu5/script_docs_data.py`. Should be done after each major update to help with localising triggers and effects which is partially based on it

#### millennia/generate_tables.py
generates most of the tables on the wiki

#### millennia/generate_templates.py
experimental code to generate tooltip templates

#### millennia/dump_xml.py
exports the XML files from the unity assets. Expects the output folder as the only parameter. The files will be written in subfolders according to the addressables of the unity assets

# Sample code
    from vic3.game import vic3game

    for tag, country in vic3game.parser.countries.items():
        if country.capital_state:
            capital_name = country.capital_state.display_name
        else:
            capital_name = 'No capital'
        print(tag, country.display_name, capital_name)
