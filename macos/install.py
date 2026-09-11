"""Install a user-login launcher with its own Local Network identity."""
import argparse,getpass,json,os,plistlib,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--host',required=True);a=p.parse_args()
r=Path(__file__).resolve().parent.parent
os.umask(0o077);(r/'private').mkdir(exist_ok=True);(r/'logs').mkdir(exist_ok=True)
if not (r/'.venv/bin/python').exists():raise SystemExit('Create .venv and install requirements first.')
if not (r/'firmware/private/control.token').exists():raise SystemExit('Run firmware/configure.py first.')
(r/'private/service.json').write_text(json.dumps({'PICO_HOST':a.host,'PICO_TOKEN':str(r/'firmware/private/control.token'),'PILOT_PIN':getpass.getpass('PIN for web writes (optional): ')}))
b=Path.home()/'Applications/Aldes Pilot.app';(b/'Contents/MacOS').mkdir(parents=True,exist_ok=True)
subprocess.run(['swiftc',str(r/'macos/Service.swift'),'-o',str(b/'Contents/MacOS/AldesPilot')],check=True)
(b/'Contents/Info.plist').write_bytes(plistlib.dumps({'CFBundleIdentifier':'local.aldes.pilot','CFBundleExecutable':'AldesPilot','CFBundleName':'Aldes Pilot','CFBundleVersion':'1','CFBundlePackageType':'APPL','LSUIElement':True,'PilotRoot':str(r),'PicoHost':a.host,'NSLocalNetworkUsageDescription':'Lire votre bridge Pico et transmettre vos commandes depuis la page locale.'}))
subprocess.run(['codesign','--force','--sign','-',str(b)],check=True)
job=Path.home()/'Library/LaunchAgents/local.aldes.pilot.plist';job.parent.mkdir(parents=True,exist_ok=True)
job.write_bytes(plistlib.dumps({'Label':'local.aldes.pilot','ProgramArguments':['/usr/bin/open','-W',str(b)],'RunAtLoad':True,'KeepAlive':True,'ThrottleInterval':10,'StandardOutPath':str(r/'logs/launchagent.log'),'StandardErrorPath':str(r/'logs/launchagent.err')}))
subprocess.run(['launchctl','bootstrap',f'gui/{os.getuid()}',str(job)],check=True)
print('Allow Aldes Pilot under macOS Privacy & Security > Local Network. Check fresh reports before relying on startup.')
