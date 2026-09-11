#!/usr/bin/env python3
"""Local RX/TX workbench. No retries and no scheduled/automatic PAC packets."""
import argparse
import datetime
import json
from pathlib import Path
import socket
import time
BASE = Path(__file__).resolve().parent

def read_line(stream):
    raw = stream.readline(1024)
    if not raw or not raw.endswith(b'\n'):
        raise RuntimeError('Connexion perdue / réponse incomplète : résultat inconnu, ne pas réessayer automatiquement.')
    return raw.decode('ascii').strip()

def request(stream, line):
    stream.write(line.encode('ascii') + b'\n')
    return read_line(stream)

def status_fields(s):
    if not s.startswith('STATUS '):
        raise RuntimeError(s)
    return dict(item.split('=', 1) for item in s.split()[1:])

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--host', required=True)
    p.add_argument('--token-file', type=Path, default=BASE/'private/control.token')
    sub = p.add_subparsers(dest='action', required=True)
    for name in ('status', 'stop', 'usb-on'):
        sub.add_parser(name)
    send = sub.add_parser('send', help='Un envoi USB explicite, sans correction de checksum ni retry')
    send.add_argument('--hex', required=True)
    logs = sub.add_parser('logs', help='Suit un fichier existant sans déconnecter le collecteur')
    logs.add_argument('file', type=Path)
    a = p.parse_args()
    if a.action == 'logs':
        with a.file.open() as f:
            f.seek(0, 2)
            while True:
                line = f.readline()
                if line:
                    print(line, end='', flush=True)
                else:
                    time.sleep(.2)
    payload = None
    if a.action == 'send':
        payload = bytes.fromhex(a.hex)
        if not 1 <= len(payload) <= 512:
            p.error('1 à 512 octets requis')
    record = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'action': a.action, 'host': a.host}
    if payload is not None:
        record['hex'] = payload.hex()
    journal_dir = BASE/'private'
    journal_dir.mkdir(mode=0o700, exist_ok=True)
    def journal(event):
        with (journal_dir/'operations.jsonl').open('a') as out:
            out.write(json.dumps({**record, **event})+'\n')
            out.flush()
            import os
            os.fsync(out.fileno())
    try:
        with socket.create_connection((a.host, 8766), timeout=5) as sock:
            with sock.makefile('rwb', buffering=0) as stream:
                if read_line(stream) != 'WORKBENCH 1 AUTH_REQUIRED':
                    raise RuntimeError('Mauvais protocole de contrôle')
                token = a.token_file.read_text().strip()
                if len(token) != 64 or any(c not in '0123456789abcdef' for c in token):
                    raise RuntimeError('Fichier jeton invalide')
                if request(stream, 'AUTH '+token) != 'OK AUTH':
                    raise RuntimeError('Authentification refusée')
                if payload is None:
                    cmd = {'status': 'STATUS', 'stop': 'STOP', 'usb-on': 'USBON'}[a.action]
                    result = request(stream, cmd)
                    print(result); journal({'result': result})
                    return
                state = status_fields(request(stream, 'STATUS'))
                record['id'] = int(state['last'])+1
                tx_timeout_ms = int(state.get('tx_timeout_ms', '3000'))
                if not 3000 <= tx_timeout_ms <= 90000:
                    raise RuntimeError('Délai USB annoncé hors limites : aucun envoi.')
                record['tx_timeout_ms'] = tx_timeout_ms
                if state['mounted'] != '1' or state['tx'] == 'PENDING':
                    raise RuntimeError('USB indisponible ou occupé')
                if not request(stream, 'ARM').startswith('OK ARM '):
                    raise RuntimeError('Armement refusé')
                # Durable intention BEFORE bytes are transmitted, even on uncertain disconnect.
                journal({'result': 'INTENT_BEFORE_SEND'})
                result = request(stream, f"SEND {record['id']} {payload.hex()}")
                print(result); journal({'result': result})
                if result != 'OK SUBMITTED':
                    raise RuntimeError(result)
                end = time.monotonic()+tx_timeout_ms/1000+5
                while time.monotonic()<end:
                    result = request(stream, 'STATUS')
                    if result.startswith('ERR USB_RESET'):
                        time.sleep(.1); continue
                    state = status_fields(result)
                    if state['tx'] != 'PENDING':
                        print(result); journal({'result': result})
                        if state['tx'] != 'USB_DONE':
                            raise RuntimeError('Pas de réception USB complète confirmée ; aucun retry.')
                        print('Réception USB confirmée ; effet applicatif à vérifier dans la capture et sur la PAC.')
                        return
                    time.sleep(.25)
                raise RuntimeError('Délai dépassé ; résultat inconnu. Aucun retry.')
    except Exception as exc:
        journal({'result': 'ERROR_OR_UNKNOWN', 'detail': str(exc)})
        raise SystemExit(str(exc))

if __name__ == '__main__':
    main()
