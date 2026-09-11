"""Offline RAW audit. No sockets, PAC writes, or assumed wall-clock conversion."""
from pathlib import Path
import argparse, collections, hashlib, json, re

def audit(raw):
    chunks=[]; errors=[]; boundaries=[]; controls=[]; pending=None; segment=0
    for ln,line in enumerate(raw.decode(errors='replace').splitlines(),1):
        if line.startswith('[collector]') or 'USB bus reset' in line:
            boundaries.append({'line':ln,'text':line})
            if pending: errors.append({'line':pending['line'],'reason':'incomplete_at_boundary'}); pending=None
            segment+=1
        m=re.match(r'\[\s*(\d+)\] (.*)',line)
        if not m: continue
        t=int(m[1]); msg=m[2]
        if msg.startswith(('ENUM ', 'LCDIAG ', 'TX ', 'USB bus reset')):
            controls.append({'line':ln,'uptime':t,'text':msg})
        h=re.match(r'OUT xfer #(\d+), (\d+) octets',msg)
        if h:
            if pending: errors.append({'line':pending['line'],'reason':'incomplete_transfer'})
            pending={'segment':segment,'line':ln,'time':t,'id':int(h[1]),'length':int(h[2]),'data':bytearray()}
            continue
        h=re.match(r'\s+raw \+(\d+): ([0-9A-F ]+)',msg)
        if h and pending:
            if int(h[1])!=len(pending['data']):
                errors.append({'line':ln,'reason':'offset_gap'}); pending=None; continue
            pending['data'].extend(bytes.fromhex(h[2]))
            if len(pending['data'])==pending['length']: chunks.append(pending); pending=None
            elif len(pending['data'])>pending['length']: errors.append({'line':ln,'reason':'overlength'}); pending=None
    streams=[]
    for c in chunks:
        if not streams or c['segment']!=streams[-1]['segment'] or c['id']!=streams[-1]['last_id']+1:
            streams.append({'segment':c['segment'],'last_id':c['id'],'data':bytearray(),'ranges':[]})
        s=streams[-1]; start=len(s['data']);s['data'].extend(c['data']);s['last_id']=c['id']
        s['ranges'].append((start,len(s['data']),c['time'],c['line']))
    frames=[]; leftovers=[]; nested=[]; unframed_spans=[]
    for si,s in enumerate(streams):
        b=bytes(s['data']); i=0; discarded=0; span_start=0
        while i+5<=len(b):
            size=b[i+2]
            candidate=b[i:i+size]
            if b[i:i+2] in (b'\xfa\xfd',b'\xff\xfd') and b[i+3]==255 and size>=7 and len(candidate)==size and candidate[-2]==254 and sum(candidate)%256==0:
                if span_start<i:
                    st,sl=next((t,l) for a,z,t,l in s['ranges'] if a<=span_start<z)
                    unframed_spans.append({'stream':si,'offset':span_start,'uptime':st,'line':sl,'length':i-span_start,'hex':b[span_start:i].hex()})
                time,line=next((t,l) for a,z,t,l in s['ranges'] if a<=i<z)
                frames.append({'stream':si,'offset':i,'uptime':time,'line':line,'opcode':f'{candidate[4]:02x}','length':size,'hex':candidate.hex()})
                for j in range(1,size-4):
                    if candidate[j:j+2] in (b'\xfa\xfd',b'\xff\xfd') and candidate[j+3]==255:
                        nested.append({'frame':len(frames)-1,'offset':j,'opcode':f'{candidate[j+4]:02x}'})
                i+=size; span_start=i
            else: discarded+=1;i+=1
        leftovers.append({'stream':si,'unframed_bytes':discarded+len(b)-i})
        if span_start<len(b):
            st,sl=next((t,l) for a,z,t,l in s['ranges'] if a<=span_start<z)
            unframed_spans.append({'stream':si,'offset':span_start,'uptime':st,'line':sl,'length':len(b)-span_start,'hex':b[span_start:].hex()})
    transitions=[];runs=[]
    for f in frames:
        if not runs or (runs[-1]['stream'],runs[-1]['opcode'])!=(f['stream'],f['opcode']):
            if runs and runs[-1]['stream']==f['stream']:
                transitions.append({'stream':f['stream'],'from':runs[-1]['opcode'],'to':f['opcode'],'before_uptime':runs[-1]['last'],'after_uptime':f['uptime'],'line':f['line']})
            runs.append({'stream':f['stream'],'opcode':f['opcode'],'first':f['uptime'],'last':f['uptime'],'count':0,'payloads':set()})
        runs[-1]['count']+=1; runs[-1]['last']=f['uptime']; runs[-1]['payloads'].add(f['hex'])
    for r in runs:r['distinct_payloads']=len(r.pop('payloads'))
    return {'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'transfers':len(chunks),'streams':len(streams),'errors':errors,'pending_tail':bool(pending),'frame_counts':dict(collections.Counter(f['opcode'] for f in frames)),'runs':runs,'transitions':transitions,'unframed':leftovers,'unframed_spans':unframed_spans,'nested_headers':nested,'boundaries':boundaries,'controls':controls,'frames':frames}

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('source');ap.add_argument('output');a=ap.parse_args()
    result=audit(Path(a.source).read_bytes());Path(a.output).write_text(json.dumps(result,indent=2))
    print(json.dumps({k:result[k] for k in ('sha256','bytes','transfers','streams','errors','pending_tail','frame_counts','runs','transitions','unframed')},indent=2))
