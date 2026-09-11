"""HA MQTT discovery and observed state. Never retain/retry a PAC command."""
import json,math,os,threading,time,urllib.request
from pathlib import Path
AIR=['Arrêt','Chauffage Confort','Chauffage Éco','Chauffage Programme A','Chauffage Programme B','Clim Confort','Clim Boost','Clim Programme C','Clim Programme D']
ECS=['Arrêt','Marche','Boost']
def discovery(identity):
 base='aldes_pilot/'+identity
 device={'identifiers':[identity],'name':'Aldes Pilot','manufacturer':'Communauté','model':'Bridge USB Pico W'}
 rows=[]
 for key,options in [('air',AIR),('ecs',ECS)]:
  rows.append(('select',key,{'name':'Mode '+key.upper(),'options':options,'optimistic':False}))
 for zone in range(1,5):rows.append(('number','k'+str(zone),{'name':f'Consigne K{zone}','min':16,'max':30,'step':.5,'mode':'box','unit_of_measurement':'°C','optimistic':False}))
 rows.append(('button','vacation_clear',{'name':'Annuler vacances / hors gel','payload_press':'CLEAR'}))
 result={}
 for component,key,extra in rows:
  cfg={'unique_id':identity+'_'+key,'device':device,'availability_topic':base+'/availability','command_topic':base+'/'+key+'/set','qos':0,'retain':False,**extra}
  if component!='button':cfg['state_topic']=base+'/'+key+'/state'
  result[f'homeassistant/{component}/{identity}/{key}/config']=cfg
 return result

def parse_command(key,payload,retained=False):
 if retained or len(payload)>100:raise ValueError('Retained/oversized command refused')
 value=payload.decode('utf-8')
 if key in ('air','ecs'):
  values=AIR if key=='air' else ECS
  if value not in values:raise ValueError('Unknown mode')
  return '/api/'+key,{'mode':values.index(value)}
 if key in ('k1','k2','k3','k4'):
  v=float(value)
  if not math.isfinite(v) or not 16<=v<=30 or v*2!=int(v*2):raise ValueError('Invalid setpoint')
  return '/api/setpoint',{'zone':int(key[1]),'temperature':v}
 if key=='vacation_clear' and value=='CLEAR':return '/api/vacation/clear',{}
 raise ValueError('Unknown command')

def observed(s):
 if not s.get('available') or s.get('busy') or s.get('cooldown_s',0)>0 or s.get('recovery',{}).get('status')=='recovering':return None
 a=s['air']['actual'];e=s['ecs']['actual']
 if type(a)!=int or type(e)!=int or not 0<=a<len(AIR) or not 0<=e<len(ECS):return None
 out={'air':AIR[a],'ecs':ECS[e]}
 for z in range(1,5):
  v=s['zones'][str(z)]['actual']
  if not isinstance(v,(int,float)) or not math.isfinite(v):return None
  out['k'+str(z)]=str(v)
 return out

def api(path,body=None):
 request=urllib.request.Request('http://127.0.0.1:8771'+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json','x-pilot-ui':'1','x-pilot-pin':os.environ.get('PILOT_PIN','')})
 with urllib.request.urlopen(request,timeout=100 if body is not None else 5) as r:return json.load(r)

def main():
 import paho.mqtt.client as mqtt
 config=json.loads(Path(os.environ['MQTT_CONFIG']).read_text());identity=config['id'];base='aldes_pilot/'+identity
 client=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id=identity,clean_session=True)
 client.username_pw_set(config['username'],config['password']);client.will_set(base+'/availability','offline',qos=1,retain=True)
 if config.get('ssl'):client.tls_set()
 connected=threading.Event();command_lock=threading.Lock();fresh_until=0.0
 def publish_discovery():
  for topic,cfg in discovery(identity).items():client.publish(topic,json.dumps(cfg),qos=1,retain=True)
 def connect(c,u,flags,reason,props):
  nonlocal fresh_until
  fresh_until=0
  if reason.is_failure:return
  connected.set();c.publish(base+'/availability','offline',qos=1,retain=True)
  publish_discovery();c.subscribe(base+'/+/set',qos=0);c.subscribe('homeassistant/status',qos=0)
 def disconnect(*args):
  nonlocal fresh_until
  fresh_until=0;connected.clear()
 def run_command(path,body):
  nonlocal fresh_until
  try:
   # Recheck immediately; no queue, no replay after an offline interval.
   if not connected.is_set() or observed(api('/api/state')) is None:return
   answer=api(path,body)
   client.publish(base+'/command_result',json.dumps({'ok':bool(answer.get('ok')),'detail':answer.get('error','Envoyée ; attendre le rapport PAC')}),retain=False)
  except Exception as exc:
   client.publish(base+'/command_result',json.dumps({'ok':False,'detail':type(exc).__name__}),retain=False)
  finally:fresh_until=0;command_lock.release()
 def message(c,u,m):
  nonlocal fresh_until
  if m.topic=='homeassistant/status':
   if m.payload==b'online':publish_discovery()
   return
  parts=m.topic.split('/')
  if len(parts)!=4 or '/'.join(parts[:2])!=base or parts[3]!='set':return
  try:path,body=parse_command(parts[2],m.payload,m.retain)
  except (ValueError,UnicodeError):return
  if time.monotonic()>fresh_until or not connected.is_set() or not command_lock.acquire(blocking=False):return
  fresh_until=0;c.publish(base+'/availability','offline',qos=1,retain=True)
  threading.Thread(target=run_command,args=(path,body),daemon=True).start()
 client.on_connect=connect;client.on_disconnect=disconnect;client.on_message=message
 client.connect_async(config['host'],int(config['port']),keepalive=20);client.loop_start()
 try:
  while True:
   values=None
   try:values=observed(api('/api/state'))
   except Exception:pass
   if connected.is_set():
    if values is not None and not command_lock.locked():
     for key,value in values.items():client.publish(base+'/'+key+'/state',value,qos=0,retain=False)
     fresh_until=time.monotonic()+6;client.publish(base+'/availability','online',qos=1,retain=True)
    else:fresh_until=0;client.publish(base+'/availability','offline',qos=1,retain=True)
   time.sleep(4)
 finally:
  client.publish(base+'/availability','offline',qos=1,retain=True).wait_for_publish(timeout=2);client.disconnect();client.loop_stop()
if __name__=='__main__':main()
