"""Garde USB : rallume l'USB du Pico (commande USBON) quand il l'a éteint.

Un envoi interrompu peut laisser le Pico en ABORTED_USB_OFF avec usb=0.
USBON ne rejoue rien et n'envoie aucune trame à la PAC ; il relance seulement
la pile USB du Pico.
Jamais d'ARM ni de SEND ici. Budget : 3 USBON par heure, au-delà on bloque et on journalise.
"""
import fcntl, json, os, socket, time
from pathlib import Path
from pico import PICO_HOST, PICO_PORT, ROOT, TOKEN

PERIOD = 30
BUDGET, WINDOW = 3, 3600
STATE = ROOT / 'private/usbguard.json'
EVENTS = ROOT / 'private/usbguard-events.jsonl'


def decide(status, attempts, now):
    """status = dict STATUS du Pico. Renvoie (action, attempts) ; action in None/'usbon'/'blocked'."""
    attempts = [t for t in attempts if 0 <= now - t < WINDOW]
    if status.get('usb') != '0' or status.get('tx') == 'PENDING':
        return None, attempts
    if len(attempts) >= BUDGET:
        return 'blocked', attempts
    return 'usbon', attempts + [now]


def session(cmds):
    with socket.create_connection((PICO_HOST, PICO_PORT), timeout=5) as s, s.makefile('rwb', buffering=0) as f:
        def line():
            raw = f.readline(2048)
            if not raw.endswith(b'\n'):
                raise RuntimeError('connexion interrompue')
            return raw.decode('ascii').strip()
        if line() != 'WORKBENCH 1 AUTH_REQUIRED':
            raise RuntimeError('protocole inattendu')
        f.write(('AUTH ' + TOKEN.read_text().strip() + '\n').encode())
        if line() != 'OK AUTH':
            raise RuntimeError('auth refusée')
        out = []
        for c in cmds:
            f.write((c + '\n').encode()); out.append(line())
        return out


def parse(reply):
    if not reply.startswith('STATUS '):
        raise RuntimeError('STATUS invalide')
    return dict(i.split('=', 1) for i in reply.split()[1:])


def journal(**row):
    with EVENTS.open('a') as f:
        f.write(json.dumps({'utc': time.time(), **row}) + '\n')


def main():
    try:
        st = json.loads(STATE.read_text())
    except (OSError, ValueError):
        st = {'attempts': []}
    while True:
        try:
            with (ROOT / 'private/tx.lock').open('a') as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    time.sleep(PERIOD); continue
                status = parse(session(['STATUS'])[0])
                action, st['attempts'] = decide(status, st.get('attempts', []), time.time())
                st.update(checked=time.time(), usb=status.get('usb'), mounted=status.get('mounted'), action=action)
                if action == 'usbon':
                    journal(event='usbon', before=status, reply=session(['USBON'])[0])
                elif action == 'blocked' and st.get('last_blocked', 0) < time.time() - WINDOW:
                    st['last_blocked'] = time.time(); journal(event='blocked', before=status)
            tmp = STATE.with_suffix('.tmp'); tmp.write_text(json.dumps(st)); tmp.replace(STATE)
        except Exception as exc:   # Pico injoignable ou occupé : on retente au tour suivant
            st['error'] = repr(exc)
        time.sleep(PERIOD)


if __name__ == '__main__':
    main()
