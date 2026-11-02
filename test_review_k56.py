"""Synthetic K5/K6 review regressions; no hardware access."""
import importlib.util
import json
import unittest
from pathlib import Path

from pico import frame_setpoint
from report21 import decode21

ROOT = Path(__file__).parent
SPEC = importlib.util.spec_from_file_location('rest_generator', ROOT / 'homeassistant/rest/generate.py')
GENERATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GENERATOR)


class K56ReviewTests(unittest.TestCase):
    def test_rest_package_is_parseable_and_reproducible(self):
        package = json.loads((ROOT / 'homeassistant/rest/aldes_pilot.yaml').read_text())
        self.assertEqual(package, GENERATOR.package())
        numbers = package['template'][0]['number']
        self.assertEqual([n['unique_id'] for n in numbers],
                         [f'aldes_pilot_rest_k{z}' for z in range(1, 7)])
        for zone, number in enumerate(numbers, 1):
            self.assertEqual(number['set_value'][1]['data']['zone'], zone)

    def test_new_commands_mask_every_other_zone(self):
        for zone in (5, 6):
            frame = frame_setpoint(zone, 22.5)
            self.assertEqual(len(frame), 88)
            self.assertEqual(sum(frame) % 256, 0)
            for other in range(1, 7):
                start = 13 + 2 * (other - 1)
                expected = (2250).to_bytes(2, 'little') if other == zone else b'\xff\xff'
                self.assertEqual(frame[start:start+2], expected)
            self.assertEqual(frame[81:83], b'\xff\xff')

    def test_synthetic_readback_does_not_claim_hardware_validation(self):
        frame = bytearray(90)
        frame[:5] = bytes.fromhex('fffd5aff21')
        frame[21:25] = (2250).to_bytes(2, 'little') + (2300).to_bytes(2, 'little')
        frame[-2] = 254
        frame[-1] = -sum(frame) % 256
        zones = decode21(frame)['zones']
        self.assertEqual([z['setpoint_c'] for z in zones[4:]], [22.5, 23])
        for zone in zones[4:]:
            self.assertIn('pending', zone['setpoint_validation'])


if __name__ == '__main__':
    unittest.main()
