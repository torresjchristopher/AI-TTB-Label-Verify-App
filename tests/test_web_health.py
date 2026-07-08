from fastapi.testclient import TestClient
from web_app import app


def test_health_endpoint():
    client = TestClient(app)
    response = client.get('/api/health')
    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'ok'
    assert data['local_only'] is True
    assert data['max_files'] >= 50
