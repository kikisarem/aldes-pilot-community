"""Generate the add-on build context from reviewed application sources (no secrets)."""
import hashlib,json,shutil
from pathlib import Path
r=Path(__file__).resolve().parent.parent;out=r/'homeassistant/addon/source';out.mkdir(exist_ok=True)
names=['LICENSE','NOTICE','THIRD_PARTY.md','USAGE.md','app.py','pico.py','index.html','logs.html','manifest.json','reader.py','raw_audit.py','report21.py','report_clock.py','readback.py','collector.py','supervisor.py','recovery.py','usbguard.py','mqtt_bridge.py','requirements.txt','icon-192.png','icon-512.png']
for p in out.iterdir():
 if p.is_file() and p.name not in names and p.name!='SOURCE-HASHES.json':p.unlink()
for name in names:shutil.copy2(r/name,out/name)
(out/'SOURCE-HASHES.json').write_text(json.dumps({n:hashlib.sha256((r/n).read_bytes()).hexdigest() for n in names},indent=2)+'\n')
addon=r/'homeassistant/addon'
shutil.copy2(r/'homeassistant/docker/container_run.py',addon/'container_run.py')
mirror=r/'aldes_pilot';mirror.mkdir(exist_ok=True)
for name in ('config.yaml','Dockerfile','run.py','container_run.py','.dockerignore'):
 shutil.copy2(addon/name,mirror/name)
mirror_source=mirror/'source';mirror_source.mkdir(exist_ok=True)
mirror_names=set(names)|{'SOURCE-HASHES.json'}
for p in mirror_source.iterdir():
 if p.is_file() and p.name not in mirror_names:p.unlink()
for name in mirror_names:
 shutil.copy2(out/name,mirror_source/name)
print('Add-on context generated; sources only, no private config.')
