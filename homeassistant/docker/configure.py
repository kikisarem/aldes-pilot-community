"""Configure REST by default; MQTT remains optional."""
import getpass,json,os,re,secrets
from pathlib import Path
os.umask(0o077)
p=Path(__file__).resolve().parent/'private'
p.mkdir(exist_ok=True)
host=input('Adresse du Pico : ').strip()
token=getpass.getpass('Token de contrôle Pico : ').strip()
if not host or not re.fullmatch(r'[a-zA-Z0-9.:-]+',host):raise SystemExit('Adresse Pico invalide.')
if not re.fullmatch(r'[0-9a-fA-F]{64}',token):raise SystemExit('Token : 64 caractères hexadécimaux attendus.')
p.joinpath('control.token').write_text(token+'\n')
service={'PICO_HOST':host,'PICO_TOKEN':'/data/private/control.token'}
if input('Utiliser MQTT plutôt que REST ? [o/N] : ').lower()=='o':
 ident=p/'mqtt-id'
 if not ident.exists():ident.write_text('aldes_'+secrets.token_hex(8))
 mqtt={'id':ident.read_text(),'host':input('Hôte MQTT : ').strip(),'port':int(input('Port MQTT [1883] : ') or '1883'),'username':input('Utilisateur MQTT : '),'password':getpass.getpass('Mot de passe MQTT : '),'ssl':input('MQTT TLS ? [o/N] : ').lower()=='o'}
 p.joinpath('mqtt.json').write_text(json.dumps(mqtt))
 service['MQTT_CONFIG']='/data/private/mqtt.json'
p.joinpath('service.json').write_text(json.dumps(service))
print('Configuration privée écrite. Voir ../README.md avant de démarrer : un seul collecteur par Pico.')
