import json
import re

from collections import Counter

import pandas as pd


from .classes import Unit
from .util import load_config,prep_replay



unit_db = load_config("unit_db.json")



def parse_map(bucket):
    
    # A small hiccup in replay format causes the parser to revew "scenario" instead of "replay_parser" for a few versions
    if bucket["replay_start"]:
        content = bucket["replay_start"].head
    else:
        content = bucket["scenario"].head
    
    
    if scenario := re.search(r'\nname\s*=\s*_?"([^"]+)"', content):
    
        map_name = re.sub(r'[^a-zA-Z0-9\s]+', '', re.split(r'-|—', scenario.group(1).replace("_"," "))[-1].strip()).title()
    
        return map_name





def parse_era(bucket):

    # Defaulting to "default" rather than "unknown" for now
    default_answer = "default_era"

    
    # There are 2 main areas to find "era", and each have 2 potential names that they use
    # The most reliable is "multiplayer" where the era is a lot more explicit
    # Otherwise, the era can be parsed from the head of the bucket where "version" also sits
    
    if bucket["multiplayer"]:
    
        if re.search(r'mp_era="([^"]*)"', bucket["multiplayer"].head):
            result = re.search(r'mp_era="([^"]*)"', bucket["multiplayer"].head).group(1).lower()
    
        elif re.search(r'mp_era_name="([^"]*)"', bucket["multiplayer"].head):
            result = re.search(r'mp_era_name="([^"]*)"', bucket["multiplayer"].head).group(1).lower()
    
        else:
    
            return default_answer
            


    # If "multiplayer" does not exist in this version of the replay 
    else:   
        
        if re.search(r'era_define="([^"]*)"', bucket.head):
            result = re.search(r'era_define="([^"]*)"', bucket.head).group(1).lower()
    
        elif re.search(r'era_id="([^"]*)"', bucket.head) and not result:
            result = re.search(r'era_id="([^"]*)"', bucket.head).group(1).lower()
    
        else:
            return default_answer

        
    # Converting the text answers inside the replay to a standardized format
    # Currently converting "unknown" to "default_era" 
    if "ladder" in result:
        return "ladder_era"
    elif "default" in result:
        return "default_era"
    else:
        return default_answer



    



    




def parse_players(bucket):
    
    player_list = {}

    
    # Most of the time, side details is contained within "replay_start".  When there is no replay start, it is stored in "scenario"
    if bucket["replay_start"]:
        content = bucket["replay_start"]
    else:
        content = bucket["scenario"]

        
    side_list = content.bundle("side")

    
    for i,side_data in enumerate(side_list):


        side_content = side_data.head

        # Even for 1v1 games, the replay file will have sample data for the other possible sides.  This is why the parser filters exclusively for "human" or "network" players
        if re.search(r'current_player="([^"]*)"',side_content) and re.search(r'controller="([^"]*)"',side_content).group(1) in ("human","network"):
            player = re.search(r'current_player="([^"]*)"',side_content).group(1)

            agent = "human"


            side = int(re.search(r'\nside=(")?(\d+)(")?',side_content).group(2))

            try:
                location = re.search(r'\nteam_name="([^"]*)"',side_content).group(1)
            except:
                location = re.search(r'\nteam_name=([^"\n]+)\n',side_content).group(1)


            try:
                leader = re.search(r'\ntype\s*=\s*_?"([^"]+)"',side_content).group(1).replace("female^","")
            except:
                leader = re.search(r'\nlanguage_name\s*=\s*_?"([^"]+)"',side_data["unit"].head).group(1).replace("female^","")


            try:
                lx = int(re.search(r"\nx=(\d+)",side_data["unit"].head).group(1))
                ly = int(re.search(r"\ny=(\d+)",side_data["unit"].head).group(1))
                lpos = (lx,ly)
            except:
                lpos = (0,-1*side)            


            try:
                faction_units = re.search(r'\nrecruit\s*=\s*_?"([^"]+)"',side_content).group(1)
                factions = [unit_db[unit]["faction"] for unit in faction_units.split(",") if unit_db[unit]["faction"] != "Loyalists/Rebels"]

            except:
                try:
                    faction_units = re.search(r'\nprevious_recruits\s*=\s*_?"([^"]+)"',side_content).group(1)
                    factions = [unit_db[unit]["faction"] for unit in faction_units.split(",") if unit_db[unit]["faction"] != "Loyalists/Rebels"]

                except:
                    try:
                        faction_units = re.search(r'\nleader\s*=\s*_?"([^"]+)"',side_content).group(1)
                        factions = [unit_db[unit]["faction"] for unit in faction_units.split(",") if unit_db[unit]["faction"] != "Loyalists/Rebels"]
                    
                    except:

                        new_content = next(content.head for content in bucket["carryover_sides_start"].bundle("side") if player==re.search(r'current_player="([^"]*)"',content.head).group(1))  
                        faction_units = re.search(r'\nprevious_recruits\s*=\s*_?"([^"]+)"', new_content).group(1)
                        factions = [unit_db[unit]["faction"] for unit in faction_units.split(",") if unit_db[unit]["faction"] != "Loyalists/Rebels"]


            faction_counter = Counter(factions)
            potential_faction = faction_counter.most_common(1)[0][0]

            """
There is no way to guarantee the leader and/or faction for each side.  However, "parse_starting_units" relies on the faction.
The current logic is to parse the leader and faction using old logic that is accurate ~95% of the time.
The real faction is solved for within "parse_action".
If the leader does not perform an action (which is the best way to prove the leader), and if the potential leader's faction agrees
with the new leader, then the potential leader becomes the leader.
            """

            player_list[side] = {
                "player": player
                ,"agent": agent
                ,"faction": None
                ,"potential_faction": potential_faction
                ,"unit_factions": []
                ,"leader":None
                ,"potential_leader": leader
                ,"leader_known": lpos[1]>0
                ,"starting_position": lpos
                ,"side": side
                ,"location": location
            }
        

            
    return player_list 











def parse_starting_units(bucket, player_list):

    
    unit_list = {}
    unique_sides = [p["side"] for p in player_list.values()]
    unit_ids = {s:0 for s in unique_sides}    

    # For hornshark island, the starting units depend on the player's faction.  This dictionary provides the necessary conversion to allow starting units
    # to line up with the players "potential_faction"
    faction_conversion = {
        0:"Drakes"
        ,1:"Knalgan Alliance"
        ,2:"Loyalists"
        ,3:"Northerners"
        ,4:"Rebels"
        ,5:"Undead"
        }
    
    for player in player_list.values():

        side = player["side"]

        # Despite unreliable leader information from "replay_start", we can still create a placeholder unit and set it equal to leader
        # Once the leader participates in combat, we can confirm the unit and store it in memory
        place_holder_leader = {
            "name": None,
            "unit_id": None
            ,"faction": None
            ,"attacks":[]
        }
        
        unit_list[player["starting_position"]] = Unit(uid=f"{side:01d}X{unit_ids[side]:02d}", unit_def=place_holder_leader, side=side, leader=True)
        unit_ids[side] += 1          
            
            
    if bucket["replay_start"]:
        
        for event in bucket["replay_start"].bundle("event"):
    
    
            if event["switch"]:
                for switch in event.bundle("switch"):
                    if re.search(r'(p|side)(\d+)_faction',switch.head):
                        side_check = int(re.search(r'(p|side)(\d+)_faction',switch.head).group(2))
                        for content in switch.buckets:
                            if content.name=="case":
                                if re.search(r'\[(\d+)\]',content.head):
                                    factions = [faction_conversion[int(re.search(r'\[(\d+)\]',content.head).group(1))]]
                                else:
                                    factions = re.search(r'value="([^"]+)"',content.head).group(1).split(",")
                                if player_list[side_check]["potential_faction"] in factions:
                                    for starting_unit in content.bundle("unit"):
                                        side = int(re.search(r"side=(\d+)",starting_unit.head).group(1))
                                        x = int(re.search(r"x=(\d+)",starting_unit.head).group(1))
                                        y = int(re.search(r"y=(\d+)",starting_unit.head).group(1))
                                        name = re.search(r'type\s*=\s*_?"([^"]+)"',starting_unit.head).group(1)
    
                                        if side in unique_sides:
    #                                         print(factions,side,name,x,y)
                                            unit_list[(x,y)] = Unit(uid=f"{side:01d}X{unit_ids[side]:02d}", unit_def=unit_db[name], side=side)
                                            unit_ids[side] += 1  
                                    break
                                    
                            elif content.name=="else":
                                for starting_unit in content.bundle("unit"):
                                    side = int(re.search(r"side=(\d+)",starting_unit.head).group(1))
                                    x = int(re.search(r"x=(\d+)",starting_unit.head).group(1))
                                    y = int(re.search(r"y=(\d+)",starting_unit.head).group(1))
                                    name = re.search(r'type\s*=\s*_?"([^"]+)"',starting_unit.head).group(1)
    
                                    if side in unique_sides:
                                        unit_list[(x,y)] = Unit(uid=f"{side:01d}X{unit_ids[side]:02d}", unit_def=unit_db[name], side=side)
                                        unit_ids[side] += 1  
                                break
                            
                                
    return unit_list, unit_ids
                            






def parse_turns(bucket, player_list, flags):

    """
There is a sesction within "replay" that summarizes the info at the beginning of each side's turn.

There are a few potential issues:
    Sometimes inactive sides will have info summarized (in a 1v1 game on a 4 player map there may be 4 sides inside the turn summary)
    Sometimes turn info summaries are fired mid-round giving two rows with different info for the same turn/side combination

We can get around this by only including data on sides that have been parsed during "parse_players" and by only keeping the first turn summary per side/turn
    """

    data = []  
    unique_sides = [p["side"] for p in player_list.values()]
    
    try:
        turn_list = map(lambda x: x.head, bucket["replay"]["upload_log"]["ai_log"].bundle("turn_info"))
    except:
        turn_list = []
        
    
    for content in turn_list:

        gold = int(re.search(r"\ngold=(-?\d+)",content).group(1))
        side = int(re.search(r"\nside=(\d+)",content).group(1))
        turn = int(re.search(r"\nturn=(\d+)",content).group(1))
        units = int(re.search(r"\nunits=(\d+)",content).group(1))
        units_cost = int(re.search(r"\nunits_cost=(\d+)",content).group(1))
        villages = int(re.search(r"\nvillages=(\d+)",content).group(1))


        if side in unique_sides:
            turn_info = {
                "experience_id": None
                ,"turn":turn
                ,"side":side
                ,"gold":gold
                ,"units":units
                ,"units_cost":units_cost
                ,"villages":villages
            }

            data.append(turn_info)
        
        
    turn_df = pd.DataFrame(data)
    turn_df.drop_duplicates(subset=['side', 'turn'], keep='first',inplace=True)
    
    if len(turn_df)<=4:
        flags["turn_long_enough"] = False
        
    elif len(turn_df.side.unique())!=2:
        flags["two_players"] = False
        
        
    return turn_df, flags







def parse_actions(bucket, player_list, flags):

    """
There are many actions that exist within Wesnoth replays.  This function takes the bucket, player_list generated from *parse_players*, and flags
    to compile a list of actions that have been taken.
The resultant data (action_df) contains 1 row per turn per individual unit.
Units that made no turn are still included as inaction is almost as important as actions in this game.

There are 4 main events that this function parses:
    INIT_SIDE
        Whenever a new side takes control of the game.  This may fire multiple times per turn, but replays from version 1.11 and greater always indicate the new side.
        The multiple instances of "init_side" per round as well as the lack of declaring the side is the reason older replays have not been parsed.
    RECRUIT
        Whenever a unit is recruited, this event fires.  It tells us the location, name of the unit, and the location of the leader.
    MOVE
        This action details the movement of units.  This does not specify the name or unique identifier of the unit, so this must be tracked by the parser.
    ATTACK
        This contains information regarding combat.  It gives the location of the two units as well as their names and the attack they used.
        It also gives the information regarding individual strikes (whether they hit, how much damage they dealt, and the odds of hitting).
        Unfortunately, it does not say who performed each attack as well as information on "first_strike", so this must also be solved by the parser.
    """

 
    unit_list, unit_ids = parse_starting_units(bucket,player_list)

    
    data = []
    combat_data = {}
    graveyard = {}

    # plague resurrecting a walking corpse is such a rare occurence that it's useful enough to figure out that possibility as early as possible
    plague = any([p["faction"]=="Undead" for p in player_list.values()])

    
    turn = 1
    side = None
    first_side = None
    
    # compiling a list of all the actions that exist within the "replay"
    action_list = []
    for replay_item in bucket.bundle("replay"):
        if len(replay_item.bundle("command"))>0:
            action_list = replay_item.bundle("command")
            break
    
    
    idx = 0
    
    # Some actions and replay structures require accessing previous and later actions, preventing a simple for loop over the list
    while idx<len(action_list):
        
        action = action_list[idx]
        
        idx += 1


        # This logic parses "init_side" action to verify that a new side was indeed chosen and if so, if the result is a new turn
        if action["init_side"]:
            
            new_side = int(re.search(r"\nside_number=(\d+)",action["init_side"].head).group(1))

            
            if not side:
                side = first_side = new_side
                first_side = new_side

            # This means that the init_side actually switched which player has control
            elif side!=new_side:

                # compiling a list of all units that performed an action last round
                active_units = set((d["uid"] for d in data if d["side"]==side and d["turn"]==turn))

                # All units that did not perform an action but could have, needs to be included in the data
                for (x,y), unit_info in unit_list.items():
                    if unit_info.side==side and unit_info.uid not in active_units:
                        
                        inaction_info = {
                            "experience_id": None
                            ,"turn": turn
                            ,"side": side
                            ,"tod": None
                            ,"leader": unit_info.leader
                            ,"active": False
                            ,"recruited": False
                            ,"uid": unit_info.uid
                            ,"unit_type_id": unit_info.unit_id
                            ,"movement_origin_x": x
                            ,"movement_origin_y": y
                            ,"movement_destination_x": x
                            ,"movement_destination_y": y
                            ,"attack_origin_x": None
                            ,"attack_origin_y": None
                            ,"attack_destination_x": None
                            ,"attack_destination_y": None
                            ,"attack_id": None
                            ,"defender_uid": None
                            ,"defender_unit_type_id": None
                            ,"defender_attack_id": None
                            ,"attacker_kill": None
                            ,"defender_kill": None
                            ,"attacker_leveled": None
                            ,"defender_leveled": None
                            ,"attacker_raised_corpse": None
                            ,"defender_raised_corpse": None
                            ,"hits_dealt": None
                            ,"hits_dealt_attempted": None
                            ,"hits_dealt_estimated": None
                            ,"damage_dealt": None
                            ,"hits_received": None
                            ,"hits_received_attempted": None 
                            ,"hits_received_estimated": None 
                            ,"damage_received": None
                        }
            
                        data.append(inaction_info)                   

                # If we are returning to the first player, the turn must increment
                side = new_side
                
                if side==first_side:
                    
                    turn +=1
    
                
        
        
        # A common action is "recruit" where a unit is recruited.  Often, we only get info on the location of the recruitment alongside the name, as well as the coordinates of the leader
        elif action["recruit"]:


            content = action["recruit"]
            
            name = re.search(r'\ntype\s*=\s*_?"([^"]+)"',content.head).group(1)

            # coordinates of the new recruitment
            x = int(re.search(r"\nx=(\d+)",content.head).group(1))
            y = int(re.search(r"\ny=(\d+)",content.head).group(1))

            # coordinates of the leader
            leader_x = int(re.search(r"\nx=(\d+)",content["from"].head).group(1))
            leader_y = int(re.search(r"\ny=(\d+)",content["from"].head).group(1))


            # A quick check to make sure that the replay correctly followed the leader's position
            if player_list[side]["leader_known"]:
                if ((leader_x,leader_y) not in unit_list) or (not unit_list[(leader_x,leader_y)].leader):
                    flags["correct_leader_location"] = False
                    
                elif side!=unit_list[(leader_x,leader_y)].side:
                    flags["correct_leader_side"] = False

                
            # If leader was not known (a relatively uncommon issue for replays), the leader position is then noted
            if not player_list[side]["leader_known"]:
                unit_list[(leader_x,leader_y)] = unit_list[(0,-1*side)]
                unit_list.pop((0,-1*side))
                player_list[side]["leader_known"] = True


            
            unit_list[(x,y)] = Unit(uid=f"{side:01d}X{unit_ids[side]:02d}", unit_def=unit_db[name], side=side)
            unit_ids[side] += 1

            # The parser compiles a list of the faction of each unit recruited.  At the end, the most common faction is determined to be the player's faction
            player_list[side]["unit_factions"].append(unit_list[(x,y)].faction)


            action_info = {
                "experience_id": None
                ,"turn": turn
                ,"side": side
                ,"tod": None
                ,"leader": False
                ,"active": False
                ,"recruited": True
                ,"uid": unit_list[(x,y)].uid
                ,"unit_type_id": unit_list[(x,y)].unit_id
                ,"movement_origin_x": x
                ,"movement_origin_y": y
                ,"movement_destination_x": x
                ,"movement_destination_y": y
                ,"attack_origin_x": None
                ,"attack_origin_y": None
                ,"attack_destination_x": None
                ,"attack_destination_y": None
                ,"attack_id": None
                ,"defender_uid": None
                ,"defender_unit_type_id": None
                ,"defender_attack_id": None
                ,"attacker_kill": None
                ,"defender_kill": None
                ,"attacker_leveled": None
                ,"defender_leveled": None
                ,"attacker_raised_corpse": None
                ,"defender_raised_corpse": None
                ,"hits_dealt": None
                ,"hits_dealt_attempted": None
                ,"hits_dealt_estimated": None
                ,"damage_dealt": None
                ,"hits_received": None
                ,"hits_received_attempted": None 
                ,"hits_received_estimated": None 
                ,"damage_received": None
            }

            data.append(action_info)
         

        # unfortunately, it is not as easy as pulling values for movement given by the replay.
        # Sometimes, later actions give updates to the actual movement.
        elif action["move"]:


            xo = int(re.search(r'\nx\s*=\s*_?"([^"]+)"',action["move"].head).group(1).split(",")[0])
            yo = int(re.search(r'\ny\s*=\s*_?"([^"]+)"',action["move"].head).group(1).split(",")[0])
            x = int(re.search(r'\nx\s*=\s*_?"([^"]+)"',action["move"].head).group(1).split(",")[-1])
            y = int(re.search(r'\ny\s*=\s*_?"([^"]+)"',action["move"].head).group(1).split(",")[-1])


                
            if action["checkup"]:

                try:
                    x = int(re.search(r"\nfinal_hex_x=(\d+)",action["checkup"]["result"].head).group(1))
                    y = int(re.search(r"\nfinal_hex_y=(\d+)",action["checkup"]["result"].head).group(1))
                except:
                    x = xo
                    y = yo



            else:

                next_action = action_list[idx+1]

                if next_action["mp_checkup"]:


                    if re.search(r"\nfinal_hex_x=(\d+)",next_action["mp_checkup"].head):

                        try:
                            x = int(re.search(r"\nfinal_hex_x=(\d+)",next_action["mp_checkup"].head).group(1))
                            y = int(re.search(r"\nfinal_hex_y=(\d+)",next_action["mp_checkup"].head).group(1))
                        except:
                            x = xo
                            y = yo
               

            # For faulty movements, we set the starting and final location variables to be the same
            # That way, only "real" movement is handled by the following code
            if xo!=x or yo!=y:

                # Graveyard tracks potential resurrections because the replay file does not say if a walking corpse is created, only if a unit is killed
                # If there is movement from a graveyard, it means that a walking corpse was created
                if (xo,yo) in graveyard:
                    new_uid = f"{graveyard[(xo,yo)]['tombstone'].side:01d}X{unit_ids[graveyard[(xo,yo)]['tombstone'].side]:02d}"
                    unit_list[(xo,yo)] = Unit(uid=new_uid, unit_def=unit_db["Walking Corpse"], side=graveyard[(xo,yo)]["tombstone"].side)
                    unit_ids[graveyard[(xo,yo)]["tombstone"].side] += 1 

                    # Locating the combat where a walking corpse was created
                    for i in range(len(data)-1,-1,-1):
                        cur_action = data[i]

                        # If the data contains combat
                        if cur_action["defender_uid"]:
                            # Need to check if combat included the potential resurrected unit
                            if graveyard[(xo,yo)]["tombstone"].uid==cur_action["defender_uid"]:
                                data[i]["attacker_raised_corpse"] = new_uid
                            elif graveyard[(xo,yo)]["tombstone"].uid==cur_action["uid"]:
                                data[i]["defender_raised_corpse"] = new_uid
                            else:
                                continue

                            break

                    graveyard.pop((xo,yo))
            
                # Super simple, update unit location inside unit_list and add movement to data
                if (xo,yo) in unit_list:
                    unit_list[(x,y)] = unit_list[(xo,yo)]
                    unit_list.pop((xo,yo))


                    # Units can have multiple move commands, we only need the initial and final movement, so if a previous movement command exits, we simple update final x,y
                    action_idx = next((i for i, item in enumerate(data) if item["side"]==side and item["turn"]==turn and item["uid"]==unit_list[(x,y)].uid), None)

                    if action_idx is not None:
                        data[action_idx]["movement_destination_x"] = x
                        data[action_idx]["movement_destination_y"] = y
                        
                    else:  

                        action_info = {
                            "experience_id": None
                            ,"turn": turn
                            ,"side": side
                            ,"tod": None
                            ,"leader": unit_list[(x,y)].leader
                            ,"active": True
                            ,"recruited": False
                            ,"uid": unit_list[(x,y)].uid
                            ,"unit_type_id": unit_list[(x,y)].unit_id
                            ,"movement_origin_x": xo
                            ,"movement_origin_y": yo
                            ,"movement_destination_x": x
                            ,"movement_destination_y": y
                            ,"attack_origin_x": None
                            ,"attack_origin_y": None
                            ,"attack_destination_x": None
                            ,"attack_destination_y": None
                            ,"attack_id": None
                            ,"defender_uid": None
                            ,"defender_unit_type_id": None
                            ,"defender_attack_id": None
                            ,"attacker_kill": None
                            ,"defender_kill": None
                            ,"attacker_leveled": None
                            ,"defender_leveled": None
                            ,"attacker_raised_corpse": None
                            ,"defender_raised_corpse": None
                            ,"hits_dealt": None
                            ,"hits_dealt_estimated": None
                            ,"hits_dealt_attempted": None
                            ,"damage_dealt": None
                            ,"hits_received": None
                            ,"hits_received_attempted": None 
                            ,"hits_received_estimated": None 
                            ,"damage_received": None
                        }
            
                        data.append(action_info) 

                    # Units can't walk on top of other units, if there was a potential resurrection on (x,y) then it is no longer possible a resurrection occurred
                    if plague:
                        if (x,y) in graveyard:
                            graveyard.pop((x,y))               
                
                
                else:
                    flags["no_phantom_unit"] = False    
    
            
    
        # For combat, we get a lot of data upfront    
        elif action["attack"]:
            
            tod = re.search(r'tod="([^"]+)"',action["attack"].head).group(1)         
            
            attacker = re.search(r'attacker_type="([^"]+)"',action["attack"].head).group(1).replace("female^","")
            attacker_lvl = int(re.search(r"attacker_lvl=(\d+)",action["attack"].head).group(1))
            attacker_weapon = int(re.search(r"\nweapon=((-?\d+))",action["attack"].head).group(1))
            attacker_x = int(re.search(r"x=(\d+)",action["attack"]["source"].head).group(1))
            attacker_y = int(re.search(r"y=(\d+)",action["attack"]["source"].head).group(1))
            attacker_coord = (attacker_x,attacker_y)
            
            
            defender = re.search(r'defender_type="([^"]+)"',action["attack"].head).group(1).replace("female^","")
            defender_lvl = int(re.search(r"defender_lvl=(\d+)",action["attack"].head).group(1))
            defender_weapon = int(re.search(r"defender_weapon=((-?\d+))",action["attack"].head).group(1))
            defender_x = int(re.search(r"x=(\d+)",action["attack"]["destination"].head).group(1))
            defender_y = int(re.search(r"y=(\d+)",action["attack"]["destination"].head).group(1))
            defender_coord = (defender_x,defender_y)
            
            
           
            # Need to add resurrection to data
            if attacker_coord in graveyard:
                new_uid = f"{graveyard[attacker_coord]['tombstone'].side:01d}X{unit_ids[graveyard[attacker_coord]['tombstone'].side]:02d}"
                unit_list[attacker_coord] = Unit(uid=new_uid, unit_def=unit_db["Walking Corpse"], side=graveyard[attacker_coord]["tombstone"].side)
                unit_ids[graveyard[attacker_coord]["tombstone"].side] += 1 

                for i in range(len(data)-1,-1,-1):
                    cur_action = data[i]

                    # If the data contains combat
                    if cur_action["defender_uid"]:
                        # Need to check if combat included the potential resurrected unit
                        if graveyard[attacker_coord]["tombstone"].uid==cur_action["defender_uid"]:
                            data[i]["attacker_raised_corpse"] = new_uid
                        elif graveyard[attacker_coord]["tombstone"].uid==cur_action["uid"]:
                            data[i]["defender_raised_corpse"] = new_uid
                        else:
                            continue

                        break
                
                graveyard.pop(attacker_coord)
                
                
            if defender_coord in graveyard:
                new_uid = f"{graveyard[defender_coord]['tombstone'].side:01d}X{unit_ids[graveyard[defender_coord]['tombstone'].side]:02d}"
                unit_list[defender_coord] = Unit(uid=new_uid, unit_def=unit_db["Walking Corpse"], side=graveyard[defender_coord]["tombstone"].side)
                unit_ids[graveyard[defender_coord]["tombstone"].side] += 1 

                for i in range(len(data)-1,-1,-1):
                    cur_action = data[i]

                    # If the data contains combat
                    if cur_action["defender_uid"]:
                        # Need to check if combat included the potential resurrected unit
                        if graveyard[defender_coord]["tombstone"].uid==cur_action["defender_uid"]:
                            data[i]["attacker_raised_corpse"] = new_uid
                        elif graveyard[defender_coord]["tombstone"].uid==cur_action["uid"]:
                            data[i]["defender_raised_corpse"] = new_uid
                        else:
                            continue

                        break
                
                graveyard.pop(defender_coord)

            
            # If we have unit information on each of the combatants
            if attacker_coord in unit_list and defender_coord in unit_list:


                # Leaders start off unknown, if a leader is involved in combat and we don't have data yet, we can update the leader's info to be unit specific
                if unit_list[attacker_coord].leader and not unit_list[attacker_coord].name:
                    new_leader = Unit(uid=unit_list[attacker_coord].uid, unit_def=unit_db[attacker], side=unit_list[attacker_coord].side, leader=True)
                    unit_list[attacker_coord] = new_leader
                    player_list[new_leader.side]["leader"] = new_leader.name
                    player_list[new_leader.side]["leader_known"] = True
    
                    for leader_idx in (i for i, item in enumerate(data) if item["uid"]==new_leader.uid):
                        data[leader_idx]["unit_type_id"] = new_leader.unit_id
    
                        
                if unit_list[defender_coord].leader and not unit_list[defender_coord].name:
                    new_leader = Unit(uid=unit_list[defender_coord].uid, unit_def=unit_db[defender], side=unit_list[defender_coord].side, leader=True)
                    unit_list[defender_coord] = new_leader
                    player_list[new_leader.side]["leader"] = new_leader.name
                    player_list[new_leader.side]["leader_known"] = True
    
                    for leader_idx in (i for i, item in enumerate(data) if item["uid"]==new_leader.uid):
                        data[leader_idx]["unit_type_id"] = new_leader.unit_id


                
                
                a = unit_list[attacker_coord]
                d = unit_list[defender_coord]
                
                
                if a.name!=attacker:

                    # Leveling up is another event that is not tracked directly by the replay, so we need to check if a unit leveled up last combat
                    if attacker in a.evolution:
                        a = Unit(uid=a.uid, unit_def=unit_db[attacker], side=a.side)
                        unit_list[attacker_coord] = a

                        # Updating the previous combat the unit participated in
                        for i in range(len(data)-1,-1,-1):
                            cur_action = data[i]
                            if cur_action["defender_uid"]:

                                if cur_action["uid"]==a.uid:
                                    data[i]["attacker_leveled"] = a.unit_id
                                elif cur_action["defender_uid"]==a.uid:
                                    data[i]["defender_leveled"] = a.unit_id
                                else:
                                    continue
                                    
                            break
                                               
                
                if d.name!=defender:
                    
                    if defender in d.evolution:
                        d = Unit(uid=d.uid, unit_def=unit_db[defender], side=d.side)
                        unit_list[defender_x,defender_y] = d
                        
                        for i in range(len(data)-1,-1,-1):
                            cur_action = data[i]
                            if cur_action["defender_uid"]:

                                if cur_action["uid"]==d.uid:
                                    data[i]["attacker_leveled"] = d.unit_id
                                elif cur_action["defender_uid"]==d.uid:
                                    data[i]["defender_leveled"] = d.unit_id
                                else:
                                    continue
                                    
                            break                
                

                # Making sure that combat data agrees with data parsed from replay    
                if unit_list[attacker_coord].name==attacker and unit_list[defender_coord].name==defender:
                    
                    # Using basic logic to determine the weapon the attacker used
                    if attacker_weapon<len(a.attacks):
                        attacker_attack = a.attacks[attacker_weapon]
                    elif len(a.attacks)==1:
                        attacker_attack = a.attacks[0]
                    else:
                        flags["known_weapon"] = False
                        continue


                    # Slightly more complicated logic to determine the weapon that the defender used 
                    potential_def_attacks = [att for att in d.attacks if att.ranged==attacker_attack.ranged]    
                    
                    if len(potential_def_attacks)==0:
                        defender_attack = None
                    elif len(potential_def_attacks)==1:
                        defender_attack = potential_def_attacks[0]
                    else:
                        if defender_weapon<0 or defender_weapon>=len(d.attacks):
                            flags["known_weapon"] = False
                            continue
                        else:
                            defender_attack = d.attacks[defender_weapon]
                     
                    
                    if defender_attack and attacker_attack.ranged!=defender_attack.ranged:
                        flags["weapon_mismatch"] = False
                        continue

                    

                    
                    # There are two main ways combat data is stored, one is easy and the other requires more manual bundling of all combat events
                    if action["checkup"] and action["checkup"]["result"]:
                        results = action["checkup"].bundle("result")
                    elif idx<len(action_list):
                        j = idx
                        next_action = action_list[j]
                        event_names = [b.name for b in next_action.buckets]
                        
                        results = []
                        
                        while not any([key_event in event_names for key_event in ("init_side","move","attack","recruit")]) and j<len(action_list): 
                            next_action = action_list[j]
                            event_names = [b.name for b in next_action.buckets] 
                            
                            if next_action["mp_checkup"]:
                                results.append(next_action)
 
                            j+=1
                            
                        idx = j-1
            
                    else:
                        break


                    # Checking to see if the attacker has already made movement this round.  If so, we update that row with the combat info
                    action_idx = next((i for i, item in enumerate(data) if item["side"]==side and item["turn"]==turn and item["uid"]==a.uid), None)

                    if action_idx:
                        current_combat = data[action_idx]
                        current_combat["tod"] = tod
                        current_combat["attack_origin_x"] = attacker_x
                        current_combat["attack_origin_y"] = attacker_y
                        current_combat["attack_destination_x"] = defender_x
                        current_combat["attack_destination_y"] = defender_y
                        current_combat["attack_id"] = attacker_attack.attack_id
                        current_combat["defender_uid"] = d.uid
                        current_combat["defender_unit_type_id"] = d.unit_id
                        current_combat["defender_attack_id"] = defender_attack.attack_id if defender_attack else None
                        current_combat["damage_dealt"] = 0
                        current_combat["hits_dealt"] = 0
                        current_combat["hits_dealt_attempted"] = 0
                        current_combat["hits_dealt_estimated"] = 0
                        current_combat["damage_received"] = 0
                        current_combat["hits_received"] = 0
                        current_combat["hits_received_attempted"] = 0
                        current_combat["hits_received_estimated"] = 0

                        
                    else:
                        action_info = {
                            "experience_id": None
                            ,"turn": turn
                            ,"side": side
                            ,"tod": tod
                            ,"leader": a.leader
                            ,"active": True
                            ,"recruited": True
                            ,"uid": a.uid
                            ,"unit_type_id": a.unit_id
                            ,"movement_origin_x": attacker_x
                            ,"movement_origin_y": attacker_y
                            ,"movement_destination_x": attacker_x
                            ,"movement_destination_y": attacker_y
                            ,"attack_origin_x": attacker_x
                            ,"attack_origin_y": attacker_y
                            ,"attack_destination_x": defender_x
                            ,"attack_destination_y": defender_y
                            ,"attack_id": attacker_attack.attack_id
                            ,"defender_uid": d.uid
                            ,"defender_unit_type_id": d.unit_id
                            ,"defender_attack_id": defender_attack.attack_id if defender_attack else None
                            ,"attacker_kill": None
                            ,"defender_kill": None
                            ,"attacker_leveled": None
                            ,"defender_leveled": None
                            ,"attacker_raised_corpse": None
                            ,"defender_raised_corpse": None
                            ,"hits_dealt": 0
                            ,"hits_dealt_attempted": 0
                            ,"hits_dealt_estimated": 0
                            ,"damage_dealt": 0
                            ,"hits_received": 0
                            ,"hits_received_attempted": 0
                            ,"hits_received_estimated": 0 
                            ,"damage_received": 0
                        }
                        
                        data.append(action_info) 
                        current_combat = data[-1]
                        
                    
                    # Logic to determine the order of attacks
                    if defender_attack:
                        if defender_attack.first_strike==1 and attacker_attack.first_strike==0:
                            combatants = [defender_coord,attacker_coord]
                        else:
                            combatants = [attacker_coord,defender_coord]

                    else:
                        combatants = [attacker_coord]
                    
                    
                    
                    strike = 0
                    dies = False  
                    hit_known = False
                    berserk = attacker_attack.berserk or (defender_attack.berserk if defender_attack else False)

                    # Have to track hits remaining to follow combat data on who performed which attack
                    combat_tracker = {
                        attacker_coord:{
                            "hits": attacker_attack.hits
                            ,"hits_remaining": attacker_attack.hits
                            ,"opp_coord": defender_coord
                            }
                    }

                    if defender_attack:
                        combat_tracker[defender_coord] = {
                            "hits": defender_attack.hits
                            ,"hits_remaining": defender_attack.hits
                            ,"opp_coord": attacker_coord
                            }

                    # Iterating over combat "results" to find the full information on the combat
                    for result in results:
                

                        current_coord = combatants[strike]
                        
                        if result["mp_checkup"]:
                            content = result["mp_checkup"].head
                            
                        else:
                            content = result.head
 
                            
                            
                        if hit_known and re.search(r"dies=(yes|no)",content):    

                            dies = True if re.search(r"dies=(yes|no)",content).group(1)=="yes" else False


                            if dies:

                                if current_coord==attacker_coord:
                                    current_combat["attacker_kill"] = d.uid

                                    if unit_list[defender_coord].race!="Undead" and attacker_attack.plague:
                                        graveyard[defender_coord] = {"tombstone":unit_list[defender_coord],"killer":unit_list[attacker_coord].uid}
                                        graveyard[defender_coord]["tombstone"].side = unit_list[attacker_coord].side

                                        
                                else:
                                    current_combat["defender_kill"] = a.uid

                                    if unit_list[attacker_coord].race!="Undead" and defender_attack.plague:
                                        graveyard[attacker_coord] = {"tombstone":unit_list[attacker_coord],"killer":unit_list[defender_coord].uid}
                                        graveyard[attacker_coord]["tombstone"].side = unit_list[defender_coord].side
                                                                
                                    
                                break


                                

                            hit_known = False



                            if all([ct["hits_remaining"]==0 for ct in combat_tracker.values()]) and berserk: 

                                
                                for ct in combat_tracker.keys():
                                    combat_tracker[ct]["hits_remaining"] = combat_tracker[ct]["hits"]
                                    strike = 0

                            elif len(combatants)>1 and combat_tracker[combat_tracker[current_coord]["opp_coord"]]["hits_remaining"]>0:
                                strike = (strike+1)%len(combatants)



                        elif not hit_known and re.search(r"damage=(\d+)",content):
                                
                            dmg = int(re.search(r"damage=(\d+)",content).group(1))
                            hits = True if re.search(r"hits=(yes|no)",content).group(1)=="yes" else False
                            chance = int(re.search(r"chance=(\d+)",content).group(1))/100

                            combat_tracker[current_coord]["hits_remaining"] -= 1


                            if current_coord==attacker_coord:
                                current_combat["hits_dealt_attempted"] += 1
                                current_combat["hits_dealt_estimated"] += chance

                                if hits:
                                    current_combat["hits_dealt"] += 1
                                    current_combat["damage_dealt"] += dmg

                            else:
                                current_combat["hits_received_attempted"] += 1
                                current_combat["hits_received_estimated"] += chance

                                if hits:
                                    current_combat["hits_received"] += 1
                                    current_combat["damage_received"] += dmg
                                
                                


                            hit_known = True

                    
                    if any([ct["hits_remaining"]>0 for ct in combat_tracker.values()]) and not dies:
                        flags["attacks_exhausted"] = False
                        
                
                else:
                    flags["attack_correct_units"] = False
#                     print(f'''
# Turn: {turn}
# Side: {side}
# UIDs: {a.uid}, {d.uid}
                    
# Attacker
#     Memory: {unit_list[attacker_coord].name}
#     Replay: {attacker}
# Defender
#     Memory: {unit_list[defender_coord].name}
#     Replay: {defender}                    
# ''')      
    
                pass
    
    
            else:
                # print(turn, side, unit_db[attacker]["unit_id"], unit_db[defender]["unit_id"],attacker_coord, defender_coord)
                # print(unit_list)
                flags["attack_correct_locations"] = False
            
        else:
            pass
    

    action_df = pd.DataFrame(data)



    if len(action_df)>=3:

        if action_df.groupby(["turn","side","uid"])["movement_origin_x"].count().max()>1:
            flags["action_granularity_upheld"] = False
    
        if flags["turn_long_enough"]:
            turn_df, flags = parse_turns(bucket, player_list, flags)
            
            if turn_df.turn.max() in (action_df.turn.max(),action_df.turn.max()+1):
                pass
            else:
                flags["correct_turn_count"] = False

        # if len(df[df.unit=="PHANTOM"])>1:
        #     flags["only_one_phantom"] = False


    else:
        flags["action_long_enough"] = False



    for player_side, player in player_list.items():
    
        potential_factions = set(faction for faction in player["unit_factions"] if faction!="Loyalists/Rebels")
        
        if len(potential_factions)>1:
            flags["faction_known"] = False
            
            faction_counter = Counter([faction for faction in player["unit_factions"] if faction!="Loyalists/Rebels"])
            player["faction"] = faction_counter.most_common(1)[0][0]
            
        elif len(potential_factions)==1:
            player["faction"] = next(iter(potential_factions))

            if not player["leader"]:
                if player["faction"] in unit_db[player["potential_leader"]]["faction"].split("/"):
                    player["leader"] = unit_db[player["potential_leader"]]["name"]

        else:
            player["faction"] = None

    
    for player in player_list.values():
        if not player["leader"]:
            flags["leader_known"] = False


        
                    
    return action_df, player_list, flags










def parse_replay(content):
    

    bucket = prep_replay(content)



    flags = {flag:True for flag in list(load_config("flags.json").keys())}
    
    
    data = {}
    
    map_name = parse_map(bucket)
    era = parse_era(bucket)

    assert era in ("default_era", "ladder_era")

    player_list = parse_players(bucket)
    
    assert len(player_list)==2
    

    turn_df, flags = parse_turns(bucket, player_list, flags)
    action_df, player_list, flags = parse_actions(bucket, player_list, flags)
    

    data["meta"] = {
        "version": bucket.version
        ,"map": map_name
        ,"era": era
        ,"players": player_list
       }
        
    
    data["flags"] = flags    
    data["turns"] = turn_df
    data["actions"] = action_df

    
    return data











