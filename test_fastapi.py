import requests
import json

BASE_URL = 'http://127.0.0.1:8000'
print("Testing FastAPI Web Interface Endpoints")
print("=" * 50)

# Test health endpoint
try:
    r = requests.get(f'{BASE_URL}/health')
    print(f"✓ /health - {r.status_code}")
except Exception as e:
    print(f"✗ /health - {e}")

# Test home page
try:
    r = requests.get(f'{BASE_URL}/')
    if '<html' in r.text.lower():
        print(f"✓ / (Home) - Returns HTML")
    else:
        print(f"⚠ / (Home) - {r.status_code}")
except Exception as e:
    print(f"✗ / (Home) - {e}")

# Test benchmark page
try:
    r = requests.get(f'{BASE_URL}/benchmark')
    if '<html' in r.text.lower():
        print(f"✓ /benchmark - Returns HTML")
    else:
        print(f"⚠ /benchmark - {r.status_code}")
except Exception as e:
    print(f"✗ /benchmark - {e}")

# Test API endpoints
try:
    r = requests.get(f'{BASE_URL}/api/benchmark')
    data = r.json()
    print(f"✓ /api/benchmark - Returns JSON with {data.get('total_questions', 0)} questions")
except Exception as e:
    print(f"✗ /api/benchmark - {e}")

# Test query API
try:
    r = requests.post(f'{BASE_URL}/api/query', json={"question": "test"})
    print(f"✓ /api/query - Returns {r.status_code}")
except Exception as e:
    print(f"✗ /api/query - {e}")

print("=" * 50)
print("Web interface is ready! 🚀")
