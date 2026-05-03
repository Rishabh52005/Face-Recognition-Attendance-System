from attendance_web.app import app, create_access_token
import json

with app.test_client() as client:
    token = create_access_token(1, 'user', 'demo@example.com')
    try:
        client.set_cookie('access_token', token)
    except TypeError:
        client.set_cookie('localhost', 'access_token', token)
    response = client.get('/api/stats')
    print('Status:', response.status_code)
    print('Data:', json.dumps(response.get_json(), indent=2))

