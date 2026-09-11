"""Local90-byte report21 decoding. Zone sensor identity remains unverified."""
import hashlib
ZONE_NAMES=('K1','K2','K3','K4')
AIR={3:'Chauffage Programme A',4:'Chauffage Programme B',7:'Clim Programme C',8:'Clim Programme D',0:'OFF',1:'Chauffage Confort',2:'Chauffage Éco',5:'Clim Confort',6:'Clim Boost'}
ECS={0:'OFF',1:'ON',2:'Boost'}

def decode21(data):
 if len(data)!=90 or data[:5]!=bytes.fromhex('fffd5aff21') or data[-2]!=0xfe or sum(data)%256:
  raise ValueError('Not a complete valid local 0x21')
 zones=[]
 for i,name in enumerate(ZONE_NAMES):
  raw=int.from_bytes(data[53+2*i:55+2*i],'little')
  zones.append({'zone':f'K{i+1}','name':name,
   'setpoint_c':int.from_bytes(data[13+2*i:15+2*i],'little')/100,
   'setpoint_validation':'Reference installation: USB readback roundtrip confirmed',
   'temperature_candidate_c':None if raw==65535 else int.from_bytes(data[53+2*i:55+2*i],'little',signed=True)/100,
   'temperature_validation':'Layout candidate; physical zone/value confirmation pending'})
 return {'zones':zones,'air':{'raw':data[81],'label':AIR.get(data[81],'Mode non validé')},
  'ecs':{'raw':data[82],'label':ECS.get(data[82],'Mode non validé')},
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
