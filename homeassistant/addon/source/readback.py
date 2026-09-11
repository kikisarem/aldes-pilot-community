"""Read the existing collector only; never connects to the PAC."""
import time
from reader import snapshot

def read_state(path):
    try:
        with path.open('rb') as stream:
            import os
            st=os.fstat(stream.fileno())
            # Bounded window; discard the initial partial log line.
            start=max(0,st.st_size-250000)
            stream.seek(start)
            if start: stream.readline()
            raw=stream.read(250000)
        data=snapshot(raw,st.st_mtime,time.time())
        page=data.get('pages',{}).get('21',{})
        return {'available':bool(page.get('available')), 'age_s':page.get('age_seconds'),
                'uptime_ms':page.get('uptime_ms'), 'sha256':page.get('sha256'),
                'decoded':page.get('decoded') if page.get('available') else None,
                'reason':None if page.get('available') else 'Aucun rapport PAC récent et valide'}
    except (OSError,ValueError,KeyError) as exc:
        return {'available':False,'decoded':None,'age_s':None,'reason':'Lecture PAC indisponible'}
