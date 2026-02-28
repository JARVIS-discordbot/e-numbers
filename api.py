from flask import Flask, jsonify, request, abort, send_from_directory
import json
import os
import requests
from apscheduler.schedulers.background import BackgroundScheduler
import argparse
from flask_cors import CORS
import re
import html
import bleach
import time
from functools import wraps
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)

# Security: Apply ProxyFix if behind a reverse proxy
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Security: Configure CORS properly
CORS(app, 
     origins=["http://localhost:5000", "http://127.0.0.1:5000"], 
     allow_headers=["Content-Type", "Authorization"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])

@app.after_request
def add_security_headers(response):
    csp = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "connect-src 'self' https://world.openfoodfacts.org; "
        "font-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none'; "
        "upgrade-insecure-requests"
    )
    response.headers['Content-Security-Policy'] = csp
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = "geolocation=(), microphone=(), camera=(), payment=()"
    return response

EN_FILE = 'enumbers.json'
USER_AGENT = "ENumbersApp/1.0 (contact@example.com)"

parser = argparse.ArgumentParser()
parser.add_argument('--allow-editing', action='store_true', help='Allow editing endpoints')
args, unknown = parser.parse_known_args()
EDITING_ALLOWED = args.allow_editing

# --- Utility Functions ---

def sanitize_string(input_str, max_length=200):
    if not isinstance(input_str, str): return ""
    cleaned = bleach.clean(input_str.strip(), tags=[], strip=True)
    return cleaned[:max_length]

def sanitize_code(code):
    if not isinstance(code, str): return ""
    sanitized = re.sub(r'[^E0-9a-zA-Z\-]', '', code.upper().strip())
    return sanitized[:10]

def validate_json_input(data, required_fields):
    if not data or not isinstance(data, dict):
        return False, "Invalid JSON data"
    for field in required_fields:
        if field not in data or not data[field]:
            return False, f"Missing required field: {field}"
    return True, None

def check_editing_allowed(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not EDITING_ALLOWED:
            return jsonify({'error': 'Editing is disabled on this server.'}), 403
        return f(*args, **kwargs)
    return decorated_function

# --- Data Management ---

def load_enumbers():
    try:
        if not os.path.exists(EN_FILE): return []
        with open(EN_FILE, encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading: {e}")
        return []

def save_enumbers(data):
    try:
        for entry in data:
            if 'code' in entry: entry['code'] = sanitize_code(entry['code'])
            if 'name' in entry: entry['name'] = sanitize_string(entry['name'], 500)
        with open(EN_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving: {e}")

# --- Open Food Facts Logic ---

def fetch_openfoodfacts_product(barcode):
    clean_barcode = re.sub(r'[^0-9E\-a-zA-Z]', '', str(barcode))[:50]
    url = f"https://world.openfoodfacts.org/api/v2/product/{clean_barcode}.json"
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=10)
        return response.json().get("product") if response.status_code == 200 else None
    except: return None

def fetch_all_additives():
    url = "https://world.openfoodfacts.org/facets/additives.json"
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
        return response.json().get("tags", []) if response.status_code == 200 else []
    except: return []

def update_enumbers_from_off_additives_logic():
    global enumbers
    additives = fetch_all_additives()
    if not additives: return 0

    def normalize_code(code):
        match = re.search(r'(E\d+)', code.replace(' ', '').replace('-', '').upper())
        return match.group(1) if match else code.replace(' ', '').replace('-', '').upper()

    additive_dict = {}
    for add in additives:
        if 'name' in add and add['name'].startswith('E'):
            code = normalize_code(add['name'])
            additive_dict[code] = add

    code_to_entry = {normalize_code(entry.get('code', '')): entry for entry in enumbers}
    updated = 0

    for entry in enumbers:
        entry_code = normalize_code(entry.get('code', ''))
        if entry_code in additive_dict:
            add = additive_dict[entry_code]
            entry['openfoodfacts_additive'] = {
                'name': add.get('name'),
                'url': add.get('url'),
                'sameAs': add.get('sameAs', [])
            }
            entry.pop('removed', None)
        else:
            entry['removed'] = True
        updated += 1

    for code, add in additive_dict.items():
        if code not in code_to_entry:
            enumbers.append({
                'code': code,
                'name': add.get('name', code),
                'openfoodfacts_additive': {
                    'name': add.get('name'), 'url': add.get('url'), 'sameAs': add.get('sameAs', [])
                }
            })
            updated += 1

    save_enumbers(enumbers)
    return updated

# --- Routes ---

@app.route('/api/update_openfoodfacts', methods=['POST'])
@check_editing_allowed
def update_openfoodfacts():
    global enumbers
    updated = 0
    for entry in enumbers:
        barcode = entry.get('code')
        if barcode:
            product = fetch_openfoodfacts_product(barcode)
            if product:
                entry['openfoodfacts'] = product
                updated += 1
            time.sleep(1) # Rate limiting
    save_enumbers(enumbers)
    return jsonify({'message': f'Updated {updated} entries'})

@app.route('/api/update_enumbers_from_off_additives', methods=['POST'])
@check_editing_allowed
def update_enumbers_from_off_additives():
    updated = update_enumbers_from_off_additives_logic()
    if updated == 0: return jsonify({'error': 'Failed fetch'}), 500
    return jsonify({'message': f'Updated {updated} entries'})

@app.route('/api/enumbers', methods=['GET'])
def get_enumbers():
    query = sanitize_string(request.args.get('q', ''), 100).lower()
    try:
        limit = min(int(request.args.get('limit', 1000)), 2000)
    except (ValueError, TypeError):
        limit = 1000

    results = enumbers
    if query:
        results = [e for e in enumbers if query in e['code'].lower() or query in e['name'].lower()]
    return jsonify(results[:limit])

@app.route('/api/enumbers', methods=['POST'])
@check_editing_allowed
def create_enumber():
    data = request.get_json()
    is_valid, err = validate_json_input(data, ['code', 'name'])
    if not is_valid: return jsonify({'error': err}), 400
    
    clean_code = sanitize_code(data['code'])
    if any(e['code'] == clean_code for e in enumbers):
        return jsonify({'error': 'Exists'}), 409
        
    new_entry = {'code': clean_code, 'name': sanitize_string(data['name'], 500)}
    enumbers.append(new_entry)
    save_enumbers(enumbers)
    return jsonify(new_entry), 201

@app.route('/api/enumbers/<code>', methods=['PUT'])
@check_editing_allowed
def update_enumber(code):
    data = request.get_json()
    clean_code = sanitize_code(code)
    for e in enumbers:
        if e['code'] == clean_code:
            e['name'] = sanitize_string(data.get('name', e['name']), 500)
            save_enumbers(enumbers)
            return jsonify(e)
    return jsonify({'error': 'Not found'}), 404

@app.route('/api/enumbers/<code>', methods=['DELETE'])
@check_editing_allowed
def delete_enumber(code):
    clean_code = sanitize_code(code)
    global enumbers
    for i, e in enumerate(enumbers):
        if e['code'] == clean_code:
            removed = enumbers.pop(i)
            save_enumbers(enumbers)
            return jsonify(removed)
    return jsonify({'error': 'Not found'}), 404

@app.route('/')
@app.route('/enumbers.html')
def index():
    return send_from_directory('.', 'enumbers.html')

# --- Startup ---

enumbers = load_enumbers()
scheduler = BackgroundScheduler()
scheduler.add_job(update_enumbers_from_off_additives_logic, 'interval', days=1)
scheduler.start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
