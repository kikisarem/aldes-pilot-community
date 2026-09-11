"""Generate a HA package (JSON is valid YAML), no credentials included."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from mqtt_bridge import AIR, ECS

REPORT = 'sensor.aldes_pilot_rapport'
COMMAND_READY = "{{ is_state('sensor.aldes_pilot_rapport', 'online') and not state_attr('sensor.aldes_pilot_rapport', 'busy') and (state_attr('sensor.aldes_pilot_rapport', 'cooldown_s') | float(0)) <= 0 and (state_attr('sensor.aldes_pilot_rapport', 'recovery') or {}).get('status') != 'recovering' }}"

AVAILABLE = "{{ is_state('sensor.aldes_pilot_rapport', 'online') }}"

def action(command, data):
    return [
        {'if': [{'condition': 'template', 'value_template': "{{ not (" + COMMAND_READY[3:-3] + ") }}"}],
         'then': [{'stop': 'Commande indisponible : attendre la fin de l’envoi, de la reprise ou du délai de 45 secondes.', 'error': True}]},
        {'action': 'rest_command.aldes_pilot_' + command, 'data': data, 'response_variable': 'reply'},
        {'if': [{'condition': 'template', 'value_template': "{{ reply.status != 200 or reply.content is not mapping or not reply.content.get('ok', false) }}"}],
         'then': [{'stop': 'Commande refusée ou livraison non confirmée ; consulter Aldes Pilot.', 'error': True}]},
        {'action': 'homeassistant.update_entity', 'target': {'entity_id': REPORT}},
    ]

def package():
    selects = []
    for key, options in [('air', AIR), ('ecs', ECS)]:
        values = json.dumps(options, ensure_ascii=False)
        selects.append({'name': 'Aldes Pilot ' + key.upper(), 'unique_id': 'aldes_pilot_rest_' + key,
            'availability': AVAILABLE, 'optimistic': False, 'options': '{{ ' + values + ' }}',
            'state': "{% set v = (state_attr('" + REPORT + "', '" + key + "') or {}).get('actual') %}{{ " + values + "[v] if v is integer and 0 <= v < " + str(len(options)) + " else none }}",
            'select_option': action(key, {'mode': '{{ ' + values + '.index(option) }}'})})
    numbers = []
    for zone in range(1, 5):
        numbers.append({'name': f'Aldes Pilot Consigne K{zone}', 'unique_id': f'aldes_pilot_rest_k{zone}',
            'availability': AVAILABLE, 'optimistic': False, 'min': 16, 'max': 30, 'step': 0.5, 'unit_of_measurement': '°C',
            'state': "{{ ((state_attr('" + REPORT + "', 'zones') or {}).get('" + str(zone) + "') or {}).get('actual') }}",
            'set_value': action('setpoint', {'zone': zone, 'temperature': '{{ value }}'})})
    commands = {}
    for key, path, payload in [('air', 'air', '{"mode": {{ mode | int }} }'),
                               ('ecs', 'ecs', '{"mode": {{ mode | int }} }'),
                               ('setpoint', 'setpoint', '{"zone": {{ zone | int }}, "temperature": {{ temperature | float }} }'),
                               ('vacation_clear', 'vacation/clear', '{}')]:
        commands['aldes_pilot_' + key] = {'url': 'http://127.0.0.1:8771/api/' + path,
            'method': 'POST', 'headers': {'x-pilot-ui': '1'}, 'content_type': 'application/json', 'payload': payload, 'timeout': 100}
    return {'rest': [{'resource': 'http://127.0.0.1:8771/api/state', 'scan_interval': 5, 'timeout': 4,
        'sensor': [{'name': 'Aldes Pilot rapport', 'unique_id': 'aldes_pilot_rest_report',
            'value_template': "{{ 'online' if value_json.available else 'offline' }}",
            'json_attributes': ['air', 'ecs', 'zones', 'recovery', 'busy', 'cooldown_s']}]}],
        'rest_command': commands,
        'template': [{'select': selects, 'number': numbers,
            'binary_sensor': [{'name': 'Aldes Pilot Commandes disponibles', 'unique_id': 'aldes_pilot_rest_commands_ready', 'state': COMMAND_READY, 'attributes': {'attente_secondes': "{{ state_attr('sensor.aldes_pilot_rapport', 'cooldown_s') | int(0) }}"}}],
            'button': [{'name': 'Aldes Pilot Annuler vacances', 'unique_id': 'aldes_pilot_rest_vacation_clear',
                'availability': AVAILABLE, 'press': action('vacation_clear', {})}]}]}

if __name__ == '__main__':
    destination = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name('aldes_pilot.yaml')
    destination.write_text(json.dumps(package(), ensure_ascii=False, indent=2) + '\n')
