# WESNOTHANALYTICS

_wesnothanalytics_ is a Python package that parses _Battle for Wesnoth_ replays to grab metadata.  It is used to create the dataset feeding into the _Wesnoth Analytics_ dashboard (https://lookerstudio.google.com/reporting/a0a2ddd6-7104-403c-8a54-4c0d0ddcc551).

## Table of Contents

- [Installation and Usage](#installation)
- [Limitations](#limitations)
- [Bugs](#bugs)



## Installation and Usage

The package is publicly available and can be installed like any package (https://pypi.org/project/wesnothanalytics/).

```bash
pip install wesnothanalytics
``` 

Using the package is very easy, a single function will convert the replay into a dictionary of metadata.


```python 

import wesnothanalytics as wa

with open("replay.txt", "r", encoding="utf-8") as f:
    replay_data = f.read()

data = wa.parse_replay(replay_data)
``` 

The resultant dictionary contains data in the form of the following keys:

1. <b>meta:</b> The version and map of the game, the name of the players, the factions they played and the leaders they controlled.
2. <b>turns:</b> The turn summary for each player (this seems to have been removed from recent replays).
3. <b>actions:</b> A list of all actions taken by each unit per turn.  If a unit was inactive, they are still included.
4. <b>flags:</b> A list of all flags that check to see if data makes sense within the replay.  Helpful for debugging and performing QA.


## Limitations

There are a lot of potential Wesnoth replay files.  To simplify the parsing, there are a few assumptions that have been made:

1. All players are controlled by humans
2. Factions and units are unmodified from the base game (dunefolk and Hornshark Island units are included)


Additionally, the replay files themselves often rely on the game engine to properly display actions.  This means the replay parser needs to simulate certain events that the game engine naturally handles.  These include:

- Combat only gives damage dealt, chance to hit, and if the opponent dies
    - The parser needs to predict who hits first, and how many hits each unit has
- Terrain/Villages are not explicitly mentioned inside movement/combat
    - Each replay file contains a terrain map but the parser currently does not have the ability to parse and connect coordinates to terrain/villages
    - This means that the number of villages a player controls and units healing from villages is not tracked
- Poison is not explicitly mentioned in attacks or when units take damage or are healed from poison
    - This is not currently handled by the replay parser as villages are not tracked





## Bugs

While performing QA on the parser, I found a couple bugs that caused a mismatch between the parser data and the replay.


1. <b>Unit Collisions:</b> There are instances with movement inside the replay that causes a unit to move to coordinates where another unit already occupies.  This results in a mismatch with the type of unit that actually occupies that space.  I may need to revisit the parser in the future to see if there's a reason this happens, although it is rare.

2. <b>False Resurrections:</b> There are instances where a combat involving a walking corpse is labelled as a death and a new walking corpse is created.  However, the replay indicates that the unit did not die and participates in future combats.  




