"""HA Supervisor entrypoint. Credentials remain in /data, never in the image."""
import json,os,re,secrets,sys
from pathlib import Path

def mqtt_config(opts,private):
 host=opts.get('mqtt_host','').strip()
 username=opts.get('mqtt_username','').strip()
 password=opts.get('mqtt_password','')
 port=opts.get('mqtt_port',1883)
 if not username and not password and host in ('','core-mosquitto') and not opts.get('mqtt_ssl',False):
  return None
 if not host or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]{0,252}',host):
  raise SystemExit('Renseignez un hôte MQTT valide, par exemple core-mosquitto.')
 if not isinstance(port,int) or isinstance(port,bool) or not 1<=port<=65535:
  raise SystemExit('Le port MQTT doit être compris entre 1 et 65535.')
 if bool(username)!=bool(password):
  raise SystemExit('Renseignez les deux identifiants MQTT, ou laissez-les tous les deux vides pour un broker sans authentification.')
 ident=private/'mqtt-id'
 if not ident.exists():ident.write_text('aldes_'+secrets.token_hex(8))
 config={'id':ident.read_text(),'name':opts.get('bridge_name','Aldes Pilot').strip() or 'Aldes Pilot',
         'host':host,'port':port,'username':username,'password':password,'ssl':bool(opts.get('mqtt_ssl',False))}
 path=private/'mqtt.json'
 path.write_text(json.dumps(config))
 return path

def main():
 os.umask(0o077)
 opts=json.loads(Path('/data/options.json').read_text())
 host=opts['pico_host'].strip();token=opts['control_token'].strip()
 if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]{0,252}',host) or not re.fullmatch(r'[0-9a-fA-F]{64}',token):raise SystemExit('Renseignez pico_host et le token de contrôle (64 caractères hexadécimaux).')
 private=Path('/data/private');private.mkdir(exist_ok=True)
 private.joinpath('control.token').write_text(token+'\n')
 mqtt_path=mqtt_config(opts,private)
 private.joinpath('service.json').write_text(json.dumps({'PICO_HOST':host,'PICO_TOKEN':str(private/'control.token'),'MQTT_CONFIG':str(mqtt_path) if mqtt_path else '','PILOT_INGRESS':'1'}))
 os.execv(sys.executable,[sys.executable,'/app/supervisor.py'])
if __name__=='__main__':main()
