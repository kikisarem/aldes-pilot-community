import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


RUN_MODULE = Path(__file__).parent / 'homeassistant/addon/run.py'
SPEC = importlib.util.spec_from_file_location('aldes_addon_run', RUN_MODULE)
ADDON_RUN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ADDON_RUN)


class AddonConfigTests(unittest.TestCase):
    def test_mqtt_options_are_saved_with_stable_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            private = Path(directory)
            options = {
                'bridge_name': 'PAC étage',
                'mqtt_host': 'core-mosquitto',
                'mqtt_port': 1883,
                'mqtt_username': 'aldes_bridge',
                'mqtt_password': 'private-password',
                'mqtt_ssl': False,
            }
            first_path = ADDON_RUN.mqtt_config(options, private)
            first = json.loads(first_path.read_text())
            options['mqtt_password'] = 'updated-password'
            second = json.loads(ADDON_RUN.mqtt_config(options, private).read_text())

        self.assertEqual(first['host'], 'core-mosquitto')
        self.assertEqual(first['port'], 1883)
        self.assertEqual(first['name'], 'PAC étage')
        self.assertFalse(first['ssl'])
        self.assertTrue(first['id'].startswith('aldes_'))
        self.assertEqual(second['id'], first['id'])
        self.assertEqual(second['password'], 'updated-password')

    def test_unconfigured_mqtt_is_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertIsNone(ADDON_RUN.mqtt_config({
                    'mqtt_host': '',
                    'mqtt_port': 1883,
                    'mqtt_username': '',
                    'mqtt_password': '',
                }, Path(directory)))
            self.assertIsNone(ADDON_RUN.mqtt_config({
                    'mqtt_host': 'core-mosquitto',
                    'mqtt_port': 1883,
                    'mqtt_username': '',
                    'mqtt_password': '',
                }, Path(directory)))

    def test_mqtt_supports_anonymous_broker_and_requires_complete_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = ADDON_RUN.mqtt_config({
                'mqtt_host': 'mqtt.example.local',
                'mqtt_port': 1883,
                'mqtt_username': '',
                'mqtt_password': '',
            }, Path(directory))
            self.assertEqual(json.loads(config_path.read_text())['host'], 'mqtt.example.local')
            with self.assertRaisesRegex(SystemExit, 'les deux identifiants MQTT'):
                ADDON_RUN.mqtt_config({
                    'mqtt_host': 'mqtt.example.local',
                    'mqtt_port': 1883,
                    'mqtt_username': 'bridge',
                    'mqtt_password': '',
                }, Path(directory))

    def test_mqtt_configuration_validates_host_and_port(self):
        base = {'mqtt_username': 'bridge', 'mqtt_password': 'secret'}
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(SystemExit, 'hôte MQTT valide'):
                ADDON_RUN.mqtt_config({**base, 'mqtt_host': 'bad host', 'mqtt_port': 1883}, Path(directory))
            with self.assertRaisesRegex(SystemExit, 'port MQTT'):
                ADDON_RUN.mqtt_config({**base, 'mqtt_host': 'core-mosquitto', 'mqtt_port': 70000}, Path(directory))


if __name__ == '__main__':
    unittest.main()
