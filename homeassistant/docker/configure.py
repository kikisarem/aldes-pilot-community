import getpass,json,os,re,secrets
from pathlib import Path
os.umask(0o077);p=Path(__file__).resolve().parent/'private';p.mkdir(exist_ok=True)
host=input('Adresse du Pico : ').strip();token=getpass.getpass('Token de contrôle Pico : ').strip()
if not re.fullmatch(r'[0-9a-fA-F]{64}',token):raise SystemExit('Token : 64 caractères hexadécimaux attendus.')
p.joinpath('control.token').write_text(token+'\n')
ident=p/'mqtt-id'
if not ident.exists():ident.write_text('aldes_'+secrets.token_hex(8))
mqtt={'id':ident.read_text(),'host':input('Hôte MQTT : ').strip(),'port':int(input('Port MQTT [1883] : ') or '1883'),'username':input('Utilisateur MQTT : '),'password':getpass.getpass('Mot de passe MQTT : '),'ssl':input('MQTT TLS ? [o/N] : ').lower()=='o'}
p.joinpath('mqtt.json').write_text(json.dumps(mqtt))
p.joinpath('service.json').write_text(json.dumps({'PICO_HOST':host,'PICO_TOKEN':'/data/private/control.token','MQTT_CONFIG':'/data/private/mqtt.json','PILOT_PIN':getpass.getpass('PIN des commandes web locales (facultatif) : ')}))
print('Configuration privée écrite. docker compose up -d --build depuis ce dossier.')
