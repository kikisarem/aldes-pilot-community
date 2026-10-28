"""Test fixture: real HTTP/queue logic, synthetic state and recorded USB frames."""
import threading

from fastapi import Request
from app import app, pilot

lock = threading.Lock()
control = {'available': True, 'cooldown_s': 0, 'fail_transport': False}
actual = {'air': 0, 'ecs': 1, 'zones': {str(z): 22 for z in range(1, 5)}}
frames = []


def state():
    with lock:
        result = {'available': control['available'], 'cooldown_s': control['cooldown_s'],
                  'recovery': {'status': 'ready'}, 'health': {}, 'busy': pilot.busy,
                  'air': {'actual': actual['air']}, 'ecs': {'actual': actual['ecs']},
                  'zones': {str(z): {'active': z <= 4,
                            'actual': actual['zones'].get(str(z)),
                            'temperature_candidate_c': 21.5 if z <= 4 else None}
                            for z in range(1, 10)}}
    result['command_queue'] = pilot.command_queue_state()
    return result


def transport(frame, journal=lambda **kw: None, **kwargs):
    assert len(frame) == 88 and sum(frame) % 256 == 0
    with lock:
        row = {'hex': frame.hex(), 'unknown': control['fail_transport']}
        frames.append(row)
        if control['fail_transport']:
            raise RuntimeError('Simulated unknown USB delivery')
        for z in range(1, 5):
            offset = 13 + 2 * (z - 1)
            raw = int.from_bytes(frame[offset:offset+2], 'little')
            if raw != 65535:
                actual['zones'][str(z)] = raw / 100
        for field, offset in (('air', 81), ('ecs', 82)):
            if frame[offset] != 255:
                actual[field] = frame[offset]
        return {'txid': len(frames), 'elapsed_s': 0, 'simulated': True}


pilot.state = state
pilot.wb.transact = transport


@app.get('/review/state')
def review_state():
    with lock:
        return {'frames': list(frames), 'control': dict(control)}


@app.post('/review/control')
async def review_control(request: Request):
    body = await request.json()
    assert set(body) <= set(control)
    with lock:
        control.update(body)
    return {'ok': True}
