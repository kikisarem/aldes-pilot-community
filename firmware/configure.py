"""Generate your own private build configuration. Never reuse another owner's UF2."""
import getpass,ipaddress,json,os,secrets
from pathlib import Path
root=Path(__file__).resolve().parent
os.umask(0o077)
p=root/'private';p.mkdir(exist_ok=True)
ssid=input('Wi-Fi SSID (2.4 GHz): ')
password=getpass.getpass('Wi-Fi password: ')
ip=ipaddress.IPv4Address(input('Unused static Pico IPv4: '))
gw=ipaddress.IPv4Address(input('Gateway IPv4 (same /24): '))
if str(ip).split('.')[:3]!=str(gw).split('.')[:3]:raise SystemExit('This reference configuration requires the same /24 subnet.')
token=p/'control.token'
if not token.exists():token.write_text(secrets.token_hex(32)+'\n')
(p/'control_config.h').write_text('#pragma once\n#define CONTROL_TOKEN '+json.dumps(token.read_text().strip())+'\n')
parts=str(ip).split('.')
header='#pragma once\n#define WIFI_PASSWORD '+json.dumps(password)+'\n'
header+='\n'.join('#define CB_IP_'+key+' '+value for key,value in zip('ABCD',parts))+'\n#define CB_GW_D '+str(gw).split('.')[-1]+'\n'
(p/'wifi_config.h').write_text(header)
(p/'ssid.txt').write_text(ssid)
print('Configuration generated under firmware/private (excluded from Git).')
