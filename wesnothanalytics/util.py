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
    
    bucket = Bucket(re.sub(r'\s*Ladder_[0-9]+(_[0-9]+)?',"",content.replace("\t","")).replace("Dark Sorceress","Dark Sorcerer"))

    pattern = re.compile(r'^\d+\.\d+\.\d+$')
    assert bool(pattern.match(bucket.version))

    if bucket["replay_start"] and bucket["replay"]:
        return bucket
    else:
        raise Exception("This must be a valid Wesnoth replay.")