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
from werkzeug.middleware.proxy_fix import ProxyFix
from functools import wraps  
app = Flask(__name__)

# Security: Apply ProxyFix if behind a reverse proxy
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Security: Configure CORS properly - be more restrictive in production
CORS(app, 
     origins=["http://localhost:5000", "http://127.0.0.1:5000"],  # Add your production domains
     allow_headers=["Content-Type", "Authorization"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])

# Security: Add comprehensive security headers
@app.after_request
def add_security_headers(response):
    # Content Security Policy - prevents XSS attacks
    csp = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "  # Allow inline scripts for now
        "style-src 'self' 'unsafe-inline'; "   # Allow inline styles
        "img-src 'self' data: https:; "        # Allow images from self, data URIs, and HTTPS
        "connect-src 'self' https://world.openfoodfacts.org; "  # Allow API calls to OpenFoodFacts
        "font-src 'self'; "
        "object-src 'none'; "                  # Block plugins
        "base-uri 'self'; "                    # Prevent base tag injection
        "form-action 'self'; "                 # Restrict form submissions
        "frame-ancestors 'none'; "             # Prevent clickjacking
        "upgrade-insecure-requests"            # Force HTTPS upgrades
    )
    response.headers['Content-Security-Policy'] = csp

    # X-Content-Type-Options - prevent MIME type sniffing
    response.headers['X-Content-Type-Options'] = 'nosniff'

    # X-Frame-Options - prevent clickjacking
    response.headers['X-Frame-Options'] = 'DENY'

    # X-XSS-Protection - enable XSS filtering
    response.headers['X-XSS-Protection'] = '1; mode=block'

    # Strict-Transport-Security - enforce HTTPS (uncomment for production with HTTPS)
    # response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'

    # Referrer-Policy - control referrer information
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

    # Permissions-Policy - control browser features
    response.headers['Permissions-Policy'] = (
        "geolocation=(), "
        "microphone=(), "
        "camera=(), "
        "payment=(), "
        "usb=(), "
        "magnetometer=(), "
        "gyroscope=(), "
        "speaker=()"
    )

    return response

EN_FILE = 'enumbers.json'

USER_AGENT = "ENumbersApp/1.0 (contact@example.com)"

# Parse command-line argument for editing
parser = argparse.ArgumentParser()
parser.add_argument('--allow-editing', action='store_true', help='Allow editing (POST, PUT, DELETE) endpoints')
args, unknown = parser.parse_known_args()
EDITING_ALLOWED = args.allow_editing

# Security: Input sanitization functions
def sanitize_string(input_str, max_length=200):
    """Sanitize string input to prevent XSS and limit length"""
    if not isinstance(input_str, str):
        return ""

    # Remove HTML tags and limit length
    cleaned = bleach.clean(input_str.strip(), tags=[], strip=True)
    return cleaned[:max_length]

def sanitize_code(code):
    """Sanitize E-number code input"""
    if not isinstance(code, str):
        return ""

    # Only allow E followed by numbers, letters, and specific characters
    sanitized = re.sub(r'[^E0-9a-zA-Z\-]', '', code.upper().strip())
    return sanitized[:10]  # Limit length

def validate_json_input(data, required_fields):
    """Validate JSON input and required fields"""
    if not data or not isinstance(data, dict):
        return False, "Invalid JSON data"

    for field in required_fields:
        if field not in data or not data[field]:
            return False, f"Missing required field: {field}"

    return True, None

def check_editing_allowed():
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # This part only runs when a user actually hits the URL
            if not EDITING_ALLOWED:
                return jsonify({'error': 'Editing is disabled on this server.'}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def load_enumbers():
    try:
        with open(EN_FILE, encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading enumbers.json: {e}")
        return []

def save_enumbers(data):
    try:
        # Security: Validate data before saving
        if not isinstance(data, list):
            raise ValueError("Data must be a list")

        # Remove spaces from the 'code' field for every entry before saving
        for entry in data:
            if 'code' in entry:
                entry['code'] = sanitize_code(entry['code'])
            if 'name' in entry:
                entry['name'] = sanitize_string(entry['name'], 500)

        with open(EN_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving enumbers.json: {e}")
        raise

# Helper function to fetch Open Food Facts data for a barcode
def fetch_openfoodfacts_product(barcode):
    # Security: Sanitize barcode input
    clean_barcode = re.sub(r'[^0-9E\-a-zA-Z]', '', str(barcode))[:50]

    url = f"https://world.openfoodfacts.org/api/v2/product/{clean_barcode}.json"
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get("product")
    except Exception as e:
        print(f"Error fetching {clean_barcode}: {e}")
    return None

# Helper function to fetch all additives (E numbers) from Open Food Facts

def fetch_all_additives():
    url = "https://world.openfoodfacts.org/facets/additives.json"
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(url, headers=headers, timeout=20)
        if response.status_code == 200:
            data = response.json()
            return data.get("tags", [])
    except Exception as e:
        print(f"Error fetching additives: {e}")
    return []

# Helper function to update enumbers.json with the latest E-number (additive) data from Open Food Facts

def update_enumbers_from_off_additives_logic():
    global enumbers
    additives = fetch_all_additives()
    if not additives:
        print('Failed to fetch additives from Open Food Facts')
        return 0

    def normalize_code(code):
        # Extract E-number using regex, remove spaces/dashes, uppercase
        match = re.match(r'(E\d+)', code.replace(' ', '').replace('-', '').upper())
        return match.group(1) if match else code.replace(' ', '').replace('-', '').upper()

    # Build a dict for quick lookup by normalized E number code (e.g., E330, E322, etc.)
    additive_dict = {}
    for add in additives:
        if 'name' in add and add['name'].startswith('E'):
            # Extract E-number using regex from the additive name
            match = re.match(r'(E\d+)', add['name'].replace(' ', '').replace('-', '').upper())
            if match:
                code = match.group(1)
                additive_dict[code] = add

    # Build a set of all local codes for quick lookup
    local_codes = set(normalize_code(entry.get('code', '')) for entry in enumbers)
    updated = 0
    code_to_entry = {normalize_code(entry.get('code', '')): entry for entry in enumbers}

    # 1. Update existing entries and mark as removed if not present in Open Food Facts
    for entry in enumbers:
        entry_code = normalize_code(entry.get('code', ''))
        if entry_code in additive_dict:
            add = additive_dict[entry_code]
            # Prepare the openfoodfacts_additive field with links
            off_add = {
                'name': add.get('name'),
                'url': add.get('url'),
                'sameAs': add.get('sameAs', [])
            }
            entry['openfoodfacts_additive'] = off_add
            # Remove 'removed' flag if present
            if 'removed' in entry:
                entry.pop('removed')
            updated += 1
        else:
            # Mark as removed, but do not delete
            entry['removed'] = True
            entry.pop('openfoodfacts_additive', None)

    # 2. Add new E numbers from Open Food Facts if not present locally
    for code, add in additive_dict.items():
        if code not in code_to_entry:
            new_entry = {
                'code': code,
                'name': add.get('name', code),
                'openfoodfacts_additive': {
                    'name': add.get('name'),
                    'url': add.get('url'),
                    'sameAs': add.get('sameAs', [])
                }
            }
            enumbers.append(new_entry)
            updated += 1

    save_enumbers(enumbers)
    enumbers = load_enumbers()
    print(f'Updated {updated} entries with Open Food Facts additive data (including new and removed).')
    return updated
# Endpoint to update enumbers.json with Open Food Facts data
@app.route('/api/update_openfoodfacts', methods=['POST'])
@check_editing_allowed()  # NB check for edit perms
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
    save_enumbers(enumbers)
    return jsonify({'message': f'Updated {updated} entries with Open Food Facts data.'})

# Flask route for manual update
@app.route('/api/update_enumbers_from_off_additives', methods=['POST'])
def update_enumbers_from_off_additives():
    denied = check_editing_allowed()
    if denied:
        return denied
    global enumbers
    updated = update_enumbers_from_off_additives_logic()
    if updated == 0:
        return jsonify({'error': 'Failed to fetch additives from Open Food Facts'}), 500
    return jsonify({'message': f'Updated {updated} entries with Open Food Facts additive data.'})

# Schedule daily update using APScheduler
scheduler = BackgroundScheduler()
scheduler.add_job(update_enumbers_from_off_additives_logic, 'interval', days=1)
scheduler.start()

enumbers = load_enumbers()

@app.route('/')
def index():
    return send_from_directory('.', 'enumbers.html')

@app.route('/enumbers.html')
def enumbers_page():
    return send_from_directory('.', 'enumbers.html')

@app.route('/api/enumbers', methods=['GET'])
def get_enumbers():
    global enumbers
    # Security: Sanitize query parameter
    query = sanitize_string(request.args.get('q', ''), 100).lower()

    # Security: Limit results to prevent DoS
    limit = min(int(request.args.get('limit', 1000)), 2000)

    if query:
        filtered = [e for e in enumbers if query in e['code'].lower() or query in e['name'].lower()]
        return jsonify(filtered[:limit])
    return jsonify(enumbers[:limit])

@app.route('/api/enumbers', methods=['POST'])
def create_enumber():
    denied = check_editing_allowed()
    if denied:
        return denied

    global enumbers
    data = request.get_json()

    # Security: Validate input
    is_valid, error_msg = validate_json_input(data, ['code', 'name'])
    if not is_valid:
        return jsonify({'error': error_msg}), 400

    # Security: Sanitize inputs
    clean_code = sanitize_code(data['code'])
    clean_name = sanitize_string(data['name'], 500)

    if not clean_code or not clean_name:
        return jsonify({'error': 'Invalid code or name format'}), 400

    # Check for duplicates
    if any(e['code'] == clean_code for e in enumbers):
        return jsonify({'error': 'E-number already exists'}), 409

    new_entry = {'code': clean_code, 'name': clean_name}
    enumbers.append(new_entry)
    save_enumbers(enumbers)
    return jsonify({'message': 'Created', 'enumber': new_entry}), 201

@app.route('/api/enumbers/<code>', methods=['PUT'])
def update_enumber(code):
    denied = check_editing_allowed()
    if denied:
        return denied

    global enumbers
    data = request.get_json()

    # Security: Validate input
    is_valid, error_msg = validate_json_input(data, ['name'])
    if not is_valid:
        return jsonify({'error': error_msg}), 400

    # Security: Sanitize inputs
    clean_code = sanitize_code(code)
    clean_name = sanitize_string(data['name'], 500)

    if not clean_code or not clean_name:
        return jsonify({'error': 'Invalid code or name format'}), 400

    for e in enumbers:
        if e['code'] == clean_code:
            e['name'] = clean_name
            save_enumbers(enumbers)
            return jsonify({'message': 'Updated', 'enumber': e})
    return jsonify({'error': 'E-number not found'}), 404

@app.route('/api/enumbers/<code>', methods=['DELETE'])
def delete_enumber(code):
    denied = check_editing_allowed()
    if denied:
        return denied

    global enumbers
    # Security: Sanitize code parameter
    clean_code = sanitize_code(code)

    if not clean_code:
        return jsonify({'error': 'Invalid code format'}), 400

    for i, e in enumerate(enumbers):
        if e['code'] == clean_code:
            removed = enumbers.pop(i)
            save_enumbers(enumbers)
            return jsonify({'message': 'Deleted', 'enumber': removed})
    return jsonify({'error': 'E-number not found'}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
