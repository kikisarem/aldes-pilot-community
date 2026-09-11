import tempfile,unittest,time,os
from pathlib import Path
from unittest.mock import patch
from pico import Pilot,frame_vacation_clear,frame_air,frame_ecs
from test_reader import chunk,status
from readback import read_state

class IntegrationTests(unittest.TestCase):
 def frame(self,air=0,ecs=1,k1=2200):
  f=bytearray(90);f[:5]=bytes.fromhex('fffd5aff21');f[13:15]=k1.to_bytes(2,'little');f[81]=air;f[82]=ecs;f[-2]=254;f[-1]=-sum(f)%256;return f
 def log(self,path,frame):
  path.write_text('[collector] test\n'+chunk(1,1000,frame[:64])+chunk(2,1001,frame[64:])+status(1002))
 def test_external_changes_and_no_network(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'capture';self.log(path,self.frame())
   with patch('pico._find_capture',return_value=path),patch('socket.create_connection',side_effect=AssertionError('GET must not connect')):
    p=Pilot(Path(d)/'private');s=p.state();self.assertEqual(s['air']['actual'],0)
    self.log(path,self.frame(air=4,ecs=2,k1=2400));s=p.state()
    self.assertEqual(s['air']['actual'],4);self.assertEqual(s['ecs']['actual'],2);self.assertEqual(s['zones'][1]['actual'],24)
    self.assertIsNone(s['air']['requested']);self.assertFalse(p.journal_path.exists())
    os.utime(path,(time.time()-90,time.time()-90));s=p.state();self.assertFalse(s['available']);self.assertIsNone(s['air']['actual'])
 def test_historical_failure_is_not_current_state(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'capture';self.log(path,self.frame(air=1,ecs=1))
   with patch('pico._find_capture',return_value=path):
    p=Pilot(Path(d)/'private')
    p._journal(event='error',kind='ecs',zone=None,value=1,utc=time.time()-86400)
    p._journal(event='delivered',kind='air',zone=None,value=0,utc=time.time()-86400)
    s=p.state()
    self.assertTrue(s['ecs']['matches_request'])
    self.assertEqual(s['ecs']['status'],'observed')
    self.assertEqual(s['ecs']['delivery_status'],'error')
    self.assertFalse(s['air']['matches_request'])
    self.assertEqual(s['air']['status'],'observed')
    self.assertEqual(s['observation'],s['observed'])
    self.assertIsNotNone(s['observation']['age_s'])
 def test_truncation_and_replacement(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'capture';self.log(path,self.frame());self.assertTrue(read_state(path)['available'])
   path.write_text('');self.assertFalse(read_state(path)['available'])
   self.log(path,self.frame(air=8));self.assertEqual(read_state(path)['decoded']['air']['raw'],8)
 def test_command_masks(self):
  f=frame_vacation_clear();self.assertEqual(f[5:13],bytes(8));self.assertEqual(f[13:21],b'\xff'*8);self.assertEqual(f[81:83],b'\xff\xff');self.assertEqual(sum(f)%256,0)
  for mode in range(9):
   f=frame_air(mode);self.assertEqual(f[81],mode);self.assertEqual(f[5:13],b'\xff'*8);self.assertEqual(f[82],255);self.assertEqual(sum(f)%256,0)
  for mode in range(3):
   f=frame_ecs(mode);self.assertEqual(f[82],mode);self.assertEqual(f[81],255);self.assertEqual(sum(f)%256,0)
if __name__=='__main__':unittest.main()
