import json
import re

from collections import Counter

import pandas as pd


from .classes import Unit
from .util import load_config,prep_replay



unit_db = load_config("unit_db.json")



def parse_map(bucket):
    
    
    content = bucket["replay_start"].head
    
    
    if scenario := re.search(r'\nname\s*=\s*_?"([^"]+)"', content):
    
        map_name = re.sub(r'[^a-zA-Z0-9\s]+', '', re.split(r'-|—', scenario.group(1).replace("_"," "))[-1].strip()).title()
    
        return map_name
    










def parse_players(bucket):
    
    player_list = {}
    
    replay = bucket["replay_start"]   
    side_list = replay.bundle("side")
    
    for i,side_data in enumerate(side_list):


        content = side_data.head
        
        if re.search(r'current_player="([^"]*)"',content) and re.search(r'controller="([^"]*)"',content).group(1) in ("human","network"):
            player = re.search(r'current_player="([^"]*)"',content).group(1)

            agent = "human"


            side = int(re.search(r'\nside=(")?(\d+)(")?',content).group(2))

            try:
                location = re.search(r'\nteam_name="([^"]*)"',content).group(1)
            except:
                location = re.search(r'\nteam_name=([^"\n]+)\n',content).group(1)


            try:
                leader = re.search(r'\ntype\s*=\s*_?"([^"]+)"',content).group(1).replace("female^","")
            except:
                leader = re.search(r'\nlanguage_name\s*=\s*_?"([^"]+)"',side_data["unit"].head).group(1).replace("female^","")


            try:
                lx = int(re.search(r"\nx=(\d+)",side_data["unit"].head).group(1))
                ly = int(re.search(r"\ny=(\d+)",side_data["unit"].head).group(1))
                lpos = (lx,ly)
            except:
                lpos = (0,-1*side)            




        # Calculating the faction
            faction = unit_db[leader]["faction"]


            if faction=="Loyalists/Rebels":

                try:

                    faction_units = re.search(r'\nrecruit\s*=\s*_?"([^"]+)"',content).group(1)
                    factions = [unit_db[unit]["faction"] for unit in faction_units.split(",") if unit_db[unit]["faction"] in ("Loyalists","Rebels")]




                except:

                    try:
                        faction_units = re.search(r'\nprevious_recruits\s*=\s*_?"([^"]+)"',content).group(1)
                        factions = [unit_db[unit]["faction"] for unit in faction_units.split(",") if unit_db[unit]["faction"] in ("Loyalists","Rebels")]





                    except:

                        faction_units = re.search(r'\nleader\s*=\s*_?"([^"]+)"',content).group(1)
                        factions = [unit_db[unit]["faction"] for unit in faction_units.split(",") if unit_db[unit]["faction"] in ("Loyalists","Rebels")]




                faction_counter = Counter(factions)
                faction = faction_counter.most_common(1)[0][0]


        

            player_list[side] = {"player":player,"agent":agent,"faction":faction,"leader":leader,"starting_position":lpos,"side":side,"location":location}
        

            
    return player_list











def parse_starting_units(bucket, player_list):

    unit_list = {}
    unique_sides = [p["side"] for p in player_list.values()]
    unit_ids = {s:0 for s in unique_sides}    
    leader_known = {s:False for s in unique_sides}
    
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
        unit_list[player["starting_position"]] = Unit(uid=f"{side:01d}X{unit_ids[side]:02d}", unit_def=unit_db[player["leader"]], side=side, leader=True)
        unit_ids[side] += 1

        if player["starting_position"][1]>0:
            leader_known[player["side"]] = True

                
            
            
            
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
                            if player_list[side_check]["faction"] in factions:
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
#                                     print("ELSE",side,name,x,y)
                                    unit_list[(x,y)] = Unit(uid=f"{side:01d}X{unit_ids[side]:02d}", unit_def=unit_db[name], side=side)
                                    unit_ids[side] += 1  
                            break
                            


                                
    return unit_list, unit_ids, leader_known
                            






def parse_turns(bucket, player_list, flags):
    

    data = []  
    unique_sides = [p["side"] for p in player_list.values()]
    
    try:
        turn_list = map(lambda x: x.head,bucket["replay"]["upload_log"]["ai_log"].bundle("turn_info"))
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
            turn_info = {"turn":turn,"side":side,"gold":gold,"units":units,"units_cost":units_cost,"villages":villages}
            data.append(turn_info)
        
        
    df = pd.DataFrame(data)
    df.drop_duplicates(subset=['side', 'turn'], keep='first',inplace=True)
    
    if len(df)<=4:
        flags["long_enough"] = False
        
    elif len(df.side.unique())!=2:
        flags["two_players"] = False
        
        
    return df, flags







def parse_actions(bucket, player_list, flags):
    
    unit_list, unit_ids, leaders_known = parse_starting_units(bucket,player_list)
    
    
    data = []
    combat_data = []
    graveyard = {}
    
    plague = any([p["faction"]=="Undead" for p in player_list.values()])
    
    combats = 1    
    turn = 1
    side = None
    first_side = None
    
#     flags = {flag:True for flag in ["correct_leader_side", "correct_leader_location", "no_phantom_unit", "only_one_phantom", "correct_turn_count", "attack_correct_locations", "attack_correct_units","known_weapons","weapon_mismatch","attacks_exhausted"]}
    
    action_list = bucket["replay"].bundle("command")
    
    idx = 0
#     print(len(action_list))
    while idx<len(action_list):
        
        action = action_list[idx]
        
        idx += 1
#     for action in action_list:
        
        if action["init_side"]:
            


            new_side = int(re.search(r"\nside_number=(\d+)",action["init_side"].head).group(1))
            
            if not side:
                side = first_side = new_side
                first_side = new_side
                
            elif side!=new_side:
                
                side = new_side
                
                if side==first_side:
                    
                    turn +=1
                    

                    
        
                
        
        
        
        elif action["recruit"]:



            content = action["recruit"]


            name = re.search(r'\ntype\s*=\s*_?"([^"]+)"',content.head).group(1)


            x = int(re.search(r"\nx=(\d+)",content.head).group(1))
            y = int(re.search(r"\ny=(\d+)",content.head).group(1))


            leader_x = int(re.search(r"\nx=(\d+)",content["from"].head).group(1))
            leader_y = int(re.search(r"\ny=(\d+)",content["from"].head).group(1))


            if leaders_known[side]:
                if ((leader_x,leader_y) not in unit_list) or (not unit_list[(leader_x,leader_y)].leader):
                    flags["correct_leader_location"] = False
                elif side!=unit_list[(leader_x,leader_y)].side:
                    flags["correct_leader_side"] = False

                
                
            if not leaders_known[side]:
                unit_list[(leader_x,leader_y)] = unit_list[(0,-1*side)]
                del unit_list[(0,-1*side)]
                leaders_known[side] = True



            unit_list[(x,y)] = Unit(uid=f"{side:01d}X{unit_ids[side]:02d}", unit_def=unit_db[name], side=side)
            unit_ids[side] += 1

            action_info = {"turn":turn,"side":side,"action":"recruit","uid":unit_list[(x,y)].uid,"unit":name,"xo":"","yo":"","x":x,"y":y}

            data.append(action_info)
    
        


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
               
            
            if xo!=x or yo!=y:
                
                if (xo,yo) in graveyard:
                    new_uid = f"{graveyard[(xo,yo)]:01d}X{unit_ids[graveyard[(xo,yo)]]:02d}"
                    unit_list[(xo,yo)] = Unit(uid=new_uid, unit_def=unit_db["Walking Corpse"], side=graveyard[(xo,yo)])
                    unit_ids[graveyard[(xo,yo)]] += 1 

                    for i in range(len(data)-1,-1,-1):
                        cur_action = data[i]
                        if cur_action["action"]=="attack" and ((xo,yo)==(cur_action["x"],cur_action["y"]) or (xo,yo)==(cur_action["xo"],cur_action["yo"])):

                            resurrection = {
                                "turn":cur_action["turn"]
                                ,"side":graveyard[(xo,yo)]
                                ,"action":"resurrect"
                                ,"uid":new_uid
                                ,"unit":"Walking Corpse"
                                ,"x":xo
                                ,"y":yo
                                }

                            data.insert(i+1,resurrection)
                            break

                    del graveyard[(xo,yo)]
            
                
                if (xo,yo) in unit_list:
                    unit_list[(x,y)] = unit_list[(xo,yo)]
                    del unit_list[(xo,yo)]

                    action_info = {"turn":turn,"side":side,"action":"move","uid":unit_list[(x,y)].uid,"unit":unit_list[(x,y)].name,"xo":xo,"yo":yo,"x":x,"y":y}

                    data.append(action_info)   
                    
                    if plague:
                        if (x,y) in graveyard:
                            del graveyard[(x,y)]               
                
                
                else:
                    action_info = {"turn":turn,"side":side,"action":"move","uid":"X","unit":"PHANTOM","xo":xo,"yo":yo,"x":x,"y":y}

                    data.append(action_info) 
                    flags["no_phantom_unit"] = False    
    
            
    

        elif action["attack"]:
            
            
#             cid = f"{1:02d}X{combats:03d}"
#             combats += 1
            
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
                new_uid = f"{graveyard[attacker_coord]:01d}X{unit_ids[graveyard[attacker_coord]]:02d}"
                unit_list[attacker_coord] = Unit(uid=new_uid, unit_df=unit_db["Walking Corpse"], side=graveyard[attacker_coord])
                unit_ids[graveyard[attacker_coord]] += 1 
                
                for i in range(len(data)-1,-1,-1):
                    cur_action = data[i]
                    if cur_action["action"]=="attack" and (attacker_coord==(cur_action["x"],cur_action["y"]) or attacker_coord==(cur_action["xo"],cur_action["yo"])):
                        
                        resurrection = {
                            "turn":cur_action["turn"]
                            ,"side":graveyard[attacker_coord]
                            ,"action":"resurrect"
                            ,"uid":new_uid
                            ,"unit":"Walking Corpse"
                            ,"x":attacker_x
                            ,"y":attacker_y
                            }
                        
                        data.insert(i+1,resurrection)
                        break
                
                del graveyard[attacker_coord]
                
                
            if defender_coord in graveyard:
                new_uid = f"{graveyard[defender_coord]:01d}X{unit_ids[graveyard[defender_coord]]:02d}"
                unit_list[defender_coord] = Unit(uid=new_uid, unit_def=unit_db["Walking Corpse"], side=graveyard[defender_coord])
                unit_ids[graveyard[defender_coord]] += 1 
                
                for i in range(len(data)-1,-1,-1):
                    cur_action = data[i]
                    if cur_action["action"]=="attack" and (defender_coord==(cur_action["x"],cur_action["y"]) or defender_coord==(cur_action["xo"],cur_action["yo"])):
                        
                        resurrection = {
                            "turn":cur_action["turn"]
                            ,"side":graveyard[defender_coord]
                            ,"action":"resurrect"
                            ,"uid":new_uid
                            ,"unit":"Walking Corpse"
                            ,"x":defender_x
                            ,"y":defender_y
                            }
                        
                        data.insert(i+1,resurrection)
                        break
                
                del graveyard[defender_coord]

            
            if attacker_coord in unit_list and defender_coord in unit_list:
                
                a = unit_list[attacker_coord]
                d = unit_list[defender_x,defender_y]
                
                
                if a.name!=attacker:
                    
                    if attacker in a.evolution:
                        a = Unit(uid=a.uid, unit_def=unit_db[attacker], side=a.side)
                        unit_list[attacker_coord] = a
                        
                        for i in range(len(data)-1,-1,-1):
                            cur_action = data[i]
                            if cur_action["action"]=="attack" and (attacker_coord==(cur_action["x"],cur_action["y"]) or (attacker_coord)==(cur_action["xo"],cur_action["yo"])):
                                data.insert(i+1,{"turn":cur_action["turn"],"side":a.side,"action":"level","uid":a.uid,"unit":attacker,"x":attacker_x,"y":attacker_y})
                                
                
                
                
                if d.name!=defender:
                    
                    if defender in d.evolution:
                        d = Unit(uid=d.uid, unit_def=unit_db[defender], side=d.side)
                        unit_list[defender_x,defender_y] = d
 
                        for i in range(len(data)-1,-1,-1):
                            cur_action = data[i]
                            if cur_action["action"]=="attack" and (defender_coord==(cur_action["x"],cur_action["y"]) or (defender_coord)==(cur_action["xo"],cur_action["yo"])):
                                data.insert(i+1,{"turn":cur_action["turn"],"side":d.side,"action":"level","uid":d.uid,"unit":defender,"x":defender_x,"y":defender_y})
                        

                    
                
                

                    
                if unit_list[attacker_coord].name==attacker and unit_list[defender_coord].name==defender:
                    
                    retaliation = True

                    if attacker_weapon<len(a.attacks):
                        attacker_attack = a.attacks[attacker_weapon]
                    elif len(a.attacks)==1:
                        attacker_attack = a.attacks[0]
                    else:
                        flags["known_weapon"] = False
                        continue
                        
                    potential_def_attacks = [att for att in d.attacks if att.ranged==attacker_attack.ranged]    
                    
                    if len(potential_def_attacks)==0:
                        retaliation = False
                    elif len(potential_def_attacks)==1:
                        defender_attack = potential_def_attacks[0]
                    else:
                        if defender_weapon<0 or defender_weapon>=len(d.attacks):
                            flags["known_weapon"] = False
                            continue
                        else:
                            defender_attack = d.attacks[defender_weapon]
                     
                    
                    if retaliation and attacker_attack.ranged!=defender_attack.ranged:
                        flags["weapon_mismatch"] = False
                        continue

                    

                    
                    
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

                            
                    
                    
                    if retaliation:
                        if defender_attack.first_strike==1 and attacker_attack.first_strike==0:
                            combatants = [(d,defender_attack,defender_coord,"defender"),(a,attacker_attack,attacker_coord,"attacker")]
                        else:
                            combatants = [(a,attacker_attack,attacker_coord,"attacker"),(d,defender_attack,defender_coord,"defender")]
                    
                    
                    else:
                        combatants = [(a,attacker_attack,attacker_coord,"attacker")]
                    
                    
#                     data.append({"turn":turn,"side":side,"action":"attack","cid":cid,"xo":attacker_x,"yo":attacker_y,"x":defender_x,"y":defender_y})
                    
                    strike = 0
                    dies = False
                    stats = {coord:{"dmg":0,"hits":0,"unit":unit.name,"position":position,"victory":False,"attack":attack,"hits_remaining":attack.hits} for unit,attack,coord,position in combatants}
                    hit_known = False

                    
                    for result in results:
                        
                        
                        unit,attack,coord,position = combatants[strike]
                        
                        if result["mp_checkup"]:
                            content = result["mp_checkup"].head
                            
                        else:
                            content = result.head
 
                            
                            
                        if hit_known and re.search(r"dies=(yes|no)",content):    

                            dies = True if re.search(r"dies=(yes|no)",content).group(1)=="yes" else False

                            if hits:
                                stats[coord]["hits"] += 1
                                stats[coord]["dmg"] += dmg
#                             combat_info = {"cid":cid
#                                            ,"uid":a.uid if position=="attacker" else d.uid
#                                            ,"hits":hits
#                                            ,"dmg":dmg
#                                            ,"dies":dies
#                                           }

#                             combat_data.append(combat_info)
                                

                            if dies:
#                                     print(turn,attacker,defender,position)
                                stats[coord]["victory"] = True
                                

                                if position=="attacker":

                                    if unit_list[defender_coord].race!="Undead" and attacker_attack.plague:
                                        graveyard[defender_coord] = unit_list[attacker_coord].side


                                    del unit_list[defender_coord]

                                else:

                                    if unit_list[attacker_coord].race!="Undead" and defender_attack.plague:
                                        graveyard[attacker_coord] = unit_list[defender_coord].side

                                    del unit_list[attacker_coord]

                                    
                                break

                            hit_known = False


                            if all([s["hits_remaining"]==0 for s in stats.values()]) and any([s["attack"].berserk for s in stats.values()]): 
                                for c in stats.keys():
                                    stats[c]["hits_remaining"] = stats[c]["attack"].hits
                                    strike = 0

                            elif stats[combatants[(strike+1)%len(combatants)][2]]["hits_remaining"]>0:
                                strike = (strike+1)%len(combatants)



                        elif not hit_known and re.search(r"damage=(\d+)",content):
                                
                            dmg = int(re.search(r"damage=(\d+)",content).group(1))
                            hits = True if re.search(r"hits=(yes|no)",content).group(1)=="yes" else False

                            stats[coord]["hits_remaining"]-=1




                            if hits:
                                stats[coord]["dmg"] += dmg

                            hit_known = True


                            if any([c["hits_remaining"]<0 for c in stats.values()]):
                                flags["attacks_exhausted"] = False
                                                      
                                          

                    combat_string = " | ".join([f'{s["unit"]} ({s["position"]}) did {s["dmg"]} dmg in {s["hits"]} hit{"s" if s["hits"]>1 else ""}' for s in stats.values()])    
                    
                    if dies:

                        dead_unit = attacker if position=="defender" else defender
                        combat_string += f" | {dead_unit} died"
                    
                    
                    data.append({"turn":turn,"side":side,"action":"attack","combat_string":combat_string,"xo":attacker_x,"yo":attacker_y,"x":defender_x,"y":defender_y})
                    
                        
                    
                    
                    
                    if any([p["hits_remaining"]>0 for p in stats.values()]) and all([p["victory"]==False for p in stats.values()]):
                        flags["attacks_exhausted"] = False
                        
                
                else:
                    flags["attack_correct_units"] = False
#                     print("\n"*3)
                    
                    
                    data.append({"turn":turn,"side":side,"action":"attack","combat_string":"PHANTOM","xo":attacker_x,"yo":attacker_y,"x":defender_x,"y":defender_y})
                    
                    
             
    
                pass
    
    
            else:
                    
                flags["attack_correct_locations"] = False
            
        else:
            pass
    

    df = pd.DataFrame(data)
#     cdf = pd.DataFrame(combat_data)
    
    
    
    if flags["long_enough"] and len(df)>0:
        turns,flags = parse_turns(bucket, player_list, flags)
#         print(turns.head())

        if len(df[df.unit=="PHANTOM"])>1:
            flags["only_one_phantom"] = False


        if turns.turn.max() in (df.turn.max(),df.turn.max()+1):
            pass
        else:
            flags["correct_turn_count"] = False
            

                    
    return df, flags










def parse_data(content):
    

    bucket = prep_replay(content)



    flags = {flag:True for flag in list(load_config("flags.json").keys())}
    
    
    data = {}
    
    map_name = parse_map(bucket)
    player_list = parse_players(bucket)
    
    if len(player_list)!=2:
        flags["two_players"]
    
    data["meta"] = {
        "version":bucket.version
        ,"map":map_name
        ,"players":player_list
       }
    

    turn_df, flags = parse_turns(bucket, player_list, flags)
    action_df, flags = parse_actions(bucket, player_list, flags)
        
    
    data["flags"] = flags    
    data["turns"] = turn_df.to_dict(orient='records')
    data["actions"] = action_df.to_dict(orient='records')

    
    return data











