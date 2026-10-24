"""Read existing RAW logs only. No socket or control path."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

from raw_audit import audit
from report_clock import decode_clock21
from report21 import decode21


def snapshot(raw, file_mtime, now):
    parsed = audit(raw)
    frames = parsed['frames']
    lines = raw.decode(errors='replace').splitlines()
    ticks = [int(m[1]) for line in lines if (m := re.match(r'\[\s*(\d+)\]', line))]
    status_entry = next(((i, line) for i, line in reversed(list(enumerate(lines, 1))) if 'STATUS mounted=' in line), (0, ''))
    status_line, status = status_entry
    file_age = max(0, now - file_mtime)
    healthy = 0 <= now - file_mtime <= 25 and all(re.search(re.escape(word) + r'(?:\s|$)', status) for word in
        ('mounted=1', 'rx_errors=0', 'rx_rearm_failed=0'))
    current_stream = parsed['streams'] - 1
    latest_boundary = max((b['line'] for b in parsed['boundaries']), default=0)
    status_tick = re.match(r'\[\s*(\d+)\]', status)
    status_recent = bool(status_tick and ticks and 0 <= ticks[-1] - int(status_tick[1]) <= 25000)
    # Firmware loss counter is cumulative: the collector being offline can
    # increase it without corrupting any report received after reconnection.
    # Require two current-session STATUS samples with a stable counter, then
    # accept only frames after that stable interval began. A new increase (or
    # reset) invalidates earlier frames until a new complete report arrives.
    loss_samples = []
    for number, line in enumerate(lines, 1):
        if number > latest_boundary and 'STATUS mounted=' in line:
            match = re.search(r'log perdus=(\d+)(?:\s|$)', line)
            if match:
                loss_samples.append((number, int(match[1])))
            else:
                loss_samples.append((number, None))
    stable_start = None
    if len(loss_samples) >= 2 and loss_samples[-1][1] is not None:
        latest_loss = loss_samples[-1][1]
        stable = []
        for sample in reversed(loss_samples):
            if sample[1] != latest_loss:
                break
            stable.append(sample)
        if len(stable) >= 2:
            stable_start = stable[-1][0]
    healthy = (healthy and status_line > latest_boundary and status_recent
               and stable_start is not None)
    active = frames[-1] if frames else None
    active_valid = bool(active and active['stream'] == current_stream and active['line'] > latest_boundary)
    out = {
        'read_at_utc': datetime.datetime.fromtimestamp(now, datetime.timezone.utc).isoformat(),
        'schema_version': 1, 'writes_supported': False,
        'capture_healthy': bool(healthy), 'capture_age_seconds': round(file_age, 3),
        'active_report': active['opcode'] if active_valid else None,
        'pages': {}, 'parse_errors': parsed['errors'],
    }
    latest_pages = {frame['opcode']: frame for frame in frames}
    for opcode, frame in latest_pages.items():
        same_session = frame['stream'] == current_stream and frame['line'] > latest_boundary
        age = (ticks[-1] - frame['uptime']) / 1000 + file_age if ticks and same_session else None
        fresh = bool(healthy and same_session and frame['line'] > stable_start and age is not None and 0 <= age <= 60
                     and not any(e['line'] >= frame['line'] for e in parsed['errors']))
        is_active = active_valid and opcode == active['opcode']
        page = {
            'length': frame['length'], 'uptime_ms': frame['uptime'], 'source_line': frame['line'],
            'age_seconds': round(age, 3) if age is not None else None,
            'same_session': same_session, 'fresh': fresh,
            'active': bool(is_active), 'available': bool(fresh and is_active),
            'sha256': hashlib.sha256(bytes.fromhex(frame['hex'])).hexdigest(),
        }
        if opcode == '21' and frame['length'] == 90:
            data = bytes.fromhex(frame['hex'])
            try:
                page['decoded'] = decode21(data)
            except ValueError as exc:
                page['decode_error'] = str(exc)
                page['available'] = False
            if 'decoded' in page:
                try:
                    page['decoded']['pac_clock_local'] = decode_clock21(data).isoformat()
                    page['decoded']['clock_validation'] = 'DOS/FAT format corroborated; PAC calendar is not host time'
                except ValueError as exc:
                    page['decoded']['pac_clock_local'] = None
                    page['decoded']['clock_error'] = str(exc)
        else:
            page['decoding_status'] = 'Raw page retained; field semantics not validated'
        out['pages'][opcode] = page
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--log', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--watch', action='store_true')
    parser.add_argument('--seconds', type=int, default=86400)
    args = parser.parse_args()
    end = time.monotonic() + args.seconds
    while True:
        try:
            # Take mtime before reading: a concurrent append cannot make old bytes look newer.
            mtime = args.log.stat().st_mtime
            state = snapshot(args.log.read_bytes(), mtime, time.time())
        except Exception as exc:
            state = {'capture_healthy': False, 'pages': {}, 'error': str(exc), 'writes_supported': False}
        tmp = args.output.with_suffix('.tmp')
        with tmp.open('w') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, args.output)
        if not args.watch or time.monotonic() >= end:
            break
        time.sleep(2)


if __name__ == '__main__':
    main()
