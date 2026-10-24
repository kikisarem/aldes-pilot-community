"""Build distributable lc00 firmware without private include paths."""
import hashlib,os,struct,subprocess
from pathlib import Path
BOARD=os.environ.get('PICO_BOARD','pico_w')
if BOARD not in ('pico_w','pico2_w'):
    raise SystemExit('PICO_BOARD must be pico_w or pico2_w')
r=Path(__file__).resolve().parent;b=r/f'build-generic-{BOARD}'
subprocess.run(['cmake','-S',str(r),'-B',str(b),f'-DPICO_BOARD={BOARD}','-DCB_PROVISIONING=ON','-DCB_RX_EARLY_REARM=0','-DWIFI_SSID=','-DWIFI_CONFIG_DIR='],check=True)
subprocess.run(['cmake','--build',str(b),'--target','cbclone_lc00','-j','4'],check=True)
raw=(b/'cbclone_lc00.uf2').read_bytes()
flash_end=0x10400000 if BOARD=='pico2_w' else 0x10200000
for offset in range(0,len(raw),512):
 block=raw[offset:offset+512]
 magic,magic2,flags,address,size,block_no,num_blocks,file_size=struct.unpack_from('<8I',block)
 if magic!=0x0a324655 or magic2!=0x9e5d5157 or size>476 or struct.unpack_from('<I',block,508)[0]!=0x0ab16f30:
  raise SystemExit('Unexpected UF2 format')
 if BOARD=='pico2_w' and address==0x10ffff00:
  absolute_block=(flags==0xa000 and size==256 and block_no==0 and num_blocks==2
                  and file_size==0xe48bff57 and block[32:288]==b'\xef'*256
                  and struct.unpack_from('<I',block,288)[0]==0x9957e304)
  if absolute_block:
   continue
  raise SystemExit('Unexpected RP2350 UF2 absolute block')
 if address<0x10000000 or address+size>flash_end:
  raise SystemExit('UF2 contains a block outside the board flash')
 if address+size>0x101fe000:
  raise SystemExit('UF2 overlaps reserved configuration sectors')
out=r.parent/'artifacts';out.mkdir(exist_ok=True)
name='aldes-pico-2-w-portal-experimental.uf2' if BOARD=='pico2_w' else 'aldes-pico-w-portal-experimental.uf2'
(out/name).write_bytes(raw)
manifest=out/'SHA256SUMS'
checksums=[line for line in manifest.read_text().splitlines() if line.split(maxsplit=1)[-1:]!=[name]] if manifest.exists() else []
checksums.append(f'{hashlib.sha256(raw).hexdigest()}  {name}')
manifest.write_text('\n'.join(checksums)+'\n')
print(f'Generic {BOARD} firmware generated. Hardware provisioning test remains required before deployment.')
