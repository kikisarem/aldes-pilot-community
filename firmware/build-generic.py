"""Build a distributable Pico W lc00 firmware without private include paths."""
import hashlib,json,shutil,struct,subprocess
from pathlib import Path
r=Path(__file__).resolve().parent;b=r/'build-generic'
subprocess.run(['cmake','-S',str(r),'-B',str(b),'-DPICO_BOARD=pico_w','-DCB_PROVISIONING=ON','-DCB_RX_EARLY_REARM=0','-DWIFI_SSID=','-DWIFI_CONFIG_DIR='],check=True)
subprocess.run(['cmake','--build',str(b),'--target','cbclone_lc00','-j','4'],check=True)
raw=(b/'cbclone_lc00.uf2').read_bytes()
for offset in range(0,len(raw),512):
 block=raw[offset:offset+512];magic,magic2,flags,address,size=struct.unpack_from('<5I',block)
 if magic!=0x0a324655 or magic2!=0x9e5d5157 or size>476:raise SystemExit('Unexpected UF2 format')
 if address<0x10000000 or address+size>0x101fe000:raise SystemExit('UF2 overlaps reserved configuration sectors')
out=r.parent/'artifacts';out.mkdir(exist_ok=True);name='aldes-pico-w-portal-experimental.uf2';(out/name).write_bytes(raw)
(out/'SHA256SUMS').write_text(hashlib.sha256(raw).hexdigest()+'  '+name+'\n')
print('Generic firmware generated. Hardware provisioning test remains required before deployment.')
