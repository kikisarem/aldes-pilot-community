"""Supervise exactly one collector and web process; never issue PAC commands."""
import fcntl,os,signal,subprocess,sys,time
from pathlib import Path
root=Path(__file__).resolve().parent
children={};stopping=False
parent_pid=os.getppid()

def stop(*args):
 global stopping
 stopping=True

signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
(root/'private').mkdir(exist_ok=True)
with (root/'private/service.lock').open('a') as lock:
 try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:raise SystemExit('Service already running')
 import json
 env=os.environ.copy();env.update(json.loads((root/'private/service.json').read_text()));env['PICO_CAPTURE']=str(root/'private/pico.log')
 host=env.get('PICO_HOST','127.0.0.1')
 commands={'recovery':[sys.executable,str(root/'recovery.py')],
           'collector':[sys.executable,str(root/'collector.py'),'--host',host,'--log',env['PICO_CAPTURE']],
           'web':[sys.executable,'-m','uvicorn','app:app','--host','0.0.0.0','--port','8771','--log-level','warning']}
 if env.get('MQTT_CONFIG'):commands['mqtt']=[sys.executable,str(root/'mqtt_bridge.py')]
 try:
  while not stopping:
   if os.getppid()!=parent_pid:break
   for name,cmd in commands.items():
    p=children.get(name)
    if p is None or p.poll() is not None:
     children[name]=subprocess.Popen(cmd,cwd=root,env=env)
     print(name,'started',children[name].pid,flush=True)
   time.sleep(3)
 finally:
  for p in children.values():
   if p.poll() is None:p.terminate()
  for p in children.values():
   try:p.wait(timeout=15)
   except subprocess.TimeoutExpired:p.kill();p.wait()
