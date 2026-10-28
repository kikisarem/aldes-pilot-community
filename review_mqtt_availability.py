"""Offline review probe: fake broker and API, no device or network access."""
import json
import os
import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import patch

import mqtt_bridge


class StopProbe(Exception):
    pass


class FakeClient:
    def __init__(self):
        self.published = []
        self.wills = []

    def will_set(self, *args, **kwargs):
        self.wills.append(args)

    def connect_async(self, *args, **kwargs):
        pass

    def loop_start(self):
        self.on_connect(self, None, None, types.SimpleNamespace(is_failure=False), None)

    def publish(self, topic, payload, **kwargs):
        self.published.append((topic, payload))
        return types.SimpleNamespace(wait_for_publish=lambda **kwargs: None)

    def subscribe(self, *args, **kwargs):
        pass

    def disconnect(self):
        pass

    def loop_stop(self):
        pass


client = FakeClient()
module = types.ModuleType('paho.mqtt.client')
module.CallbackAPIVersion = types.SimpleNamespace(VERSION2=2)
module.Client = lambda *args, **kwargs: client
paho = types.ModuleType('paho')
mqtt = types.ModuleType('paho.mqtt')
paho.mqtt = mqtt
mqtt.client = module
fresh = {'available': True, 'air': {'actual': 1}, 'ecs': {'actual': 1},
         'zones': {'1': {'actual': 22, 'active': True}}}
calls = []
phase = 0


def fake_api(path, body=None):
    calls.append((path, body))
    return fresh if phase == 0 else {'available': False}


def next_cycle(seconds):
    global phase
    if phase == 0:
        phase = 1
        return
    messages = [payload for topic, payload in client.published
                if topic == 'aldes_pilot/review/read_availability']
    print('Availability after valid report then unavailable report:', messages)
    print('Last availability before shutdown:', messages[-1])
    before = len(calls)
    client.on_message(client, None, types.SimpleNamespace(
        topic='aldes_pilot/review/k1/set', payload=b'22', retain=False))
    print('Command API calls after unavailable report:', calls[before:])
    print('Configured wills:', client.wills)
    assert messages[-1] == 'offline', 'Stale PAC still advertised online'
    assert len(calls) == before, 'Command forwarded after PAC became unavailable'
    raise StopProbe()


with tempfile.TemporaryDirectory() as directory:
    config = Path(directory) / 'mqtt.json'
    config.write_text(json.dumps({'id': 'review', 'host': 'fake', 'port': 1883}))
    with patch.dict(sys.modules, {'paho': paho, 'paho.mqtt': mqtt,
                                 'paho.mqtt.client': module}), \
         patch.dict(os.environ, {'MQTT_CONFIG': str(config)}), \
         patch.object(mqtt_bridge, 'api', side_effect=fake_api), \
         patch.object(mqtt_bridge.time, 'sleep', side_effect=next_cycle):
        try:
            mqtt_bridge.main()
        except StopProbe:
            pass
