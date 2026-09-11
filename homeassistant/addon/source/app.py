import os
from pathlib import Path

from fastapi import FastAPI, Request
from starlette.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse

from pico import Pilot, ROOT

PIN = os.environ.get('PILOT_PIN', '').strip()
pilot = Pilot()
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware('http')
async def guard(request: Request, call_next):
    if os.environ.get('PILOT_INGRESS') == '1' and request.client.host not in ('172.30.32.2','127.0.0.1','::1'):
        return JSONResponse({'error':'Home Assistant ingress required'}, status_code=403)
    if request.method == 'POST':
        if request.headers.get('x-pilot-ui') != '1':
            return JSONResponse({'error': 'Origine refusée'}, status_code=403)
        if PIN and request.headers.get('x-pilot-pin', '') != PIN:
            return JSONResponse({'error': 'Code incorrect'}, status_code=401)
        if int(request.headers.get('content-length', '0')) > 1024:
            return JSONResponse({'error': 'Requête trop longue'}, status_code=413)
    resp = await call_next(request)
    resp.headers['Cache-Control'] = 'no-store'
    resp.headers['X-Frame-Options'] = 'SAMEORIGIN' if os.environ.get('PILOT_INGRESS') == '1' else 'DENY'
    resp.headers['Referrer-Policy'] = 'no-referrer'
    return resp


@app.get('/')
def index():
    return FileResponse(ROOT / 'index.html')


@app.get('/manifest.json')
def manifest():
    return FileResponse(ROOT / 'manifest.json', media_type='application/manifest+json')


@app.get('/icon-192.png')
def icon192():
    return FileResponse(ROOT / 'icon-192.png')


@app.get('/icon-512.png')
def icon512():
    return FileResponse(ROOT / 'icon-512.png')


@app.get('/api/state')
def state():
    s = pilot.state()
    s['pin_required'] = bool(PIN)
    # Aucune connexion au port de commande ici. Le Pico W n'accepte qu'une
    # connexion TCP à la fois : /api/state est appelé toutes les 4 s par
    # l'interface, et chaque ouverture de 8766 soit échoue (« No route to
    # host »), soit éjecte le collecteur de 8765 — les deux bloquent l'envoi.
    # L'état du banc est vérifié au moment de l'envoi, dans Workbench.transact.
    # /api/connection reste disponible pour un test manuel, à la demande.
    return s


@app.post('/api/setpoint')
async def setpoint(request: Request):
    body = await request.json()
    try:
        return await run_in_threadpool(pilot.send, 'setpoint', body.get('temperature'), int(body.get('zone')))
    except (ValueError, TypeError) as exc:
        return JSONResponse({'ok': False, 'error': str(exc)}, status_code=400)


@app.post('/api/air')
async def air(request: Request):
    body = await request.json()
    try:
        return await run_in_threadpool(pilot.send, 'air', body.get('mode'))
    except (ValueError, TypeError) as exc:
        return JSONResponse({'ok': False, 'error': str(exc)}, status_code=400)


@app.post('/api/ecs')
async def ecs(request: Request):
    body = await request.json()
    try:
        return await run_in_threadpool(pilot.send, 'ecs', body.get('mode'))
    except (ValueError, TypeError) as exc:
        return JSONResponse({'ok': False, 'error': str(exc)}, status_code=400)


@app.get('/api/connection')
def connection():
    """Read-only authenticated bank status, serialized with UI commands."""
    import socket
    import re
    from pico import TOKEN
    if not pilot.lock.acquire(blocking=False):
        return {'ok': False, 'busy': True}
    try:
        with socket.create_connection((pilot.wb.host, pilot.wb.port), timeout=5) as sock, sock.makefile('rwb', buffering=0) as st:
            def line():
                raw = st.readline(2048)
                if not raw.endswith(b'\n'):
                    raise RuntimeError('Connexion interrompue')
                return raw.decode('ascii').strip()
            if line() != 'WORKBENCH 1 AUTH_REQUIRED':
                raise RuntimeError('Protocole de banc inattendu')
            token = TOKEN.read_text().strip()
            if not re.fullmatch('[0-9a-f]{64}', token):
                raise RuntimeError('Configuration du jeton invalide')
            st.write(('AUTH ' + token + '\n').encode('ascii'))
            if line() != 'OK AUTH':
                raise RuntimeError('Authentification refusée')
            st.write(b'STATUS\n')
            status = line()
            if not status.startswith('STATUS '):
                raise RuntimeError('État du banc invalide')
            return {'ok': True, 'status': status}
    except Exception as exc:
        return {'ok': False, 'error': str(exc)}
    finally:
        pilot.lock.release()


@app.post('/api/vacation/clear')
async def vacation_clear():
    return await run_in_threadpool(pilot.send, 'vacation_clear', 0)
