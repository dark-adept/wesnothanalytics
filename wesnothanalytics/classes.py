import json
import re



class Bucket:
    
    def __init__(self,body,name="root"):
        

        self.name = name


        self.div_pattern = r'(?<=\s)\[(.*?)\]'
        head_match = re.search(self.div_pattern,body)
        
        if head_match:
            self.head = body[:head_match.start()]
        else:
            self.head = body
            
            
        if self.name=="root": 
            self.version = re.search(r'version="(\d+\.\d+\.\d+)(?:\+dev)?"',self.head).group(1)            
            

        self.buckets = [Bucket(**b) for b in self.parse(body)]
        
        
    def __repr__(self):
        
        return f'''{self.name}
{[b.name for b in self.buckets]}
       
       '''
    
    def __getitem__(self,i):
        
        if type(i)==str:
            return next((b for b in self.buckets if b.name==i),None)
        else:
            return self.buckets[i]
    
    
    def parse(self,body):
    
        buckets = []
        matches = re.finditer(self.div_pattern, body)
        current_bucket = ""
        current_start = 0
        counter = 0

        for m in matches:


            if current_bucket=="":
                current_bucket = m.group(1)
                current_start = m.end()

            else:

                if m.group(1)==f'/{current_bucket}':

                    if counter==0:
                        buckets.append({"name":current_bucket,"body":body[current_start:m.start()]})
                        current_bucket = ""
                        current_start = 0
                        counter = 0
                    else:
                        counter -= 1
                        
                elif m.group(1)==current_bucket:
                        counter += 1
                else:
                    next

        return buckets
    
    
    def bundle(self,name):
        
        return [b for b in self.buckets if b.name==name]
   










class Attack:
    
    def __init__(self, first_strike=False, berserk=False, plague=False, **kwargs):
        
        
        self.first_strike = first_strike
        self.berserk = berserk
        self.plague = plague
        
        
        for key, value in kwargs.items():
            setattr(self, key, value)
        
    def __repr__(self):
        
        return f'Attack ({self.name}): {self.attack_type} ({"ranged" if self.ranged else "melee"})'
    
    
    
class Unit:
    
    def __init__(self, uid, unit_def, side, leader=False, evolution=[]):
    
        self.uid = uid
        self.side = side
        self.leader = leader
        self.evolution = evolution
        
        
        for key, value in unit_def.items():
            setattr(self, key, value)

        self.attacks = [Attack(**a) for a in self.attacks]
        
        
    def __repr__(self):
        
        return f'''Unit {self.uid} ({self.name}): {self.faction}
{self.attacks}'''
        