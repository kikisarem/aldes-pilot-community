"""Synthetic framing and availability regressions; no device access."""
import unittest
from reader import snapshot


def chunk(n, t, data):
    return f'[{t}] OUT xfer #{n}, {len(data)} octets\n[{t}]    raw +000: '+data.hex(' ').upper()+'\n'


def status(t):
    return f'[{t}] STATUS mounted=1 rx_errors=0 rx_rearm_failed=0 log perdus=0\n'


class ReaderTests(unittest.TestCase):
    def setUp(self):
        self.frame = bytearray(90)
        self.frame[:5] = bytes.fromhex('fffd5aff21')
        # Deliberately unset clock: this must not suppress valid setpoints.
        self.frame[-2] = 254
        self.frame[-1] = (-sum(self.frame)) % 256
        self.head = '[collector] synthetic start\n'+status(900)+chunk(1, 1000, self.frame[:64])

    def read(self, tail='', now=1800000000):
        return snapshot((self.head+tail+status(1002)).encode(), 1800000000, now)

    def test_partial(self):
        self.assertNotIn('21', self.read()['pages'])

    def test_bad_checksum(self):
        tail = bytearray(self.frame[64:]); tail[-1] ^= 1
        self.assertNotIn('21', self.read(chunk(2, 1001, tail))['pages'])

    def test_invalid_clock_does_not_hide_valid_settings(self):
        page = self.read(chunk(2, 1001, self.frame[64:]))['pages']['21']
        self.assertTrue(page['available'])
        self.assertIsNone(page['decoded']['pac_clock_local'])
        self.assertIn('clock_error', page['decoded'])
        self.assertEqual(page['decoded']['zones'], [])

    def test_only_populated_zones_are_returned(self):
        self.frame[13:15] = (2100).to_bytes(2, 'little')
        self.frame[53:55] = (2143).to_bytes(2, 'little')
        self.frame[13+2*8:15+2*8] = (1900).to_bytes(2, 'little')
        self.frame[53+2*8:55+2*8] = (1850).to_bytes(2, 'little')
        self.frame[-1] = (-sum(self.frame[:-1])) % 256
        self.head = '[collector] synthetic start\n'+status(900)+chunk(1, 1000, self.frame[:64])
        page = self.read(chunk(2, 1001, self.frame[64:]))['pages']['21']
        self.assertEqual([zone['zone'] for zone in page['decoded']['zones']], ['K1', 'K9'])
        self.assertEqual(page['decoded']['zones'][0]['setpoint_c'], 21)
        self.assertEqual(page['decoded']['zones'][0]['temperature_candidate_c'], 21.43)
        self.assertEqual(page['decoded']['zones'][1]['setpoint_c'], 19)
        self.assertEqual(page['decoded']['zones'][1]['temperature_candidate_c'], 18.5)
        slots = page['decoded']['zone_slots']
        self.assertEqual(len(slots), 9)
        self.assertEqual((slots[0]['zone'], slots[0]['active'], slots[0]['setpoint_raw'], slots[0]['temperature_raw']), ('K1', True, 2100, 2143))
        self.assertEqual((slots[1]['zone'], slots[1]['active'], slots[1]['setpoint_raw'], slots[1]['temperature_raw']), ('K2', False, 0, 0))
        self.assertEqual((slots[8]['zone'], slots[8]['active'], slots[8]['setpoint_raw'], slots[8]['temperature_raw']), ('K9', True, 1900, 1850))

    def test_reset_between_fragments(self):
        self.assertNotIn('21', self.read('[1001] USB bus reset\n'+chunk(2, 1002, self.frame[64:]))['pages'])

    def test_transfer_gap(self):
        self.assertNotIn('21', self.read(chunk(3, 1001, self.frame[64:]))['pages'])

    def test_stale_capture(self):
        state = self.read(chunk(2, 1001, self.frame[64:]), now=1800000030)
        self.assertFalse(state['capture_healthy'])
        self.assertFalse(state['pages']['21']['available'])

    def test_old_status_not_reused_after_reset(self):
        raw = ('[collector] first\n'+status(999)+'[1000] USB bus reset\n'
               +chunk(1, 1001, self.frame[:64])+chunk(2, 1002, self.frame[64:]))
        state = snapshot(raw.encode(), 1800000000, 1800000000)
        self.assertFalse(state['capture_healthy'])
        self.assertFalse(state['pages']['21']['available'])
        waiting = snapshot((raw+status(1003)).encode(), 1800000000, 1800000000)
        self.assertFalse(waiting['pages']['21']['available'])
        raw += status(1003)+chunk(3,1004,self.frame[:64])+chunk(4,1005,self.frame[64:])+status(1006)
        recovered = snapshot(raw.encode(),1800000000,1800000000)
        self.assertTrue(recovered['pages']['21']['available'])

    def test_old_status_not_reused_during_continuous_raw(self):
        raw = ('[collector] first\n'+status(1000)
               +chunk(1, 40000, self.frame[:64])+chunk(2, 40001, self.frame[64:]))
        state = snapshot(raw.encode(), 1800000000, 1800000000)
        self.assertFalse(state['capture_healthy'])
        self.assertFalse(state['pages']['21']['available'])

    def test_active_page_changes(self):
        other = bytes.fromhex('fafd07ff4afebb')
        state = self.read(chunk(2, 1001, self.frame[64:])+chunk(3, 1002, other))
        self.assertEqual(state['active_report'], '4a')
        self.assertFalse(state['pages']['21']['available'])
        self.assertTrue(state['pages']['4a']['available'])


if __name__ == '__main__':
    unittest.main()
