import tempfile,unittest,time,os,threading
from pathlib import Path
from unittest.mock import patch
from pico import Pilot,frame_vacation_clear,frame_air,frame_ecs,frame_modes,frame_setpoint,frame_setpoints
from test_reader import chunk,status
from readback import read_state

class IntegrationTests(unittest.TestCase):
 def frame(self,air=0,ecs=1,k1=2200,k9=0,temp9=0):
  f=bytearray(90);f[:5]=bytes.fromhex('fffd5aff21');f[13:15]=k1.to_bytes(2,'little')
  for i,value in enumerate((2150,2143,2125,2212)):f[53+2*i:55+2*i]=value.to_bytes(2,'little')
  f[13+2*8:15+2*8]=k9.to_bytes(2,'little')
  f[53+2*8:55+2*8]=temp9.to_bytes(2,'little')
  f[81]=air;f[82]=ecs;f[-2]=254;f[-1]=-sum(f)%256;return f
 def log(self,path,frame):
  path.write_text('[collector] test\n'+status(900)+chunk(1,1000,frame[:64])+chunk(2,1001,frame[64:])+status(1002))
 def test_external_changes_and_no_network(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'capture';self.log(path,self.frame())
   with patch('pico._find_capture',return_value=path),patch('socket.create_connection',side_effect=AssertionError('GET must not connect')):
    p=Pilot(Path(d)/'private');s=p.state();self.assertEqual(s['air']['actual'],0)
    self.log(path,self.frame(air=4,ecs=2,k1=2400));s=p.state()
    self.assertEqual(s['air']['actual'],4);self.assertEqual(s['ecs']['actual'],2);self.assertEqual(s['zones'][1]['actual'],24)
    self.assertEqual(s['zones'][1]['temperature_candidate_c'],21.5)
    self.assertEqual(s['zones'][4]['temperature_candidate_c'],22.12)
    self.assertTrue(s['zones'][1]['active'])
    self.assertFalse(s['zones'][5]['active'])
    self.log(path,self.frame(k9=1900,temp9=1850))
    s=p.state()
    self.assertTrue(s['zones'][9]['active'])
    self.assertEqual(s['zones'][9]['actual'],19)
    self.assertEqual(s['zones'][9]['temperature_candidate_c'],18.5)
    self.assertEqual(len(s['zones']),9)
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
   path=Path(d)/'capture';self.log(path,self.frame());state=read_state(path);self.assertTrue(state['available'])
   self.assertEqual(state['pages'][0]['opcode'],'21')
   self.assertTrue(state['pages'][0]['available'])
   path.write_text('');self.assertFalse(read_state(path)['available'])
   self.log(path,self.frame(air=8));self.assertEqual(read_state(path)['decoded']['air']['raw'],8)
 def test_command_masks(self):
  f=frame_vacation_clear();self.assertEqual(f[5:13],bytes(8));self.assertEqual(f[13:21],b'\xff'*8);self.assertEqual(f[81:83],b'\xff\xff');self.assertEqual(sum(f)%256,0)
  f=frame_setpoint(1,22);self.assertEqual(f[13:15],(2200).to_bytes(2,'little'))
  self.assertEqual(frame_setpoint(1,0)[13:15],b'\x00\x00')
  self.assertEqual(frame_setpoint(4,31)[19:21],(3100).to_bytes(2,'little'))
  with self.assertRaises(ValueError):frame_setpoint(1,22.5)
  for mode in (1,2,3,4):
   self.assertEqual(frame_setpoint(1,24,mode)[13:15],(2400).to_bytes(2,'little'))
   with self.assertRaises(ValueError):frame_setpoint(1,25,mode)
  for mode in (5,6,7,8):
   self.assertEqual(frame_setpoint(1,22,mode)[13:15],(2200).to_bytes(2,'little'))
   with self.assertRaises(ValueError):frame_setpoint(1,21,mode)
  self.assertEqual(frame_setpoint(1,0,5)[13:15],b'\x00\x00')
  for invalid in (1,15,32):
   with self.assertRaises(ValueError):frame_setpoint(1,invalid)
  combined=frame_setpoints({1:20,2:21,4:24},1)
  self.assertEqual(combined[13:21],(2000).to_bytes(2,'little')+(2100).to_bytes(2,'little')+b'\xff\xff'+(2400).to_bytes(2,'little'))
  self.assertEqual(sum(combined)%256,0)
  with self.assertRaises(ValueError):frame_setpoints({1:20,2:25},1)
  with self.assertRaises(ValueError):frame_setpoints({1:20.5},1)
  for mode in range(9):
   f=frame_air(mode);self.assertEqual(f[81],mode);self.assertEqual(f[5:13],b'\xff'*8);self.assertEqual(f[82],255);self.assertEqual(sum(f)%256,0)
  for mode in range(3):
   f=frame_ecs(mode);self.assertEqual(f[82],mode);self.assertEqual(f[81],255);self.assertEqual(sum(f)%256,0)
  combined_modes=frame_modes(air=0,ecs=0)
  self.assertEqual(combined_modes[81:83],b'\x00\x00')
  self.assertEqual(sum(combined_modes)%256,0)
  with self.assertRaises(ValueError):frame_modes()
 def test_send_rejects_setpoint_outside_current_air_mode_range(self):
  with tempfile.TemporaryDirectory() as d:
   p=Pilot(Path(d)/'private')
   state={'available':True,'recovery':{'status':'ready'},'cooldown_s':0,
          'air':{'actual':1},'health':{}}
   with patch.object(p,'state',return_value=state),patch.object(p.wb,'transact') as transact:
    with self.assertRaisesRegex(ValueError,'16–24'):
     p.send('setpoint',25,1)
    transact.assert_not_called()
 def test_send_setpoints_uses_one_combined_usb_frame(self):
  with tempfile.TemporaryDirectory() as d:
   p=Pilot(Path(d)/'private')
   state={'available':True,'recovery':{'status':'ready'},'cooldown_s':0,
          'air':{'actual':1},'health':{}}
   with patch.object(p,'state',return_value=state),patch.object(p.wb,'transact',return_value={'txid':3,'elapsed_s':2}) as transact:
    result=p.send_setpoints({1:20,2:21,4:24})
   self.assertTrue(result['ok'])
   self.assertEqual(result['zones'],[1,2,4])
   transact.assert_called_once()
   frame=transact.call_args.args[0]
   self.assertEqual(frame[13:21],(2000).to_bytes(2,'little')+(2100).to_bytes(2,'little')+b'\xff\xff'+(2400).to_bytes(2,'little'))
   journal=[__import__('json').loads(line) for line in p.journal_path.read_text().splitlines()]
   self.assertEqual([(row['event'],row.get('zone'),row.get('value')) for row in journal if row['event'] in ('request','delivered')],
                    [('request',1,20),('request',2,21),('request',4,24),('delivered',1,20),('delivered',2,21),('delivered',4,24)])
 def test_send_modes_uses_one_combined_usb_frame(self):
  with tempfile.TemporaryDirectory() as d:
   p=Pilot(Path(d)/'private')
   state={'available':True,'recovery':{'status':'ready'},'cooldown_s':0,'health':{}}
   with patch.object(p,'state',return_value=state),patch.object(p.wb,'transact',return_value={'txid':4,'elapsed_s':2}) as transact:
    result=p.send_modes({'air':0,'ecs':0})
   self.assertTrue(result['ok'])
   self.assertEqual(result['modes'],{'air':0,'ecs':0})
   transact.assert_called_once()
   frame=transact.call_args.args[0]
   self.assertEqual(frame[81:83],b'\x00\x00')
   self.assertEqual(sum(frame)%256,0)
   journal=[__import__('json').loads(line) for line in p.journal_path.read_text().splitlines()]
   self.assertEqual([(row['event'],row['kind'],row['value']) for row in journal if row['event'] in ('request','delivered')],
                    [('request','air',0),('request','ecs',0),('delivered','air',0),('delivered','ecs',0)])
 def test_setpoint_queue_batches_zones_after_shared_five_second_debounce(self):
  with tempfile.TemporaryDirectory() as d:
   p=Pilot(Path(d)/'private')
   p.setpoint_debounce=0.05
   state={'available':True,'recovery':{'status':'ready'},'cooldown_s':0,'busy':None}
   sent=threading.Event()
   with patch.object(p,'state',return_value=state),patch.object(p,'send_setpoints',side_effect=lambda values:(sent.set() or {'ok':True})):
    p.enqueue('setpoint',20,1)
    p.enqueue('setpoint',21,2)
    self.assertTrue(sent.wait(1))
    deadline=time.monotonic()+1
    while p.command_queue_state()['current'] is not None and time.monotonic()<deadline:
     time.sleep(0.01)
   queue=p.command_queue_state()
   self.assertEqual(queue['current'],None)
   self.assertEqual(queue['result']['status'],'delivered')
   self.assertEqual(queue['result']['value'],{1:20,2:21})
 def test_mode_queue_batches_air_and_ecs_after_shared_debounce(self):
  with tempfile.TemporaryDirectory() as d:
   p=Pilot(Path(d)/'private')
   p.mode_debounce=0.05
   state={'available':True,'recovery':{'status':'ready'},'cooldown_s':0,'busy':None}
   sent=threading.Event()
   with patch.object(p,'state',return_value=state),patch.object(p,'send_modes',side_effect=lambda values:(sent.set() or {'ok':True})):
    p.enqueue('air',0)
    p.enqueue('ecs',0)
    self.assertTrue(sent.wait(1))
    deadline=time.monotonic()+1
    while p.command_queue_state()['current'] is not None and time.monotonic()<deadline:
     time.sleep(0.01)
   queue=p.command_queue_state()
   self.assertEqual(queue['current'],None)
   self.assertEqual(queue['result']['status'],'delivered')
   self.assertEqual(queue['result']['key'],'batch:air+ecs')
   self.assertEqual(queue['result']['value'],{'air':0,'ecs':0})
 def test_ui_queue_coalesces_zone_setpoints(self):
  with tempfile.TemporaryDirectory() as d:
   p=Pilot(Path(d)/'private')
   p.queue_debounce=60
   first=p.enqueue('setpoint',20,1)
   latest=p.enqueue('setpoint',19,1)
   self.assertTrue(first['queued'])
   self.assertTrue(latest['replaced'])
   self.assertEqual(p.command_queue_state()['pending']['k1']['value'],19)
if __name__=='__main__':unittest.main()
