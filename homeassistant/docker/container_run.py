"""Standalone HA Container companion; prepare private/service.json and mqtt.json."""
import os,sys,json
from pathlib import Path
p=Path('/data/private');os.umask(0o077)
s=json.loads((p/'service.json').read_text())
for key in ('PICO_HOST','PICO_TOKEN','MQTT_CONFIG'):
 if not s.get(key):raise SystemExit('Missing '+key+' in private/service.json')
# Container companion uses localhost-bound port; HA interacts through MQTT.
s.pop('PILOT_INGRESS',None)
(p/'service.json').write_text(json.dumps(s))
os.execv(sys.executable,[sys.executable,'/app/supervisor.py'])
