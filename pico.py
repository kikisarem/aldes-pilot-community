"""Liaison avec le banc Pico et construction des trames validées le 2026-09-10.

Tout part d'un gabarit de 88 octets capturé sur une vraie ConnectBox. On ne
modifie que le champ visé ; le reste est masqué à FF (inchangé) ou laissé tel
quel (zone 53-72, lecture seule). Somme = complément à deux.
"""
import contextlib
import fcntl
import json
import os
import re
import socket
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT
TOKEN = Path(os.environ.get('PICO_TOKEN', str(PROJECT / 'firmware/private/control.token')))
def _find_capture() -> Path:
    """Read the configured capture, or private/pico.log."""
    forced = os.environ.get('PICO_CAPTURE')
    if forced:
        return Path(forced)
    stable = ROOT / 'private/pico.log'
    if stable.exists():
        return stable
    return stable
PICO_HOST = os.environ.get('PICO_HOST', '127.0.0.1')
PICO_PORT = int(os.environ.get('PICO_PORT', '8766'))
DRY_RUN = os.environ.get('PILOT_DRY_RUN') == '1'

# Gabarit : écriture capturée le 11 janvier 2026 (source SHA256 f3353d86…), 88 octets.
TEMPLATE = bytes.fromhex(
    'fdfa58ff10ffffffffffffffff6c07'
    + 'ff' * 38 + '00' * 20 + 'ff' * 13 + 'fe6c'
)
assert len(TEMPLATE) == 88 and sum(TEMPLATE) % 256 == 0

ZONES = {1: 'Zone 1', 2: 'Zone 2', 3: 'Zone 3', 4: 'Zone 4'}
AIR_MODES = {0: 'Arrêt', 1: 'Chauffage · Confort', 2: 'Chauffage · Éco',
             3: 'Chauffage · Programme A', 4: 'Chauffage · Programme B',
             5: 'Clim · Confort', 6: 'Clim · Boost',
             7: 'Clim · Programme C', 8: 'Clim · Programme D'}
ECS_MODES = {0: 'Arrêt', 1: 'Marche', 2: 'Boost'}
OFF_AIR, OFF_ECS = 81, 82
SETPOINT_MIN, SETPOINT_MAX = 16.0, 30.0


def _seal(frame: bytearray) -> bytes:
    frame[-1] = (-sum(frame[:-1])) & 0xFF
    out = bytes(frame)
    assert len(out) == 88 and sum(out) % 256 == 0
    return out


def _blank() -> bytearray:
    """Gabarit avec tous les champs pilotables masqués : consignes, air, ECS."""
    f = bytearray(TEMPLATE)
    f[13:21] = b'\xff' * 8
    f[OFF_AIR] = 0xFF
    f[OFF_ECS] = 0xFF
    return f


def frame_setpoint(zone: int, temperature: float) -> bytes:
    if zone not in ZONES:
        raise ValueError('Zone inconnue')
    t = round(float(temperature) * 2) / 2
    if not SETPOINT_MIN <= t <= SETPOINT_MAX:
        raise ValueError(f'Consigne hors plage {SETPOINT_MIN:g}–{SETPOINT_MAX:g} °C')
    f = _blank()
    off = 13 + 2 * (zone - 1)
    f[off:off + 2] = int(round(t * 100)).to_bytes(2, 'little')
    return _seal(f)


def frame_air(mode: int) -> bytes:
    if mode not in AIR_MODES:
        raise ValueError('Mode air inconnu')
    f = _blank()
    f[OFF_AIR] = mode
    return _seal(f)


def frame_ecs(mode: int) -> bytes:
    if mode not in ECS_MODES:
        raise ValueError('Mode ECS inconnu')
    f = _blank()
    f[OFF_ECS] = mode
    return _seal(f)


def frame_vacation_clear():
    f = _blank()
    f[5:13] = b'\x00' * 8
    return _seal(f)


def capture_health() -> dict:
    if DRY_RUN:
        return {'capture_age_s': 0.0, 'rx_ok': True, 'dry_run': True}
    capture = _find_capture()
    if not capture.exists():
        raise RuntimeError('Aucun collecteur actif — envoi bloqué')
    age = time.time() - capture.stat().st_mtime
    if not 0 <= age < 75:
        raise RuntimeError('Capture trop ancienne — envoi bloqué')
    with capture.open('rb') as s:
        s.seek(max(0, capture.stat().st_size - 30000))
        lines = s.read().decode(errors='replace').splitlines()
    status = next((x for x in reversed(lines) if 'STATUS mounted=' in x), '')
    for field in ('mounted=1', 'rx_errors=0', 'rx_rearm_failed=0', 'log perdus=0'):
        if not re.search(re.escape(field) + r'(?:\s|$)', status):
            raise RuntimeError('Banc non validé — envoi bloqué')
    return {'capture_age_s': round(age, 1), 'rx_ok': True, 'file': capture.name, 'dir': capture.parent.name}


class Workbench:
    """Un seul SEND par transaction, délai 90 s, STOP systématique, aucun retry."""

    def __init__(self, host=PICO_HOST, port=PICO_PORT, timeout=90):
        self.host, self.port, self.timeout = host, port, timeout

    def transact(self, frame: bytes, journal=lambda **kw: None) -> dict:
        capture_health()
        if DRY_RUN:
            time.sleep(1.2)
            return {'txid': int(time.time()) % 1000, 'elapsed_s': 1.2, 'dry_run': True}
        with socket.create_connection((self.host, self.port), timeout=5) as sock, \
                sock.makefile('rwb', buffering=0) as st:
            def line():
                raw = st.readline(2048)
                if not raw.endswith(b'\n'):
                    raise RuntimeError('Connexion interrompue — résultat inconnu')
                return raw.decode('ascii').strip()

            def req(cmd):
                st.write((cmd + '\n').encode('ascii'))
                return line()

            def state():
                a = req('STATUS')
                if not a.startswith('STATUS '):
                    raise RuntimeError('Réponse STATUS invalide')
                return dict(i.split('=', 1) for i in a.split()[1:])

            if line() != 'WORKBENCH 1 AUTH_REQUIRED':
                raise RuntimeError('Protocole de banc inattendu')
            tok = TOKEN.read_text().strip()
            if not re.fullmatch('[0-9a-f]{64}', tok) or req('AUTH ' + tok) != 'OK AUTH':
                raise RuntimeError('Authentification refusée')
            s = state()
            if frame is None:
                return s          # interrogation seule : ni ARM ni SEND
            if s.get('mounted') != '1' or s.get('usb') != '1' or s.get('armed') != '0' or s.get('tx') == 'PENDING':
                raise RuntimeError('Banc indisponible ou occupé')
            ident = int(s['last']) + 1
            armed = False
            try:
                journal(event='intent', txid=ident, hex=frame.hex())
                armed = True
                if not req('ARM').startswith('OK ARM'):
                    raise RuntimeError('Armement refusé')
                t0 = time.monotonic()
                if req(f'SEND {ident} {frame.hex()}') != 'OK SUBMITTED':
                    raise RuntimeError('Soumission non confirmée')
                journal(event='submitted', txid=ident)
                while time.monotonic() - t0 < self.timeout:
                    capture_health()
                    s = state()
                    if s.get('txid') != str(ident) or s.get('mounted') != '1':
                        raise RuntimeError('État USB incohérent — aucun retry')
                    if s.get('tx') == 'USB_DONE':
                        return {'txid': ident, 'elapsed_s': round(time.monotonic() - t0, 2)}
                    if s.get('tx') != 'PENDING':
                        raise RuntimeError('Livraison non confirmée : ' + s.get('tx', '?'))
                    time.sleep(0.1)
                raise RuntimeError('Délai USB dépassé — résultat inconnu')
            finally:
                if armed:
                    stop = req('STOP')
                    final = state()
                    journal(event='stop', stop=stop, armed=final.get('armed'))
                    if stop != 'OK STOP' or final.get('armed') != '0':
                        raise RuntimeError('Désarmement non confirmé — arrêter les essais')


class Pilot:
    """État reçu distinct des demandes, journal durable, envoi sérialisé."""

    def __init__(self, data_dir=ROOT / 'private', cooldown=45):
        self.data = Path(data_dir)
        self.data.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.journal_path = self.data / 'operations.jsonl'
        self.wb = Workbench()
        self.lock = threading.Lock()
        self.cooldown = cooldown
        self.busy = None   # descriptif de la commande en cours

    def _records(self):
        if not self.journal_path.exists():
            return []
        return [json.loads(x) for x in self.journal_path.read_text().splitlines() if x.strip()]

    def _journal(self, **row):
        row.setdefault('utc', time.time())
        with self.journal_path.open('a') as out:
            out.write(json.dumps(row, ensure_ascii=False) + '\n')
            out.flush()
            os.fsync(out.fileno())

    def _bench_from_capture(self):
        """État du banc lu dans la dernière ligne STATUS du collecteur, sans réseau."""
        try:
            cap = _find_capture()
            with cap.open('rb') as f:
                f.seek(max(0, cap.stat().st_size - 20000))
                lines = f.read().decode(errors='replace').splitlines()
            line = next((x for x in reversed(lines) if 'STATUS mounted=' in x), None)
            if not line:
                return None
            m = re.search(r'mounted=(\d)', line)
            return {'mounted': m[1] if m else '?',
                    'usb': '1' if 'rx_errors=0' in line else '?',
                    'source': 'collecteur'}
        except Exception:
            return None

    def state(self) -> dict:
        zones = {z: {'name': n, 'requested': None, 'status': 'idle', 'at': None} for z, n in ZONES.items()}
        air = {'requested': None, 'status': 'idle', 'at': None}
        ecs = {'requested': None, 'status': 'idle', 'at': None}
        last_done = 0
        for r in self._records():
            ev = r.get('event')
            if r.get('kind') == 'vacation_clear':
                if ev in ('delivered', 'error'): last_done = max(last_done, r['utc'])
                continue
            if ev not in ('request', 'delivered', 'error'):
                continue
            tgt = zones[r['zone']] if r.get('kind') == 'setpoint' else air if r.get('kind') == 'air' else ecs
            tgt.update(requested=r['value'], status={'request': 'pending', 'delivered': 'delivered', 'error': 'error'}[ev], at=r['utc'])
            if ev in ('delivered', 'error'):
                last_done = max(last_done, r['utc'])
        try:
            health = capture_health(); available = True
        except Exception as exc:
            health = {'error': str(exc)}; available = False
        # On n'interroge PAS le banc ici. Le Pico n'accepte qu'une connexion TCP
        # à la fois : ouvrir 8766 éjecte le collecteur de 8765, et /api/state est
        # appelé toutes les 4 s par l'interface. L'état du banc est vérifié au
        # moment de l'envoi, dans Workbench.transact, où la connexion est unique
        # et brève. On se contente ici de lire le journal du collecteur.
        bench = self._bench_from_capture()
        from readback import read_state
        observed = read_state(_find_capture())
        decoded = observed.get('decoded') or {}
        for z, item in zones.items():
            item['actual'] = next((v['setpoint_c'] for v in decoded.get('zones', []) if v['zone'] == f'K{z}'), None)
        air['actual'] = decoded.get('air', {}).get('raw')
        ecs['actual'] = decoded.get('ecs', {}).get('raw')
        for item in [*zones.values(), air, ecs]:
            item['matches_request'] = (item['actual'] == item['requested']) if observed['available'] and item['requested'] is not None else None
            item['delivery_status'] = item['status']
            item['status'] = 'observed' if observed['available'] else 'unavailable'
            item['command_recent'] = bool(item['at'] and 0 <= time.time() - item['at'] < 120)
        available = available and observed['available'] if not DRY_RUN else available
        if not available: health['error'] = observed.get('reason') or health.get('error', 'Lecture indisponible')
        return {'zones': zones, 'air': air, 'ecs': ecs, 'busy': self.busy, 'available': available,
                'observation': observed, 'observed': observed, 'vacation': decoded.get('vacation'), 'health': health, 'bench': bench, 'cooldown_s': max(0, int(self.cooldown - (time.time() - last_done))),
                'labels': {'air': AIR_MODES, 'ecs': ECS_MODES}, 'dry_run': DRY_RUN,
                'journal': self._records()[-12:]}

    def send(self, kind: str, value, zone: int | None = None) -> dict:
        if kind == 'setpoint':
            frame = frame_setpoint(zone, value); value = round(float(value) * 2) / 2
        elif kind == 'air':
            value = int(value); frame = frame_air(value)
        elif kind == 'ecs':
            value = int(value); frame = frame_ecs(value)
        elif kind == 'vacation_clear':
            value = 0; frame = frame_vacation_clear()
        else:
            raise ValueError('Commande inconnue')
        if not self.lock.acquire(blocking=False):
            return {'ok': False, 'error': 'Une commande est déjà en cours'}
        try:
            with (self.data / 'tx.lock').open('a') as lf:
                try:
                    fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    return {'ok': False, 'error': 'Un autre processus utilise le banc'}
                st = self.state()
                if not st['available']:
                    return {'ok': False, 'error': st['health'].get('error', 'Banc indisponible')}
                if st['cooldown_s']:
                    return {'ok': False, 'error': f"Observation en cours — {st['cooldown_s']} s"}
                base = {'kind': kind, 'zone': zone, 'value': value}
                self.busy = base
                self._journal(event='request', **base)
                try:
                    res = self.wb.transact(frame, lambda **kw: self._journal(**base, **kw))
                    self._journal(event='delivered', **base, **res)
                    return {'ok': True, **res}
                except Exception as exc:
                    self._journal(event='error', **base, error=str(exc))
                    return {'ok': False, 'error': str(exc)}
        finally:
            self.busy = None
            self.lock.release()
