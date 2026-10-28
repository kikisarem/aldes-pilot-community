"""Real MQTT + HTTP + queue with simulated USB, inside a network-isolated lab."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import urllib.request

import paho.mqtt.client as mqtt

ROOT = Path(__file__).resolve().parent
IDENTITY = 'review_queue_lab'
BASE = 'aldes_pilot/' + IDENTITY
events = []
event_lock = threading.Lock()
connected, subscribed = threading.Event(), threading.Event()
checks = []
processes = []
peer = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id='review_test_peer')


def on_connect(client, userdata, flags, reason, properties):
    assert not reason.is_failure
    client.subscribe(BASE + '/#')
    connected.set()


def on_message(client, userdata, message):
    with event_lock:
        events.append((message.topic, message.payload.decode(), message.retain))


peer.on_connect = on_connect
peer.on_subscribe = lambda *args: subscribed.set()
peer.on_message = on_message


def wait(predicate, description, seconds=25):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            if predicate():
                checks.append(description)
                print('PASS:', description, flush=True)
                return
        except (OSError, ValueError):
            pass
        time.sleep(.1)
    raise AssertionError('Timeout: ' + description)


def api(path='/api/state', body=None):
    request = urllib.request.Request('http://127.0.0.1:8771' + path,
        data=None if body is None else json.dumps(body).encode(),
        headers={'Content-Type': 'application/json', 'x-pilot-ui': '1'})
    with urllib.request.urlopen(request, timeout=3) as response:
        return json.load(response)


def publish(key, value, retain=False):
    peer.publish(BASE + '/' + key + '/set', value, qos=1, retain=retain).wait_for_publish(timeout=3)


def latest(topic):
    with event_lock:
        return next((payload for key, payload, _ in reversed(events) if key == BASE + '/' + topic), None)


def frame_count():
    return len(api('/review/state')['frames'])


try:
    environment = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1',
                   'PICO_HOST': '127.0.0.1', 'PICO_TOKEN': '/tmp/nonexistent-token'}
    logs = open('/tmp/review-server.log', 'w')
    server = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'review_queue_server:app',
        '--host', '127.0.0.1', '--port', '8771', '--log-level', 'warning'],
        cwd=ROOT, env=environment, stdout=logs, stderr=subprocess.STDOUT)
    processes.append(server)
    wait(lambda: api()['available'], 'HTTP test server ready')
    peer.connect('127.0.0.1', 1883, keepalive=10)
    peer.loop_start()
    assert connected.wait(5) and subscribed.wait(5)
    # Retained messages must be present before the bridge subscribes: a live
    # retained publication is delivered with retain=False to existing subscribers.
    publish('k1', '23', retain=True)
    config = Path('/tmp/review-mqtt.json')
    config.write_text(json.dumps({'id': IDENTITY, 'host': '127.0.0.1', 'port': 1883}))
    bridge_logs = open('/tmp/review-bridge.log', 'w')
    bridge = subprocess.Popen([sys.executable, 'mqtt_bridge.py'], cwd=ROOT,
        env={**environment, 'MQTT_CONFIG': str(config)},
        stdout=bridge_logs, stderr=subprocess.STDOUT)
    processes.append(bridge)
    wait(lambda: latest('read_availability') == 'online', 'MQTT observed state online')
    wait(lambda: latest('command_result') and 'Retained' in latest('command_result'),
         'Retained command rejected on subscription')
    time.sleep(5.5)
    assert frame_count() == 0
    publish('k1', '', retain=True)
    publish('k1', '20')
    publish('k1', '23')
    publish('k2', '24')
    wait(lambda: frame_count() == 1, 'MQTT latest K1 plus K2 reaches one combined frame')
    frame = bytes.fromhex(api('/review/state')['frames'][0]['hex'])
    assert frame[13:17] == bytes.fromhex('fc086009')
    assert frame[17:21] == b'\xff' * 4 and frame[81:83] == b'\xff\xff'
    assert sum(frame) % 256 == 0
    wait(lambda: latest('k1/state') == '23.0' and latest('k2/state') == '24.0',
         'MQTT reports actual combined setpoints')
    publish('air', 'Chauffage Confort')
    publish('air', 'Arrêt')
    publish('ecs', 'Boost')
    wait(lambda: frame_count() == 2, 'Latest air and ECS reach one combined mode frame')
    frame = bytes.fromhex(api('/review/state')['frames'][1]['hex'])
    assert frame[81:83] == b'\x00\x02' and frame[13:21] == b'\xff' * 8
    api('/review/control', {'cooldown_s': 30})
    publish('k1', '22')
    wait(lambda: 'k1' in api()['command_queue']['pending'], 'Command held during cooldown')
    api('/review/control', {'available': False})
    wait(lambda: api()['command_queue']['result']['status'] == 'error' and
         not api()['command_queue']['pending'], 'Loss of PAC state discards pending commands')
    wait(lambda: latest('read_availability') == 'offline', 'MQTT marks unavailable while broker stays connected')
    publish('k2', '21')
    wait(lambda: latest('command_result') and 'Lecture PAC indisponible' in latest('command_result'),
         'New MQTT command refused while state unavailable')
    api('/review/control', {'available': True, 'cooldown_s': 0})
    wait(lambda: latest('read_availability') == 'online', 'Observed state recovers')
    time.sleep(6)
    assert frame_count() == 2, 'Discarded commands replayed after recovery'
    checks.append('No replay after state recovery')
    api('/review/control', {'fail_transport': True})
    publish('k1', '21')
    wait(lambda: frame_count() == 3 and api()['command_queue']['result']['status'] == 'error',
         'Unknown simulated USB delivery becomes queue error')
    time.sleep(6)
    assert frame_count() == 3 and not api()['command_queue']['pending']
    checks.append('Unknown delivery not retried')
    bridge.kill()
    bridge.wait(timeout=5)
    wait(lambda: latest('read_availability') == 'offline', 'MQTT last will marks bridge unavailable')
    print(json.dumps({'ok': True, 'checks': checks, 'transport': 'simulated',
                      'frames': api('/review/state')['frames']}), flush=True)
finally:
    for process in reversed(processes):
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    peer.disconnect()
    peer.loop_stop()
