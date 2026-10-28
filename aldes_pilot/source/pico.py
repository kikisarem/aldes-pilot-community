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
from collections import OrderedDict
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
MAX_REPORTED_ZONES = 9
AIR_MODES = {0: 'Arrêt', 1: 'Chauffage · Confort', 2: 'Chauffage · Éco',
             3: 'Chauffage · Programme A', 4: 'Chauffage · Programme B',
             5: 'Clim · Confort', 6: 'Clim · Boost',
             7: 'Clim · Programme C', 8: 'Clim · Programme D'}
ECS_MODES = {0: 'Arrêt', 1: 'Marche', 2: 'Boost'}
OFF_AIR, OFF_ECS = 81, 82
SETPOINT_MIN, SETPOINT_MAX = 16.0, 31.0


def setpoint_limits(air_mode: int | None) -> tuple[float, float]:
    if air_mode in (1, 2, 3, 4):
        return 16.0, 24.0
    if air_mode in (5, 6, 7, 8):
        return 22.0, 31.0
    if air_mode == 0 or air_mode is None:
        return SETPOINT_MIN, SETPOINT_MAX
    raise ValueError('Mode air inconnu')


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


def frame_setpoint(zone: int, temperature: float, air_mode: int | None = None) -> bytes:
    if zone not in ZONES:
        raise ValueError('Zone inconnue')
    t = float(temperature)
    if not t.is_integer():
        raise ValueError('La consigne doit être un nombre entier de degrés')
    minimum, maximum = setpoint_limits(air_mode)
    if t != 0 and not minimum <= t <= maximum:
        raise ValueError(f'Consigne invalide : 0 (Off) ou {minimum:g}–{maximum:g} °C pour le mode actuel')
    f = _blank()
    off = 13 + 2 * (zone - 1)
    f[off:off + 2] = int(round(t * 100)).to_bytes(2, 'little')
    return _seal(f)


def frame_setpoints(setpoints: dict[int, float], air_mode: int | None = None) -> bytes:
    if not isinstance(setpoints, dict) or not setpoints:
        raise ValueError('Au moins une consigne est nécessaire')
    f = _blank()
    for zone, temperature in setpoints.items():
        if zone not in ZONES:
            raise ValueError('Zone inconnue')
        value = float(temperature)
        if not value.is_integer():
            raise ValueError('La consigne doit être un nombre entier de degrés')
        minimum, maximum = setpoint_limits(air_mode)
        if value != 0 and not minimum <= value <= maximum:
            raise ValueError(f'Consigne invalide : 0 (Off) ou {minimum:g}–{maximum:g} °C pour le mode actuel')
        offset = 13 + 2 * (zone - 1)
        f[offset:offset + 2] = int(value * 100).to_bytes(2, 'little')
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


def frame_modes(air: int | None = None, ecs: int | None = None) -> bytes:
    if air is None and ecs is None:
        raise ValueError('Au moins un mode est nécessaire')
    f = _blank()
    if air is not None:
        if air not in AIR_MODES:
            raise ValueError('Mode air inconnu')
        f[OFF_AIR] = air
    if ecs is not None:
        if ecs not in ECS_MODES:
            raise ValueError('Mode ECS inconnu')
        f[OFF_ECS] = ecs
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
    from reader import snapshot
    with capture.open('rb') as stream:
        stat = os.fstat(stream.fileno())
        start = max(0, stat.st_size - 250000)
        stream.seek(start)
        if start:
            stream.readline()
        raw = stream.read(250000)
    now = time.time()
    age = now - stat.st_mtime
    if not 0 <= age <= 25:
        raise RuntimeError('Capture trop ancienne — envoi bloqué')
    if not snapshot(raw, stat.st_mtime, now)['capture_healthy']:
        raise RuntimeError('Banc non validé — envoi bloqué')
    return {'capture_age_s': round(age, 1), 'rx_ok': True, 'file': capture.name, 'dir': capture.parent.name}


class Workbench:
    """Un seul SEND par transaction, délai 90 s, STOP systématique, aucun retry."""

    def __init__(self, host=PICO_HOST, port=PICO_PORT, timeout=90):
        self.host, self.port, self.timeout = host, port, timeout

    def transact(self, frame: bytes, journal=lambda **kw: None, pre_send=None) -> dict:
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
                if pre_send is not None:
                    pre_send()
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
        self.queue_condition = threading.Condition()
        self.pending_commands = OrderedDict()
        self.current_command = None
        self.queue_result = None
        self.queue_worker = None
        self.queue_limit = 16
        self.queue_debounce = 0.5
        self.mode_debounce = 2.0
        self.setpoint_debounce = 5.0

    def enqueue(self, kind: str, value, zone: int | None = None) -> dict:
        if kind == 'setpoint':
            frame_setpoint(zone, value)
            value = int(float(value))
            key = f'k{zone}'
        elif kind == 'air':
            value = int(value); frame_air(value); key = 'air'
        elif kind == 'ecs':
            value = int(value); frame_ecs(value); key = 'ecs'
        elif kind == 'vacation_clear':
            value = 0; frame_vacation_clear(); key = kind
        else:
            raise ValueError('Commande inconnue')
        with self.queue_condition:
            replaced = key in self.pending_commands
            if not replaced and len(self.pending_commands) >= self.queue_limit:
                return {'ok': False, 'error': 'File de commandes pleine'}
            self.pending_commands[key] = {
                'kind': kind, 'value': value, 'zone': zone, 'updated': time.monotonic()
            }
            self.queue_result = {'key': key, 'status': 'queued', 'value': value}
            if self.queue_worker is None or not self.queue_worker.is_alive():
                self.queue_worker = threading.Thread(target=self._command_worker, daemon=True)
                self.queue_worker.start()
            self.queue_condition.notify_all()
        return {'ok': True, 'queued': True, 'replaced': replaced, 'key': key}

    def _command_worker(self):
        while True:
            with self.queue_condition:
                while not self.pending_commands:
                    self.queue_condition.wait()
                key, command = next(iter(self.pending_commands.items()))
                setpoint_batch = command['kind'] == 'setpoint'
                mode_batch = command['kind'] in ('air', 'ecs')
                prefix = []
                if setpoint_batch or mode_batch:
                    batch_kinds = ('setpoint',) if setpoint_batch else ('air', 'ecs')
                    for pending_key, pending in self.pending_commands.items():
                        if pending['kind'] not in batch_kinds:
                            break
                        prefix.append((pending_key, pending))
                latest_update = max(item['updated'] for _, item in prefix) if prefix else command['updated']
                debounce = self.setpoint_debounce if setpoint_batch else self.mode_debounce if mode_batch else self.queue_debounce
                remaining = latest_update + debounce - time.monotonic()
                if remaining > 0:
                    self.queue_condition.wait(timeout=remaining)
                    continue
            try:
                state = self.state()
            except Exception as exc:
                with self.queue_condition:
                    self.pending_commands.clear()
                    self.queue_result = {'key': key, 'status': 'error', 'error': f'État de la PAC illisible: {exc}'}
                    self.queue_condition.notify_all()
                continue
            if not state['available'] or state.get('recovery', {}).get('status') == 'recovering':
                with self.queue_condition:
                    self.pending_commands.clear()
                    self.queue_result = {'key': key, 'status': 'error', 'error': 'Lecture PAC indisponible'}
                    self.queue_condition.notify_all()
                continue
            if state.get('busy') or state.get('cooldown_s', 0) > 0:
                with self.queue_condition:
                    self.queue_condition.wait(timeout=1)
                continue
            with self.queue_condition:
                if setpoint_batch or mode_batch:
                    current_prefix = []
                    batch_kinds = ('setpoint',) if setpoint_batch else ('air', 'ecs')
                    for pending_key, pending in self.pending_commands.items():
                        if pending['kind'] not in batch_kinds:
                            break
                        current_prefix.append((pending_key, pending))
                    debounce = self.setpoint_debounce if setpoint_batch else self.mode_debounce if mode_batch else self.queue_debounce
                    if not current_prefix or max(item['updated'] for _, item in current_prefix) + debounce > time.monotonic():
                        continue
                    batch_commands = [(pending_key, dict(item)) for pending_key, item in current_prefix]
                    # State inspection releases the queue lock. A command may
                    # have been replaced meanwhile, including a one-item batch.
                    key, command = batch_commands[0]
                    if setpoint_batch:
                        batch_values = {item['zone']: item['value'] for _, item in current_prefix}
                    else:
                        batch_values = {item['kind']: item['value'] for _, item in current_prefix}
                    for pending_key, _ in current_prefix:
                        self.pending_commands.pop(pending_key)
                    if setpoint_batch:
                        keys = list(batch_values)
                        current = 'batch:' + '+'.join('k' + str(zone) for zone in keys) if len(keys) > 1 else 'k' + str(keys[0])
                        result_value = batch_values
                    elif mode_batch:
                        keys = list(batch_values)
                        current = 'batch:' + '+'.join(keys) if len(keys) > 1 else keys[0]
                        result_value = batch_values
                else:
                    latest = self.pending_commands.get(key)
                    if latest is None or latest['updated'] != command['updated']:
                        continue
                    self.pending_commands.pop(key)
                    current = key
                    result_value = command['value']
                self.current_command = current
                self.queue_result = {'key': current, 'status': 'sending', 'value': result_value}
            try:
                if setpoint_batch and len(batch_values) > 1:
                    result = self.send_setpoints(batch_values)
                elif mode_batch and len(batch_values) > 1:
                    result = self.send_modes(batch_values)
                else:
                    result = self.send(command['kind'], command['value'], command['zone'])
            except Exception as exc:
                result = {'ok': False, 'error': f'Échec interne de la commande: {exc}'}
            with self.queue_condition:
                self.current_command = None
                error = result.get('error', '')
                if error in ('Une commande est déjà en cours', 'Un autre processus utilise le banc') or error.startswith('Observation en cours'):
                    if (setpoint_batch and len(batch_values) > 1) or (mode_batch and len(batch_values) > 1):
                        retry_at = time.monotonic()
                        for pending_key, pending in reversed(batch_commands):
                            if pending_key not in self.pending_commands:
                                pending['updated'] = retry_at
                                self.pending_commands[pending_key] = pending
                                self.pending_commands.move_to_end(pending_key, last=False)
                    elif key not in self.pending_commands:
                        command['updated'] = time.monotonic()
                        self.pending_commands[key] = command
                    self.queue_result = {'key': current, 'status': 'queued', 'value': result_value}
                    self.queue_condition.wait(timeout=1)
                    continue
                self.queue_result = {
                    'key': current, 'status': 'delivered' if result.get('ok') else 'error',
                    'value': result_value, 'error': error
                }
                self.queue_condition.notify_all()

    def command_queue_state(self) -> dict:
        with self.queue_condition:
            return {
                'pending': {
                    key: {'kind': command['kind'], 'value': command['value'], 'zone': command['zone']}
                    for key, command in self.pending_commands.items()
                },
                'current': self.current_command,
                'result': self.queue_result,
            }

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
        zones = {z: {'name': f'Zone {z}', 'requested': None, 'status': 'idle', 'at': None,
                     'active': False, 'actual': None, 'temperature_candidate_c': None}
                 for z in range(1, MAX_REPORTED_ZONES + 1)}
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
        for decoded_zone in decoded.get('zones', []):
            try:
                z = int(decoded_zone['zone'][1:])
            except (KeyError, TypeError, ValueError):
                continue
            if not 1 <= z <= MAX_REPORTED_ZONES:
                continue
            item = zones[z]
            item.update(name=f'Zone {z}', active=bool(decoded_zone.get('active', True)),
                        actual=decoded_zone.get('setpoint_c'),
                        temperature_candidate_c=decoded_zone.get('temperature_candidate_c'))
        air['actual'] = decoded.get('air', {}).get('raw')
        ecs['actual'] = decoded.get('ecs', {}).get('raw')
        for item in [*zones.values(), air, ecs]:
            item['matches_request'] = (item['actual'] == item['requested']) if observed['available'] and item['requested'] is not None else None
            item['delivery_status'] = item['status']
            item['status'] = 'observed' if observed['available'] else 'unavailable'
            item['command_recent'] = bool(item['at'] and 0 <= time.time() - item['at'] < 120)
        available = available and observed['available'] if not DRY_RUN else available
        if not available: health['error'] = observed.get('reason') or health.get('error', 'Lecture indisponible')
        try:
            recovery = json.loads((self.data / 'recovery.json').read_text())
            recovery = {k: recovery.get(k) for k in ('status', 'reason', 'last_action')}
        except (OSError, ValueError):
            recovery = {'status': 'watching'}
        return {'recovery': recovery, 'zones': zones, 'air': air, 'ecs': ecs, 'busy': self.busy, 'available': available,
                'command_queue': self.command_queue_state(),
                'observation': observed, 'observed': observed, 'vacation': decoded.get('vacation'), 'health': health, 'bench': bench, 'cooldown_s': max(0, int(self.cooldown - (time.time() - last_done))),
                'labels': {'air': AIR_MODES, 'ecs': ECS_MODES}, 'dry_run': DRY_RUN,
                'journal': self._records()[-12:]}

    def send(self, kind: str, value, zone: int | None = None) -> dict:
        if kind == 'setpoint':
            frame = frame_setpoint(zone, value); value = int(float(value))
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
                if st.get('recovery', {}).get('status') == 'recovering':
                    return {'ok': False, 'error': 'Reprise de lecture en cours'}
                if not st['available']:
                    return {'ok': False, 'error': st['health'].get('error', 'Banc indisponible')}
                if st['cooldown_s']:
                    return {'ok': False, 'error': f"Observation en cours — {st['cooldown_s']} s"}
                if kind == 'setpoint':
                    frame = frame_setpoint(zone, value, st['air']['actual'])
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

    def send_setpoints(self, setpoints: dict[int, float]) -> dict:
        normalized = {int(zone): float(value) for zone, value in setpoints.items()}
        if not normalized or any(zone not in ZONES for zone in normalized):
            raise ValueError('Consignes de zones invalides')
        if not self.lock.acquire(blocking=False):
            return {'ok': False, 'error': 'Une commande est déjà en cours'}
        try:
            with (self.data / 'tx.lock').open('a') as lock_file:
                try:
                    fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    return {'ok': False, 'error': 'Un autre processus utilise le banc'}
                state = self.state()
                if state.get('recovery', {}).get('status') == 'recovering':
                    return {'ok': False, 'error': 'Reprise de lecture en cours'}
                if not state['available']:
                    return {'ok': False, 'error': state['health'].get('error', 'Banc indisponible')}
                if state['cooldown_s']:
                    return {'ok': False, 'error': f"Observation en cours — {state['cooldown_s']} s"}
                frame = frame_setpoints(normalized, state['air']['actual'])
                normalized = {zone: int(value) for zone, value in normalized.items()}
                self.busy = {'kind': 'setpoint_batch', 'zones': normalized}
                for zone, value in normalized.items():
                    self._journal(event='request', kind='setpoint', zone=zone, value=value)
                try:
                    result = self.wb.transact(
                        frame,
                        lambda **event: self._journal(kind='setpoint_batch', zones=normalized, **event))
                    for zone, value in normalized.items():
                        self._journal(event='delivered', kind='setpoint', zone=zone, value=value, **result)
                    return {'ok': True, **result, 'zones': list(normalized)}
                except Exception as exc:
                    for zone, value in normalized.items():
                        self._journal(event='error', kind='setpoint', zone=zone, value=value, error=str(exc))
                    return {'ok': False, 'error': str(exc)}
        finally:
            self.busy = None
            self.lock.release()

    def send_modes(self, modes: dict[str, int]) -> dict:
        if not modes or any(kind not in ('air', 'ecs') for kind in modes):
            raise ValueError('Modes invalides')
        normalized = {kind: int(value) for kind, value in modes.items()}
        frame = frame_modes(normalized.get('air'), normalized.get('ecs'))
        if not self.lock.acquire(blocking=False):
            return {'ok': False, 'error': 'Une commande est déjà en cours'}
        try:
            with (self.data / 'tx.lock').open('a') as lock_file:
                try:
                    fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    return {'ok': False, 'error': 'Un autre processus utilise le banc'}
                st = self.state()
                if st.get('recovery', {}).get('status') == 'recovering':
                    return {'ok': False, 'error': 'Reprise de lecture en cours'}
                if not st['available']:
                    return {'ok': False, 'error': st['health'].get('error', 'Banc indisponible')}
                if st['cooldown_s']:
                    return {'ok': False, 'error': f"Observation en cours — {st['cooldown_s']} s"}
                self.busy = {'kind': 'mode_batch', 'value': normalized}
                for kind, value in normalized.items():
                    self._journal(event='request', kind=kind, zone=None, value=value)
                try:
                    res = self.wb.transact(frame, lambda **kw: self._journal(**kw))
                    for kind, value in normalized.items():
                        self._journal(event='delivered', kind=kind, zone=None, value=value, **res)
                    return {'ok': True, 'modes': normalized, **res}
                except Exception as exc:
                    for kind, value in normalized.items():
                        self._journal(event='error', kind=kind, zone=None, value=value, error=str(exc))
                    return {'ok': False, 'error': str(exc)}
        finally:
            self.busy = None
            self.lock.release()
