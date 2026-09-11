"""HA Supervisor entrypoint. Credentials remain in /data, never in the image."""
import json,os,re,secrets,sys,time,urllib.request
from pathlib import Path

def main():
 os.umask(0o077)
 opts=json.loads(Path('/data/options.json').read_text())
 host=opts['pico_host'].strip();token=opts['control_token'].strip()
 if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]{0,252}',host) or not re.fullmatch(r'[0-9a-fA-F]{64}',token):raise SystemExit('Renseignez pico_host et le token de contrôle (64 caractères hexadécimaux).')
 private=Path('/data/private');private.mkdir(exist_ok=True)
 private.joinpath('control.token').write_text(token+'\n')
 ident=private/'mqtt-id';
 if not ident.exists():ident.write_text('aldes_'+secrets.token_hex(8))
 mqtt=None
 # Broker may be starting; bounded wait, Supervisor restart can try again.
 for _ in range(30):
  try:
   req=urllib.request.Request('http://supervisor/services/mqtt',headers={'Authorization':'Bearer '+os.environ['SUPERVISOR_TOKEN']})
   with urllib.request.urlopen(req,timeout=5) as r:data=json.load(r)
   if data.get('result')=='ok':mqtt=data['data'];break
  except Exception:pass
  time.sleep(2)
 if mqtt is None:raise SystemExit('Service MQTT indisponible : démarrer Mosquitto et activer MQTT dans Home Assistant.')
 private.joinpath('mqtt.json').write_text(json.dumps({**mqtt,'id':ident.read_text()}))
 private.joinpath('service.json').write_text(json.dumps({'PICO_HOST':host,'PICO_TOKEN':str(private/'control.token'),'MQTT_CONFIG':str(private/'mqtt.json'),'PILOT_INGRESS':'1'}))
 os.execv(sys.executable,[sys.executable,'/app/supervisor.py'])
if __name__=='__main__':main()
