"""Queue race regressions with a fake transport; no PAC/network access."""
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock

from pico import Pilot


class QueueReviewTests(unittest.TestCase):
    def wait_result(self, pilot, status):
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            queue = pilot.command_queue_state()
            if queue['current'] is None and (queue['result'] or {}).get('status') == status:
                return queue
            time.sleep(.005)
        self.fail(f'Queue did not reach {status}')

    def test_latest_single_setpoint_wins_during_state_check(self):
        with tempfile.TemporaryDirectory() as directory:
            pilot = Pilot(Path(directory))
            pilot.setpoint_debounce = 0
            checking = threading.Event()
            release = threading.Event()
            sent = threading.Event()

            def state():
                checking.set()
                self.assertTrue(release.wait(2))
                return {'available': True, 'recovery': {'status': 'ready'},
                        'busy': None, 'cooldown_s': 0}

            pilot.state = state
            pilot.send = Mock(side_effect=lambda *args: (sent.set() or {'ok': True}))
            pilot.enqueue('setpoint', 20, 1)
            self.assertTrue(checking.wait(2))
            pilot.enqueue('setpoint', 23, 1)
            release.set()
            self.assertTrue(sent.wait(2))
            pilot.send.assert_called_once_with('setpoint', 23, 1)

    def test_latest_single_mode_wins_during_state_check(self):
        with tempfile.TemporaryDirectory() as directory:
            pilot = Pilot(Path(directory))
            pilot.mode_debounce = 0
            checking = threading.Event()
            release = threading.Event()
            sent = threading.Event()

            def state():
                checking.set()
                self.assertTrue(release.wait(2))
                return {'available': True, 'recovery': {'status': 'ready'},
                        'busy': None, 'cooldown_s': 0}

            pilot.state = state
            pilot.send = Mock(side_effect=lambda *args: (sent.set() or {'ok': True}))
            pilot.enqueue('air', 1)
            self.assertTrue(checking.wait(2))
            pilot.enqueue('air', 0)
            release.set()
            self.assertTrue(sent.wait(2))
            pilot.send.assert_called_once_with('air', 0, None)

    def test_offline_drops_pending_commands_before_transport(self):
        with tempfile.TemporaryDirectory() as directory:
            pilot = Pilot(Path(directory))
            pilot.setpoint_debounce = 0
            pilot.state = lambda: {'available': False}
            pilot.send = Mock(side_effect=AssertionError('Must not send offline'))
            pilot.enqueue('setpoint', 23, 1)
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                result = pilot.command_queue_state()['result'] or {}
                if result.get('status') == 'error':
                    break
                time.sleep(.005)
            self.assertEqual(pilot.command_queue_state()['pending'], {})
            self.assertEqual(pilot.command_queue_state()['result']['status'], 'error')
            pilot.send.assert_not_called()

    def test_replaced_batch_reaches_one_frame_with_latest_values(self):
        with tempfile.TemporaryDirectory() as directory:
            pilot = Pilot(Path(directory))
            pilot.setpoint_debounce = 0
            checking, release = threading.Event(), threading.Event()

            def state():
                checking.set()
                self.assertTrue(release.wait(2))
                return {'available': True, 'recovery': {'status': 'ready'},
                        'busy': None, 'cooldown_s': 0, 'air': {'actual': 0}, 'health': {}}

            pilot.state = state
            pilot.wb.transact = Mock(return_value={'txid': 1, 'elapsed_s': 0})
            pilot.enqueue('setpoint', 20, 1)
            self.assertTrue(checking.wait(2))
            pilot.enqueue('setpoint', 23, 1)
            pilot.enqueue('setpoint', 24, 2)
            release.set()
            self.wait_result(pilot, 'delivered')
            pilot.wb.transact.assert_called_once()
            frame = pilot.wb.transact.call_args.args[0]
            self.assertEqual(frame[13:17], bytes.fromhex('fc086009'))
            self.assertEqual(frame[17:21], b'\xff' * 4)
            self.assertEqual(frame[81:83], b'\xff\xff')
            self.assertEqual(sum(frame) % 256, 0)

    def test_uncertain_transport_failure_is_not_replayed(self):
        with tempfile.TemporaryDirectory() as directory:
            pilot = Pilot(Path(directory))
            pilot.setpoint_debounce = 0
            pilot.state = lambda: {'available': True, 'recovery': {'status': 'ready'},
                                  'busy': None, 'cooldown_s': 0,
                                  'air': {'actual': 0}, 'health': {}}
            pilot.wb.transact = Mock(side_effect=RuntimeError('Delivery outcome unknown'))
            pilot.enqueue('setpoint', 23, 1)
            self.wait_result(pilot, 'error')
            time.sleep(.05)
            self.assertEqual(pilot.command_queue_state()['pending'], {})
            pilot.wb.transact.assert_called_once()


if __name__ == '__main__':
    unittest.main()
