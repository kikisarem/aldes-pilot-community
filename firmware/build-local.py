"""Compile lc00 using private configuration; never flashes a device."""
import os,subprocess
from pathlib import Path
board=os.environ.get('PICO_BOARD','pico_w')
if board not in ('pico_w','pico2_w'):
    raise SystemExit('PICO_BOARD must be pico_w or pico2_w')
r=Path(__file__).resolve().parent
p=r/'private'
b=r/'build' if board=='pico_w' else r/'build-pico2_w'
subprocess.run(['cmake','-S',str(r),'-B',str(b),f'-DPICO_BOARD={board}','-DWIFI_CONFIG_DIR='+str(p),'-DWIFI_SSID='+p.joinpath('ssid.txt').read_text(),'-DCB_RX_EARLY_REARM=0'],check=True)
subprocess.run(['cmake','--build',str(b),'--target','cbclone_lc00','-j','4'],check=True)
print(f'UF2 generated under firmware/{b.name}. Contains your credentials: do not commit or share it.')
