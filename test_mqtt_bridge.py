import unittest
from mqtt_bridge import discovery,parse_command,observed,AIR,ECS
class MQTTTests(unittest.TestCase):
 def test_discovery_observed_and_commands_nonretained(self):
  d=discovery('test');self.assertEqual(len(d),7)
  for topic,c in d.items():
   self.assertFalse(c['retain']);self.assertEqual(c['qos'],0);self.assertEqual(c['availability_topic'],'aldes_pilot/test/availability')
   if '/button/' not in topic:self.assertFalse(c['optimistic']);self.assertIn('state_topic',c)
 def test_modes_and_programs(self):
  for i,label in enumerate(AIR):self.assertEqual(parse_command('air',label.encode()),('/api/air',{'mode':i}))
  for i,label in enumerate(ECS):self.assertEqual(parse_command('ecs',label.encode()),('/api/ecs',{'mode':i}))
 def test_refuse_retain_and_invalid(self):
  for key,payload,retained in [('air',b'Arr\xc3\xaat',True),('k1',b'nan',False),('k2',b'31',False),('k3',b'20.1',False),('k5',b'22',False),('air',b'9',False),('vacation_clear',b'ON',False)]:
   with self.assertRaises(ValueError):parse_command(key,payload,retained)
 def test_states_are_actual_only(self):
  s={'available':True,'air':{'actual':5,'requested':0},'ecs':{'actual':1},'zones':{str(z):{'actual':24 if z==1 else 22} for z in range(1,5)}}
  self.assertEqual(observed(s)['air'],'Clim Confort');self.assertEqual(observed(s)['k1'],'24')
  s['available']=False;self.assertIsNone(observed(s));s['available']=True;s['recovery']={'status':'recovering'};self.assertIsNone(observed(s))
 def test_half_degrees(self):self.assertEqual(parse_command('k4',b'22.5'),('/api/setpoint',{'zone':4,'temperature':22.5}))
if __name__=='__main__':unittest.main()
