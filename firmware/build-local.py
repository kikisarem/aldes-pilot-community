"""Compile lc00 using private configuration; never flashes a device."""
import subprocess
from pathlib import Path
r=Path(__file__).resolve().parent
p=r/'private'
subprocess.run(['cmake','-S',str(r),'-B',str(r/'build'),'-DPICO_BOARD=pico_w','-DWIFI_CONFIG_DIR='+str(p),'-DWIFI_SSID='+p.joinpath('ssid.txt').read_text(),'-DCB_RX_EARLY_REARM=0'],check=True)
subprocess.run(['cmake','--build',str(r/'build'),'--target','cbclone_lc00','-j','4'],check=True)
print('UF2 generated under firmware/build. Contains your credentials: do not commit or share it.')
