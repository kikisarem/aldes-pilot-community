"""Configure REST by default; MQTT remains optional."""
import getpass,json,os,re,secrets
import argparse
from pathlib import Path
os.umask(0o077)
parser=argparse.ArgumentParser()
parser.add_argument('--instance',help='Instance identifier for an additional bridge (letters, digits, dash, underscore)')
args=parser.parse_args()
if args.instance and not re.fullmatch(r'[A-Za-z0-9_-]{1,32}',args.instance):
 raise SystemExit('Identifiant invalide : utilisez 1 à 32 lettres, chiffres, tirets ou underscores.')
root=Path(__file__).resolve().parent
instance_dir=root/'instances'/args.instance if args.instance else root
p=instance_dir/'private'
p.mkdir(parents=True,exist_ok=True)
(instance_dir/'logs').mkdir(exist_ok=True)
bridge_name=input('Nom de cette PAC dans Home Assistant [PAC principale] : ').strip() or 'PAC principale'
host=input('Adresse du Pico : ').strip()
token=getpass.getpass('Token de contrôle Pico : ').strip()
if not host or not re.fullmatch(r'[a-zA-Z0-9.:-]+',host):raise SystemExit('Adresse Pico invalide.')
if not re.fullmatch(r'[0-9a-fA-F]{64}',token):raise SystemExit('Token : 64 caractères hexadécimaux attendus.')
p.joinpath('control.token').write_text(token+'\n')
service={'PICO_HOST':host,'PICO_TOKEN':'/data/private/control.token'}
if input('Utiliser MQTT plutôt que REST ? [o/N] : ').lower()=='o':
 ident=p/'mqtt-id'
 if not ident.exists():ident.write_text('aldes_'+secrets.token_hex(8))
 mqtt={'id':ident.read_text(),'name':bridge_name,'host':input('Hôte MQTT : ').strip(),'port':int(input('Port MQTT [1883] : ') or '1883'),'username':input('Utilisateur MQTT : '),'password':getpass.getpass('Mot de passe MQTT : '),'ssl':input('MQTT TLS ? [o/N] : ').lower()=='o'}
 p.joinpath('mqtt.json').write_text(json.dumps(mqtt))
 service['MQTT_CONFIG']='/data/private/mqtt.json'
p.joinpath('service.json').write_text(json.dumps(service))
print(f'Configuration privée écrite pour {bridge_name}. Voir ../README.md avant de démarrer : un seul collecteur par Pico.')
