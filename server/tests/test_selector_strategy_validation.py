"""API contract for explicit geometry, without rewriting legacy strategy JSON."""
import json
import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture
def client():
    # No lifespan: conftest supplies an isolated seeded in-memory DB.
    return TestClient(app)

def create(client, strategy, **extra):
    return client.post('/api/selectors', content=json.dumps({
        'action_name': 'geometry_' + uuid.uuid4().hex, 'strategies': [strategy], **extra,
    }), headers={'Content-Type': 'application/json'})

@pytest.mark.parametrize('strategy', [
    {'type': 'coordinate', 'position': {'space': 'content_normalized', 'x': 0, 'y': 1}},
    {'type': 'coordinate', 'position': {'space': 'capture_px', 'x': 0, 'y': 120}},
    {'type': 'coordinate', 'position': {'space': 'anchor_normalized', 'x': 0, 'y': 0},
     'anchor': {'type': 'id', 'value': 'container', 'match_mode': 'exact'}},
    {'type': 'text', 'value': 'send', 'offset': {'unit': 'dp', 'x': 0, 'y': -8},
     'region': {'space': 'screen_normalized', 'left': 0, 'top': 0, 'right': 1, 'bottom': 1}},
    {'type': 'image', 'template': 'send.png', 'source_resolution': '1080x2400',
     'source_density': 3, 'scales': [0.25, 0.9, 1, 1.1, 4], 'threshold': 0,
     'offset': {'unit': 'target_fraction', 'x': 0, 'y': -0.5}},
    {'type': 'coordinate', 'x_percent': 0, 'y_percent': 1, 'custom': {'keep': True}},
    {'type': 'image', 'template': 'old.png', 'x_percent': -20, 'y_percent': 120},
    {'conditions': [{'type': 'textContains', 'value': 'ok'}], 'logic': 'or', 'x_percent': 150},
    {'type': 'chain', 'steps': [{'type': 'classNameContains', 'value': 'View'}, {'nav': 'parent'}]},
])
def test_valid_geometry_preserves_exact_strategy_json(client, strategy):
    response = create(client, strategy)
    assert response.status_code == 200, response.text
    assert response.json()['strategies'] == [strategy]

@pytest.mark.parametrize('fields', [
    {'position': None}, {'offset': None}, {'region': []}, {'anchor': []},
    {'position': {'space': [], 'x': 0, 'y': 0}},
    {'offset': {'unit': [], 'x': 0, 'y': 0}},
    {'region': {'space': [], 'left': 0, 'top': 0, 'right': 1, 'bottom': 1}},
    {'anchor': {'type': [], 'value': 'ok'}},
    {'anchor': {'type': 'text', 'value': 'ok', 'match_mode': []}},
    {'region': {'space': 'anchor_normalized', 'left': 0, 'top': 0, 'right': 1, 'bottom': 1}},
    {'position': {'space': 'wrong', 'x': 0, 'y': 0}},
    {'position': {'space': 'screen_normalized', 'x': -0.1, 'y': 0}},
    {'position': {'space': 'content_normalized', 'x': 1.01, 'y': 0}},
    {'position': {'space': 'screen_px', 'x': -1, 'y': 0}},
    {'position': {'space': 'screen_px', 'x': True, 'y': 0}},
    {'position': {'space': 'screen_normalized', 'x': float('nan'), 'y': 0}},
    {'position': {'space': 'screen_normalized', 'x': 0}},
    {'position': {'space': 'anchor_normalized', 'x': 0, 'y': 0}},
    {'offset': {'unit': 'percent', 'x': 0, 'y': 0}},
    {'offset': {'unit': 'px', 'x': float('inf'), 'y': 0}},
    {'offset': {'unit': 'dp', 'x': '3', 'y': 0}},
    {'region': {'space': 'capture_px', 'left': 0, 'top': 0, 'right': 1, 'bottom': 1}},
    {'region': {'space': 'content_normalized', 'left': 0.8, 'top': 0, 'right': 0.2, 'bottom': 1}},
    {'region': {'space': 'content_normalized', 'left': 0, 'top': 1, 'right': 1, 'bottom': 1}},
    {'region': {'space': 'screen_normalized', 'left': 0, 'top': 0, 'right': 2, 'bottom': 1}},
    {'anchor': {'type': 'action', 'value': 'other'}},
    {'anchor': {'type': 'text', 'value': ''}},
    {'anchor': {'type': 'text', 'value': 'ok', 'action': 'recursive'}},
    {'source_resolution': '0x2400'}, {'source_resolution': '1080*2400'},
    {'source_density': 0}, {'source_density': float('inf')}, {'source_density': 10 ** 400},
    {'scales': []}, {'scales': [1] * 6}, {'scales': [0.24]}, {'scales': [4.01]},
    {'scales': [float('nan')]}, {'scales': ['1']},
    {'threshold': 1.1}, {'x_percent': float('nan')},
    {'conditions': [{'type': 'text', 'value': 'ok', 'offset': {'unit': 'dp', 'x': 0, 'y': float('inf')}}]},
    {'steps': [{'type': 'text', 'value': 'ok', 'region': {'space': 'content_normalized', 'left': 1, 'top': 0, 'right': 0, 'bottom': 1}}]},
])
def test_invalid_geometry_is_rejected_at_create(client, fields):
    response = create(client, {'type': 'image', 'template': 'test.png', **fields})
    assert response.status_code == 400, response.text
    saved = create(client, {'type': 'image', 'template': 'test.png'}).json()
    updated = client.put('/api/selectors/' + saved['action_name'], content=json.dumps({
        'strategies': [{'type': 'image', 'template': 'test.png', **fields}],
    }), headers={'Content-Type': 'application/json'})
    assert updated.status_code == 400, updated.text
    assert client.get('/api/selectors/' + saved['action_name']).json()['strategies'] == saved['strategies']

@pytest.mark.parametrize('strategy', [
    {'type': 'coordinate', 'x_percent': 0.5, 'y_percent': 0.5},
    {'type': 'text', 'value': 'ok', 'position': {'space': 'content_normalized', 'x': 0, 'y': 0}},
    {'conditions': [{'type': 'coordinate', 'x_percent': 0, 'y_percent': 0}]},
])
def test_page_detect_rejects_coordinate_evidence(client, strategy):
    assert create(client, strategy, purpose='page_detect').status_code == 400

def test_update_validates_effective_purpose_and_strategies(client):
    response = create(client, {'type': 'coordinate', 'x_percent': 0, 'y_percent': 0})
    name = response.json()['action_name']
    assert client.put('/api/selectors/' + name, json={'purpose': 'page_detect'}).status_code == 400
    assert client.get('/api/selectors/' + name).json()['purpose'] == 'locate'
    assert client.put('/api/selectors/' + name, json={
        'purpose': 'page_detect', 'strategies': [{'type': 'text', 'value': 'ready'}],
    }).status_code == 200
    assert client.put('/api/selectors/' + name, json={
        'strategies': [{'type': 'coordinate', 'position': {'space': 'screen_px', 'x': 0, 'y': 1}}],
    }).status_code == 400
    assert client.put('/api/selectors/' + name, json={
        'strategies': [{'type': 'text', 'value': 'ready', 'offset': {'unit': 'px', 'x': 0, 'y': 'bad'}}],
    }).status_code == 400

def test_update_validates_same_composite_key_as_mutation(client):
    name = 'profiles_' + uuid.uuid4().hex
    for profile, strategy in [('default', {'type': 'text', 'value': 'ready'}),
                              ('720x1600', {'type': 'coordinate', 'x_percent': 0, 'y_percent': 0})]:
        assert client.post('/api/selectors', json={
            'action_name': name, 'resolution_profile': profile, 'strategies': [strategy],
        }).status_code == 200
    assert client.put('/api/selectors/' + name, json={
        'resolution_profile': '720x1600', 'purpose': 'page_detect',
    }).status_code == 400
