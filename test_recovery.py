import unittest,json
from recovery import Recovery,COMMANDS
class RecoveryTests(unittest.TestCase):
 def o(self,op,tick,age=0,fresh=True):return dict(opcode=op,tick=tick,age=age,fresh=fresh)
 def test_reboot_path_only_controls(self):
  r=Recovery()
  for i,op in enumerate(['20','25','26','27','28']):
   frame=r.decide(self.o(op,1000+i*20000),100+i*20)
   self.assertEqual(len(frame),8);self.assertEqual(sum(frame)%256,0);self.assertNotEqual(frame[4],0x10)
   self.assertIsNone(r.decide(self.o(op,1001+i*20000),101+i*20))
  for tick in [101000,121000,141000]:self.assertIsNone(r.decide(self.o('21',tick),250))
  self.assertEqual(r.s['status'],'ready')
 def test_ready_never_sends(self):
  r=Recovery()
  for tick in range(100):self.assertIsNone(r.decide(self.o('21',tick),100))
 def test_stale_and_unknown(self):
  for op in COMMANDS:
   r=Recovery();self.assertIsNone(r.decide(self.o(op,1,fresh=False),10));self.assertIsNone(r.decide(self.o(op,1,age=2),10))
  r=Recovery();self.assertIsNone(r.decide(self.o('23',1),10));self.assertEqual(r.s['status'],'blocked')
 def test_restart_no_replay(self):
  r=Recovery();r.decide(self.o('20',1000),100)
  r=Recovery(json.loads(json.dumps(r.s)))
  self.assertIsNone(r.decide(self.o('20',2000),110))
 def test_timeout(self):
  r=Recovery();r.decide(self.o('20',1000),100)
  self.assertIsNone(r.decide(self.o('25',2000),701));self.assertEqual(r.s['status'],'blocked')
 def test_boot_reset_keeps_hourly_limit(self):
  r=Recovery()
  for i in range(10):
   self.assertIsNotNone(r.decide(self.o('20',10),100+i))
   r.s['last_tick']=1000
  self.assertIsNone(r.decide(self.o('20',10),120));self.assertEqual(r.s['status'],'blocked')
 def test_transport_failure_stays_blocked(self):
  r=Recovery();r.decide(self.o('20',1000),100);r.s['status']='blocked'
  self.assertIsNone(r.decide(self.o('25',2000),110))
if __name__=='__main__':unittest.main()
