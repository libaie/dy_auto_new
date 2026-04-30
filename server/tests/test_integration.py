"""Server-side integration test — covers account groups, chains, nurture V2."""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def _auth():
    r = client.post('/api/auth/login', json={'username': 'admin', 'password': 'admin123'})
    assert r.status_code == 200, f'Login failed: {r.text}'
    return {'Authorization': f'Bearer {r.json()["token"]}'}


class TestAccountGroupsIntegration:
    """Account groups CRUD + member management integration."""

    def test_full_lifecycle(self):
        auth = _auth()

        # Create group A
        r = client.post('/api/account-groups', json={'name': 'integ-group-A', 'description': 'test'}, headers=auth)
        assert r.status_code == 200
        g1_id = r.json()['id']

        # Create group B
        r = client.post('/api/account-groups', json={'name': 'integ-group-B'}, headers=auth)
        assert r.status_code == 200
        g2_id = r.json()['id']

        # Duplicate name → 409
        r = client.post('/api/account-groups', json={'name': 'integ-group-A'}, headers=auth)
        assert r.status_code == 409

        # List
        r = client.get('/api/account-groups', headers=auth)
        assert r.status_code == 200
        assert r.json()['total'] >= 2

        # Detail
        r = client.get(f'/api/account-groups/{g1_id}', headers=auth)
        assert r.status_code == 200
        assert r.json()['name'] == 'integ-group-A'

        # Update
        r = client.put(f'/api/account-groups/{g1_id}', json={'name': 'integ-group-A-renamed'}, headers=auth)
        assert r.status_code == 200
        assert r.json()['name'] == 'integ-group-A-renamed'

        # Add member (acc-001 is seeded)
        r = client.post(f'/api/account-groups/{g1_id}/members',
                        json={'account_ids': ['acc-001']}, headers=auth)
        assert r.status_code == 200
        assert r.json()['count'] == 1

        # List members
        r = client.get(f'/api/account-groups/{g1_id}/members', headers=auth)
        assert r.status_code == 200
        assert r.json()['total'] == 1

        # Idempotent add
        r = client.post(f'/api/account-groups/{g1_id}/members',
                        json={'account_ids': ['acc-001']}, headers=auth)
        assert r.status_code == 200
        assert r.json()['count'] == 0

        # Nonexistent account → 400
        r = client.post(f'/api/account-groups/{g1_id}/members',
                        json={'account_ids': ['nonexistent']}, headers=auth)
        assert r.status_code == 400

        # Status filter
        r = client.get(f'/api/account-groups/{g1_id}/members?status=active', headers=auth)
        assert r.status_code == 200

        # Remove member
        r = client.request('DELETE', f'/api/account-groups/{g1_id}/members',
                           json={'account_ids': ['acc-001']}, headers=auth)
        assert r.status_code == 200
        assert r.json()['removed'] == 1

        # Verify member count is now 0
        r = client.get(f'/api/account-groups/{g1_id}', headers=auth)
        assert r.json()['member_count'] == 0

        # Delete group B
        r = client.delete(f'/api/account-groups/{g2_id}', headers=auth)
        assert r.status_code == 200

        # 404 after delete
        r = client.get(f'/api/account-groups/{g2_id}', headers=auth)
        assert r.status_code == 404

        # Delete group A (cascade)
        r = client.delete(f'/api/account-groups/{g1_id}', headers=auth)
        assert r.status_code == 200


class TestChainsIntegration:
    """Chain template CRUD + instance lifecycle integration."""

    def test_template_crud(self):
        auth = _auth()

        r = client.post('/api/chains/templates', json={
            'name': 'integ-chain',
            'description': 'test chain',
            'steps': [
                {'step_order': 1, 'type': 'nurture', 'label': 'step1', 'params': {'duration': 5}},
                {'step_order': 2, 'type': 'search_comment', 'label': 'step2', 'params': {'keyword': 'test', 'count': 3}},
            ]
        }, headers=auth)
        assert r.status_code == 200
        tmpl_id = r.json()['id']

        r = client.get('/api/chains/templates', headers=auth)
        assert r.status_code == 200
        assert r.json()['total'] >= 1

        r = client.get(f'/api/chains/templates/{tmpl_id}', headers=auth)
        assert r.status_code == 200
        assert len(r.json()['steps']) == 2

        r = client.put(f'/api/chains/templates/{tmpl_id}', json={'name': 'integ-chain-v2'}, headers=auth)
        assert r.status_code == 200
        assert r.json()['name'] == 'integ-chain-v2'

        r = client.delete(f'/api/chains/templates/{tmpl_id}', headers=auth)
        assert r.status_code == 200

    def test_instance_lifecycle(self):
        auth = _auth()

        # Create template
        r = client.post('/api/chains/templates', json={
            'name': 'lifecycle-chain',
            'steps': [
                {'step_order': 1, 'type': 'nurture', 'label': 'nurture', 'params': {'duration': 5}},
                {'step_order': 2, 'type': 'search_comment', 'label': 'comment', 'params': {'keyword': 'test', 'count': 3}},
            ]
        }, headers=auth)
        assert r.status_code == 200
        tmpl_id = r.json()['id']

        # Create instance for acc-001
        r = client.post('/api/chains/instances', json={
            'template_id': tmpl_id,
            'account_ids': ['acc-001'],
        }, headers=auth)
        assert r.status_code == 200
        data = r.json()
        assert data['created_count'] == 1
        assert 'acc-001' in data['created']

        # Find the chain task by listing all tasks and finding one with chain_instance_id
        r = client.get('/api/tasks', headers=auth)
        chain_tasks = [t for t in r.json()['tasks'] if t.get('chain_instance_id')]
        assert len(chain_tasks) >= 1

        step1_task = chain_tasks[0]
        assert step1_task['step_order'] == 1
        inst_id = step1_task['chain_instance_id']

        # Device poll + report step 1 (device endpoints need X-Device-Secret)
        from app.config import DEVICE_SECRET
        dev_headers = {'X-Device-Secret': DEVICE_SECRET}
        r = client.get('/api/device/poll', params={'device_id': 'dev-integ'}, headers=dev_headers)
        assert r.status_code == 200
        polled_task = r.json().get('task')
        assert polled_task is not None

        r = client.post('/api/device/report', json={
            'task_id': polled_task['id'], 'status': 'completed',
            'result': {'success_count': 1, 'details': 'done'}
        }, headers=dev_headers)
        assert r.status_code == 200

        # Step 2 task should be auto-created
        r = client.get('/api/tasks', headers=auth)
        step2_tasks = [t for t in r.json()['tasks']
                       if t.get('chain_instance_id') == inst_id and t.get('step_order') == 2
                       and t.get('status') == 'pending']
        assert len(step2_tasks) == 1

        # List instances
        r = client.get('/api/chains/instances', headers=auth)
        assert r.status_code == 200
        assert r.json()['total'] >= 1

        # Instance detail
        r = client.get(f'/api/chains/instances/{inst_id}', headers=auth)
        assert r.status_code == 200
        assert r.json()['current_step'] == 2

        # Cancel
        r = client.post(f'/api/chains/instances/{inst_id}/cancel', headers=auth)
        assert r.status_code == 200

        r = client.get(f'/api/chains/instances/{inst_id}', headers=auth)
        assert r.json()['status'] == 'cancelled'


class TestNurtureV2Integration:
    """Nurture V2 param validation integration."""

    def test_v2_creation(self):
        auth = _auth()
        r = client.post('/api/tasks', json={
            'type': 'nurture', 'account_id': 'acc-001',
            'params': {
                'sub_tasks': [
                    {'type': 'browse', 'count': 5},
                    {'type': 'like', 'count': 3},
                ],
                'completion_mode': 'all',
                'duration': 30,
            }
        }, headers=auth)
        assert r.status_code == 200

    def test_v2_empty_sub_tasks_rejected(self):
        auth = _auth()
        r = client.post('/api/tasks', json={
            'type': 'nurture', 'account_id': 'acc-001',
            'params': {'sub_tasks': []}
        }, headers=auth)
        assert r.status_code == 422

    def test_v2_invalid_type_rejected(self):
        auth = _auth()
        r = client.post('/api/tasks', json={
            'type': 'nurture', 'account_id': 'acc-001',
            'params': {'sub_tasks': [{'type': 'invalid', 'count': 1}]}
        }, headers=auth)
        assert r.status_code == 422

    def test_legacy_params_still_work(self):
        auth = _auth()
        r = client.post('/api/tasks', json={
            'type': 'nurture', 'account_id': 'acc-001',
            'params': {'duration': 15}
        }, headers=auth)
        assert r.status_code == 200
