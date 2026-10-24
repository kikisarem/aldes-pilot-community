import unittest
from mqtt_bridge import discovery,active_zone_ids,zone_discovery_topics,parse_command,observed,queue_status,AIR,ECS
class MQTTTests(unittest.TestCase):
 def test_discovery_observed_and_commands_nonretained(self):
  d=discovery('test',range(1,10));self.assertEqual(len(d),21)
  for topic,c in d.items():
   self.assertFalse(c['retain']);self.assertEqual(c['qos'],0)
   self.assertEqual(c['availability_topic'],'aldes_pilot/test/read_availability')
   if '/button/' not in topic:self.assertIn('state_topic',c)
   if '/select/' in topic or '/number/' in topic:self.assertFalse(c['optimistic'])
  sensor=d['homeassistant/sensor/test/temperature_k1/config']
  self.assertEqual(sensor['device_class'],'temperature');self.assertEqual(sensor['unit_of_measurement'],'°C')
  self.assertEqual(sensor['availability_topic'],'aldes_pilot/test/read_availability')
  self.assertEqual(d['homeassistant/number/test/k1/config']['availability_topic'],'aldes_pilot/test/read_availability')
  self.assertEqual(d['homeassistant/number/test/k1/config']['step'],1)
  self.assertEqual(d['homeassistant/number/test/k1/config']['min'],0)
  self.assertEqual(d['homeassistant/number/test/k1/config']['max'],31)
  self.assertEqual(discovery('test',range(1,10),1)['homeassistant/number/test/k1/config']['max'],24)
  self.assertEqual(discovery('test',range(1,10),5)['homeassistant/number/test/k1/config']['max'],31)
  self.assertNotIn('homeassistant/sensor/test/command_queue/config',d)
  named=discovery('pac2',range(1,10),bridge_name='PAC étage')
  self.assertEqual(named['homeassistant/select/pac2/air/config']['device']['name'],'PAC étage')
  self.assertIn('homeassistant/sensor/test/temperature_k9/config',d)
  self.assertIn('homeassistant/sensor/test/setpoint_k9/config',d)
 def test_discovery_only_creates_entities_for_active_zones(self):
  d=discovery('test',{1,4,9})
  self.assertIn('homeassistant/number/test/k1/config',d)
  self.assertIn('homeassistant/number/test/k4/config',d)
  self.assertIn('homeassistant/sensor/test/temperature_k1/config',d)
  self.assertIn('homeassistant/sensor/test/temperature_k4/config',d)
  self.assertIn('homeassistant/sensor/test/temperature_k9/config',d)
  self.assertIn('homeassistant/sensor/test/setpoint_k9/config',d)
  self.assertNotIn('homeassistant/number/test/k2/config',d)
  self.assertNotIn('homeassistant/sensor/test/temperature_k2/config',d)
  self.assertNotIn('homeassistant/sensor/test/setpoint_k5/config',d)
  self.assertEqual(len(zone_discovery_topics('test')),18)
  self.assertEqual(active_zone_ids({'zones':{'1':{'active':True},'4':{'active':True},'9':{'active':True}}}),{1,4,9})
 def test_modes_and_programs(self):
  for i,label in enumerate(AIR):self.assertEqual(parse_command('air',label.encode()),('/api/queue/air',{'mode':i}))
  for i,label in enumerate(ECS):self.assertEqual(parse_command('ecs',label.encode()),('/api/queue/ecs',{'mode':i}))
 def test_refuse_retain_and_invalid(self):
  for key,payload,retained in [('air',b'Arr\xc3\xaAt',True),('k1',b'nan',False),('k2',b'32',False),('k3',b'15',False),('k3',b'20.5',False),('k5',b'22',False),('air',b'9',False),('vacation_clear',b'ON',False)]:
   with self.assertRaises(ValueError):parse_command(key,payload,retained)
 def test_states_are_actual_only(self):
  s={'available':True,'air':{'actual':5,'requested':0},'ecs':{'actual':1},'zones':{str(z):{'active':z in (1,9),'actual':24 if z==1 else 19,'temperature_candidate_c':21.5+z/100} for z in range(1,10)}}
  self.assertEqual(observed(s)['air'],'Clim Confort');self.assertEqual(observed(s)['k1'],'24')
  self.assertEqual(observed(s)['temperature_k1'],'21.51')
  self.assertEqual(observed(s)['k9'],'19')
  self.assertEqual(observed(s)['setpoint_k9'],'19')
  self.assertEqual(observed(s)['temperature_k9'],'21.59')
  self.assertEqual(observed(s)['k5'],'')
  s['busy']=True;s['cooldown_s']=40
  self.assertIsNotNone(observed(s))
  s['zones']['1']['temperature_candidate_c']=None
  self.assertEqual(observed(s)['temperature_k1'],'')
  s['available']=False;self.assertIsNone(observed(s))
  s['available']=True;s['recovery']={'status':'recovering'}
  self.assertIsNone(observed(s))
 def test_whole_degree_setpoints(self):
  self.assertEqual(parse_command('k4',b'22'),('/api/queue/setpoint',{'zone':4,'temperature':22.0}))
  self.assertEqual(parse_command('k1',b'0'),('/api/queue/setpoint',{'zone':1,'temperature':0.0}))
  self.assertEqual(parse_command('k2',b'31'),('/api/queue/setpoint',{'zone':2,'temperature':31.0}))
  self.assertEqual(parse_command('vacation_clear',b'CLEAR'),('/api/queue/vacation/clear',{}))
 def test_mqtt_displays_central_server_queue_state(self):
  self.assertEqual(queue_status({'pending':{},'current':'k2'}),'Envoi k2 · 0 en attente')
  self.assertEqual(queue_status({'pending':{},'current':'batch:k1+k2+k4'}),'Envoi groupé K1, K2, K4 · 0 en attente')
  self.assertEqual(queue_status({'pending':{},'current':'batch:air+ecs'}),'Envoi groupé mode air, ECS · 0 en attente')
  self.assertEqual(queue_status({'pending':{'k1':{},'ecs':{}},'current':None}),'2 en attente · k1, ecs')
  self.assertEqual(queue_status({'pending':{},'current':None,'result':{'status':'delivered'}}),'Repos · dernière commande transmise')
  self.assertEqual(queue_status({'pending':{},'current':None,'result':{'status':'error'}}),'Dernière commande en erreur')
if __name__=='__main__':unittest.main()
