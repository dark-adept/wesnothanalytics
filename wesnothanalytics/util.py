import re
import os
import json

from .classes import Bucket



def load_config(fname):
    

    """
This function defines how the package reads in config files.

Input will the the filename of the config file inside the configs folder (include extensions, exclude the folder name as it's implied).
Output will be the contents of the file in dictionary format.


Parameters:
  * `fname` (string): The name of the config file, including extension and not including the file path (folder).
 
Returns:
  * None

Example:

load_config("dictionary.json")

 
    """   
    
    module_dir = os.path.dirname(__file__)
    config_path = os.path.join(module_dir,f'configs/{fname}')

    with open(config_path, 'r') as config_file:
        config_data = json.load(config_file)

        
    return config_data




def prep_replay(content):
    
    # Removing the tabs to simplify the replay
    text = content.replace("\t","")

    # In ladder games, the balance changes are often signified with the following extra characters added to the unit name
    # This detail is unnecessary for the replay parser
    text = re.sub(r'\s*Ladder_[0-9]+(_[0-9]+)?',"",text)
    text = re.sub(r'\s+(Re)?[bB]alanced(_[0-9]+)?',"",text)
    text = text.replace("L_","")

    # Dark Sorcerer changes name depending on gender, simplifying the naming to remove unnecessary distinction
    text = text.replace("Dark Sorceress","Dark Sorcerer")

    # Probably unnecessary
    text = text.strip()

    # The bucket object helps to index and browse the replay file
    bucket = Bucket(text)

    # The "version" of the replay must follow this simple format
    pattern = re.compile(r'^\d+\.\d+\.\d+$')
    assert bool(pattern.match(bucket.version))


    # All replays contain a "replay" section that details what happened during the game
    # Most have a "replay_start" that gives out important information about the players playing, but for the replays that don't this info is stored in the "scenario" section
    if (bucket["replay_start"] or bucket["scenario"]) and bucket["replay"]:
        return bucket
    else:
        raise Exception("This must be a valid Wesnoth replay.")