"""Offline decoding of the 0x21 report clock; never communicates with the PAC."""
import datetime

def decode_clock21(frame):
    if len(frame) != 90 or frame[:5] != bytes.fromhex('fffd5aff21') or frame[-2] != 0xfe or sum(frame) % 256:
        raise ValueError('Invalid complete local report21')
    value = int.from_bytes(frame[77:81], 'little')
    return datetime.datetime(1980 + (value >> 25), (value >> 21) & 15,
                             (value >> 16) & 31, (value >> 11) & 31,
                             (value >> 5) & 63, (value & 31) * 2)

if __name__ == '__main__':
    import argparse, json
    from pathlib import Path
    from raw_audit import audit
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log', type=Path)
    args = parser.parse_args()
    rows = []
    for frame in audit(args.log.read_bytes())['frames']:
        if frame['opcode'] != '21':
            continue
        rows.append({'uptime_ms': frame['uptime'], 'line': frame['line'],
                     'pac_clock_local': decode_clock21(bytes.fromhex(frame['hex'])).isoformat()})
    print(json.dumps(rows, indent=2))
