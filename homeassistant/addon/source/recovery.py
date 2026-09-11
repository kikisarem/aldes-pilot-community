"""Bounded report recovery. Only five known 8-byte control messages, no settings."""
import fcntl,json,os,time
from pathlib import Path
from reader import snapshot
from pico import ROOT,Workbench,_find_capture

COMMANDS={'20':'fdfa08ff4020fea4','25':'fdfa08ff4525fe9a','26':'fdfa08ff4626fe98','27':'fdfa08ff4727fe96','28':'fdfa08ff4828fe94'}

def observe(path,now):
 with path.open('rb') as f:
  st=os.fstat(f.fileno());start=max(0,st.st_size-250000);f.seek(start)
  if start:f.readline()
  raw=f.read(250000)
 data=snapshot(raw,st.st_mtime,now);op=data['active_report'];page=data['pages'].get(op,{})
 return {'opcode':op,'fresh':bool(page.get('available')),'age':page.get('age_seconds'),'tick':page.get('uptime_ms')}

class Recovery:
 def __init__(self,state=None):
  self.s=state or {'status':'watching','used':[],'attempts':[],'last_tick':None,'good':[]}
 def decide(self,o,now):
  s=self.s;tick=o.get('tick')
  if not o.get('fresh') or tick is None:return None
  # Only a decrease in fresh device uptime starts a new boot budget.
  if s.get('last_tick') is not None and tick<s['last_tick']:
   s.update(status='watching',used=[],good=[],started=None,reason=None)
  s['last_tick']=tick
  if o['opcode']=='21':
   good=s.setdefault('good',[])
   if tick not in good:good.append(tick)
   s['good']=good[-3:]
   if len(s['good'])==3:s.update(status='ready',used=[],started=None,reason=None)
   return None
  s['good']=[]
  if s['status']=='blocked':return None
  if s['status']=='ready':s.update(status='watching',used=[],started=None)
  if o['opcode'] not in COMMANDS:
   s.update(status='blocked',reason='Page inattendue : intervention nécessaire');return None
  if s.get('started') is not None and not 0<=now-s['started']<=600:
   s.update(status='blocked',reason='Délai de reprise dépassé');return None
  if o['opcode'] in s['used']:return None
  if o.get('age') is None or not 0<=o['age']<=1.5:return None
  attempts=[t for t in s['attempts'] if now-t<3600]
  if len(attempts)>=10 or len(s['used'])>=5:
   s.update(status='blocked',reason='Limite de reprise atteinte');return None
  # Persist this reservation before touching the network: crash cannot replay it.
  s['attempts']=attempts+[now];s['used'].append(o['opcode'])
  s.update(status='recovering',started=s.get('started') or now,reason=None,last_action=now)
  return bytes.fromhex(COMMANDS[o['opcode']])

def save(path,state):
 temp=path.with_suffix('.tmp')
 with temp.open('w') as f:json.dump(state,f);f.flush();os.fsync(f.fileno())
 temp.replace(path)

def main():
 path=ROOT/'private/recovery.json'
 with (ROOT/'private/recovery.lock').open('a') as own:
  fcntl.flock(own,fcntl.LOCK_EX|fcntl.LOCK_NB)
  try:state=json.loads(path.read_text())
  except FileNotFoundError:state=None
  engine=Recovery(state)
  while True:
   try:
    with (ROOT/'private/tx.lock').open('a') as lock:
     try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
     except BlockingIOError:time.sleep(1);continue
     o=observe(_find_capture(),time.time())
     before=json.dumps(engine.s,sort_keys=True)
     frame=engine.decide(o,time.time())
     if json.dumps(engine.s,sort_keys=True)!=before:save(path,engine.s)
     if frame is not None:
      def journal(**row):
       with (ROOT/'private/recovery-events.jsonl').open('a') as f:
        f.write(json.dumps({'utc':time.time(),'page':o['opcode'],**row})+'\n');f.flush();os.fsync(f.fileno())
      journal(event='reserved',hex=frame.hex())
      def guard():
       current=observe(_find_capture(),time.time())
       if not current['fresh'] or current['opcode']!=o['opcode'] or current['tick']!=o['tick']:
        raise RuntimeError('Report changed before SEND')
      try:Workbench().transact(frame,journal,pre_send=guard)
      except Exception as exc:
       engine.s.update(status='blocked',reason='Transport non confirmé : intervention nécessaire');save(path,engine.s)
       journal(event='error',error=str(exc))
   except (OSError,ValueError,KeyError) as exc:
    # Never send on malformed, absent or stale data; retain the attempt budget.
    pass
   time.sleep(.25)

if __name__=='__main__':main()
