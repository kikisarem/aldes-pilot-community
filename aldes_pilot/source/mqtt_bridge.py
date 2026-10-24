"""HA MQTT discovery and observed state. Never retain/retry a PAC command."""
import json,math,os,threading,time,urllib.request
from pathlib import Path
AIR=['Arrêt','Chauffage Confort','Chauffage Éco','Chauffage Programme A','Chauffage Programme B','Clim Confort','Clim Boost','Clim Programme C','Clim Programme D']
ECS=['Arrêt','Marche','Boost']
def discovery(identity,active_zones=None,air_mode=None,bridge_name='Aldes Pilot'):
 base='aldes_pilot/'+identity
 device={'identifiers':[identity],'name':bridge_name,'manufacturer':'Communauté','model':'Bridge USB Pico W / Pico 2 W'}
 rows=[]
 for key,options in [('air',AIR),('ecs',ECS)]:
  rows.append(('select',key,{'name':'Mode '+key.upper(),'options':options,'optimistic':False}))
 rows.append(('button','vacation_clear',{'name':'Annuler vacances / hors gel','payload_press':'CLEAR'}))
 result={}
 for component,key,extra in rows:
  cfg={'unique_id':identity+'_'+key,'device':device,'availability_topic':base+'/read_availability','command_topic':base+'/'+key+'/set','qos':0,'retain':False,**extra}
  if component!='button':cfg['state_topic']=base+'/'+key+'/state'
  result[f'homeassistant/{component}/{identity}/{key}/config']=cfg
 active_zones=set(active_zones or ())
 for zone in range(5,10):
  if zone not in active_zones:continue
  key='setpoint_k'+str(zone)
  result[f'homeassistant/sensor/{identity}/{key}/config']={
   'unique_id':identity+'_'+key,'device':device,'name':f'Consigne K{zone}',
   'availability_topic':base+'/read_availability','state_topic':base+'/'+key+'/state',
   'unit_of_measurement':'°C','suggested_display_precision':0,
   'expire_after':60,'qos':0,'retain':False,
  }
 for zone in range(1,10):
  if zone not in active_zones:continue
  key='temperature_k'+str(zone)
  result[f'homeassistant/sensor/{identity}/{key}/config']={
   'unique_id':identity+'_'+key,'device':device,'name':f'Température K{zone}',
   'availability_topic':base+'/read_availability','state_topic':base+'/'+key+'/state',
   'unit_of_measurement':'°C','device_class':'temperature','state_class':'measurement',
   'suggested_display_precision':2,'expire_after':60,'qos':0,'retain':False,
  }
 for zone in range(1,5):
  if zone not in active_zones:continue
  key='k'+str(zone)
  result[f'homeassistant/number/{identity}/{key}/config']={
   'unique_id':identity+'_'+key,'device':device,'name':f'Consigne K{zone}',
   'availability_topic':base+'/read_availability','command_topic':base+'/'+key+'/set',
   'state_topic':base+'/'+key+'/state','min':0,'max':24 if air_mode in (1,2,3,4) else 31,'step':1,'mode':'box',
   'unit_of_measurement':'°C','optimistic':False,'qos':0,'retain':False,
  }
 return result

def zone_discovery_topics(identity):
 topics=[]
 for zone in range(1,10):
  topics.append(f'homeassistant/sensor/{identity}/temperature_k{zone}/config')
  if zone>=5:topics.append(f'homeassistant/sensor/{identity}/setpoint_k{zone}/config')
  else:topics.append(f'homeassistant/number/{identity}/k{zone}/config')
 return topics

def active_zone_ids(state):
 return {
  zone for zone in range(1,10)
  if (state.get('zones',{}).get(str(zone),{}).get('active',False))
 }

def parse_command(key,payload,retained=False):
 if retained or len(payload)>100:raise ValueError('Retained/oversized command refused')
 value=payload.decode('utf-8')
 if key in ('air','ecs'):
  values=AIR if key=='air' else ECS
  if value not in values:raise ValueError('Unknown mode')
  return '/api/queue/'+key,{'mode':values.index(value)}
 if key in ('k1','k2','k3','k4'):
  v=float(value)
  if not math.isfinite(v) or (v!=0 and not 16<=v<=31) or v!=int(v):raise ValueError('Invalid setpoint: use 0 (Off) or 16–31 °C')
  return '/api/queue/setpoint',{'zone':int(key[1]),'temperature':v}
 if key=='vacation_clear' and value=='CLEAR':return '/api/queue/vacation/clear',{}
 raise ValueError('Unknown command')

def observed(s):
 if not s.get('available') or s.get('recovery',{}).get('status')=='recovering':return None
 a=s['air']['actual'];e=s['ecs']['actual']
 if type(a)!=int or type(e)!=int or not 0<=a<len(AIR) or not 0<=e<len(ECS):return None
 out={'air':AIR[a],'ecs':ECS[e]}
 for z in range(1,10):
  zone=s.get('zones',{}).get(str(z),{})
  v=zone.get('actual')
  out['k'+str(z)]=str(v) if zone.get('active',v is not None) and isinstance(v,(int,float)) and math.isfinite(v) else ''
  out['setpoint_k'+str(z)]=out['k'+str(z)]
  value=zone.get('temperature_candidate_c')
  out['temperature_k'+str(z)]=str(value) if isinstance(value,(int,float)) and math.isfinite(value) else ''
 return out

def queue_status(queue):
 if not isinstance(queue,dict):return 'File serveur indisponible'
 pending=queue.get('pending') or {}
 current=queue.get('current')
 if current:
  if str(current).startswith('batch:'):
   keys=str(current)[6:].split('+')
   labels={'air':'mode air','ecs':'ECS'}
   items=', '.join(labels.get(key,'K'+key[1:]) for key in keys)
   return f'Envoi groupé {items} · {len(pending)} en attente'
  return f'Envoi {current} · {len(pending)} en attente'
 if pending:return f'{len(pending)} en attente · '+', '.join(pending)
 result=queue.get('result') or {}
 if result.get('status')=='error':return 'Dernière commande en erreur'
 if result.get('status')=='delivered':return 'Repos · dernière commande transmise'
 return 'Repos'

def api(path,body=None):
 request=urllib.request.Request('http://127.0.0.1:8771'+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json','x-pilot-ui':'1','x-pilot-pin':os.environ.get('PILOT_PIN','')})
 with urllib.request.urlopen(request,timeout=5) as r:return json.load(r)

def main():
 import paho.mqtt.client as mqtt
 config=json.loads(Path(os.environ['MQTT_CONFIG']).read_text());identity=config['id'];base='aldes_pilot/'+identity
 client=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id=identity,clean_session=True)
 client.username_pw_set(config['username'],config['password']);client.will_set(base+'/availability','offline',qos=1,retain=True)
 client.will_set(base+'/read_availability','offline',qos=1,retain=True)
 if config.get('ssl'):client.tls_set()
 connected=threading.Event();read_ready=threading.Event()
 latest_queue_status='En attente du serveur'
 def publish_result(key,ok,detail):
  if connected.is_set():
   client.publish(base+'/command_result',json.dumps({'key':key,'ok':ok,'detail':detail},ensure_ascii=False),retain=False)
 def publish_queue_status(value=None):
  nonlocal latest_queue_status
  if value is not None:latest_queue_status=value
  if connected.is_set():client.publish(base+'/command_queue/state',latest_queue_status,qos=0,retain=False)
 latest_active_zones=None
 latest_air_mode=None
 def publish_discovery(active_zones=None,air_mode=None):
  configs=discovery(identity,active_zones,air_mode,config.get('name','Aldes Pilot'))
  for topic,cfg in configs.items():client.publish(topic,json.dumps(cfg),qos=1,retain=True)
  client.publish(f'homeassistant/sensor/{identity}/command_queue/config',b'',qos=1,retain=True)
  if active_zones is not None:
   active_topics=set(configs)
   for topic in zone_discovery_topics(identity):
    if topic not in active_topics:client.publish(topic,b'',qos=1,retain=True)
 def connect(c,u,flags,reason,props):
  if reason.is_failure:return
  connected.set();c.publish(base+'/availability','offline',qos=1,retain=True);c.publish(base+'/read_availability','offline',qos=1,retain=True)
  publish_queue_status()
  publish_discovery(latest_active_zones,latest_air_mode);c.subscribe(base+'/+/set',qos=0);c.subscribe('homeassistant/status',qos=0)
 def disconnect(*args):
  connected.clear();read_ready.clear()
 def message(c,u,m):
  if m.topic=='homeassistant/status':
   if m.payload==b'online':publish_discovery(latest_active_zones,latest_air_mode)
   return
  parts=m.topic.split('/')
  if len(parts)!=4 or '/'.join(parts[:2])!=base or parts[3]!='set':return
  try:path,body=parse_command(parts[2],m.payload,m.retain)
  except (ValueError,UnicodeError) as exc:
   publish_result(parts[2],False,str(exc))
   return
  if not connected.is_set() or not read_ready.is_set():
   publish_result(parts[2],False,'Lecture PAC indisponible ; commande non mise en file')
   return
  try:answer=api(path,body)
  except (OSError,TimeoutError) as exc:
   publish_result(parts[2],False,'Serveur local indisponible : '+type(exc).__name__)
   return
  if not answer.get('ok'):
   publish_result(parts[2],False,answer.get('error','Commande refusée'))
   return
  detail='Commande '+('mise à jour dans la file serveur' if answer.get('replaced') else 'acceptée dans la file serveur')
  publish_result(parts[2],True,detail)
  publish_queue_status(f"En attente serveur · {answer.get('key',parts[2])}")
 client.on_connect=connect;client.on_disconnect=disconnect;client.on_message=message
 client.connect_async(config['host'],int(config['port']),keepalive=20);client.loop_start()
 try:
  while True:
   values=None;state=None
   try:
    state=api('/api/state');values=observed(state)
   except Exception:pass
   if connected.is_set():
    if state is not None:publish_queue_status(queue_status(state.get('command_queue')))
    if values is not None:
     read_ready.set()
     zones=active_zone_ids(state)
     air_mode=state.get('air',{}).get('actual')
     if zones!=latest_active_zones or air_mode!=latest_air_mode:
      latest_active_zones=zones
      latest_air_mode=air_mode
      publish_discovery(zones,air_mode)
     for key,value in values.items():client.publish(base+'/'+key+'/state',value,qos=0,retain=False)
     client.publish(base+'/read_availability','online',qos=1,retain=True)
    client.publish(base+'/availability','online',qos=1,retain=True)
   else:
     read_ready.clear()
     client.publish(base+'/read_availability','offline',qos=1,retain=True)
     client.publish(base+'/availability','offline',qos=1,retain=True)
   time.sleep(4)
 finally:
  client.publish(base+'/availability','offline',qos=1,retain=True)
  client.publish(base+'/read_availability','offline',qos=1,retain=True).wait_for_publish(timeout=2)
  client.disconnect();client.loop_stop()
if __name__=='__main__':main()
