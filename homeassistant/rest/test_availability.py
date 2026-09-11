import json,sys
from pathlib import Path
from jinja2.nativetypes import NativeEnvironment
p=json.load(open(sys.argv[1] if len(sys.argv)>1 else Path(__file__).with_name('aldes_pilot.yaml')))
e=NativeEnvironment()
for online,busy,cooldown,recovery,readable,command in [(True,None,40,'ready',True,False),(True,{'kind':'air'},0,'ready',True,False),(True,None,0,'recovering',True,False),(False,None,0,'ready',False,False),(True,None,0,'ready',True,True)]:
 attrs={'busy':busy,'cooldown_s':cooldown,'recovery':{'status':recovery},'air':{'actual':1}}
 e.globals.update(is_state=lambda *a:online,state_attr=lambda entity,key:attrs.get(key))
 t=p['template'][0]['select'][0]
 assert e.from_string(t['availability']).render()==readable
 assert e.from_string(t['select_option'][0]['if'][0]['value_template']).render()==(not command)
 if readable:assert e.from_string(t['state']).render()=='Chauffage Confort'
print('5 scenarios passed: fresh state stays visible; commands remain guarded.')
