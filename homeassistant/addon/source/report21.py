"""Local 90-byte report21 decoding. Zone sensor identity remains unverified."""
import hashlib
MAX_ZONES=9
AIR={3:'Chauffage Programme A',4:'Chauffage Programme B',7:'Clim Programme C',8:'Clim Programme D',0:'OFF',1:'Chauffage Confort',2:'Chauffage Éco',5:'Clim Confort',6:'Clim Boost'}
ECS={0:'OFF',1:'ON',2:'Boost'}

def decode21(data):
 if len(data)!=90 or data[:5]!=bytes.fromhex('fffd5aff21') or data[-2]!=0xfe or sum(data)%256:
  raise ValueError('Not a complete valid local 0x21')
 zones=[]
 zone_slots=[]
 for i in range(MAX_ZONES):
  setpoint_raw=int.from_bytes(data[13+2*i:15+2*i],'little')
  raw=int.from_bytes(data[53+2*i:55+2*i],'little')
  active=not (setpoint_raw==0 and raw in (0,65535))
  setpoint_c=setpoint_raw/100 if active else None
  temperature_c=None if raw in (0,65535) else int.from_bytes(data[53+2*i:55+2*i],'little',signed=True)/100
  slot={'zone':f'K{i+1}','active':active,'setpoint_raw':setpoint_raw,
   'setpoint_c':setpoint_c,'temperature_raw':raw,'temperature_candidate_c':temperature_c,
   'setpoint_offset':13+2*i,'temperature_offset':53+2*i}
  zone_slots.append(slot)
  if active:
   zones.append({'zone':f'K{i+1}','name':f'K{i+1}','active':True,
    'setpoint_c':setpoint_c,
    'setpoint_validation':'Report 0x21 zone slot; writing is validated only for K1-K4',
    'temperature_candidate_c':temperature_c,
    'temperature_validation':'Layout candidate; physical zone/value confirmation pending'})
 return {'zones':zones,'zone_slots':zone_slots,'air':{'raw':data[81],'label':AIR.get(data[81],'Mode non validé')},
  'ecs':{'raw':data[82],'label':ECS.get(data[82],'Mode non validé')},
  'ecs_level':{'raw':data[73],'percent':data[73] if data[73]<=100 else None,
   'validation':'Reference installation: matches IHM 4-bar gauge (100/75/50/25, 24 = lowest step); nightly refill and Boost refill observed'},
  'vacation':{'departure':decode_date(data[5:9]),'return':decode_date(data[9:13]),'present':any(data[5:13])},
  'frame_sha256':hashlib.sha256(data).hexdigest()}


def decode_date(raw):
 import datetime
 value=int.from_bytes(raw,'little')
 if not value: return None
 try:
  return datetime.datetime(1980+(value>>25),(value>>21)&15,(value>>16)&31,(value>>11)&31,(value>>5)&63,(value&31)*2).isoformat()
 except ValueError:
  return 'Date invalide'
