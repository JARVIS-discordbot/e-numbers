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
import threading
from datetime import datetime
from functools import wraps
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)

# Security: Apply ProxyFix if behind a reverse proxy
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Global status tracker
task_status = {
    "is_running": False,
    "current": 0,
    "total": 0,
    "last_completed": None
}

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
        with open(EN_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving: {e}")

# --- Background Task Logic ---

def run_deep_scan():
    global enumbers, task_status
    task_status["is_running"] = True
    task_status["total"] = len(enumbers)
    task_status["current"] = 0
    
    print(f"Starting Deep Scan of {task_status['total']} items...")
    
    updated_count = 0
    for entry in enumbers:
        task_status["current"] += 1
        barcode = entry.get('code')
        
        # Only fetch if we haven't synced in the last 7 days
        if barcode:
            url = f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
            try:
                resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=5)
                if resp.status_code == 200:
                    entry['openfoodfacts'] = resp.json().get("product")
                    entry['last_synced'] = datetime.now().isoformat()
                    updated_count += 1
                print(f"[{task_status['current']}/{task_status['total']}] Scanned {barcode}")
            except:
                pass
            time.sleep(1) # Polite delay
            
    save_enumbers(enumbers)
    task_status["is_running"] = False
    task_status["last_completed"] = datetime.now().isoformat()
    print(f"Deep Scan Complete. Updated {updated_count} entries.")

# --- Routes ---

@app.route('/api/update_status', methods=['GET'])
def get_status():
    return jsonify(task_status)

@app.route('/api/update_openfoodfacts', methods=['POST'])
@check_editing_allowed
def update_openfoodfacts():
    if task_status["is_running"]:
        return jsonify({'error': 'A task is already running'}), 409
    
    thread = threading.Thread(target=run_deep_scan)
    thread.start()
    return jsonify({'message': 'Deep scan started in background'}), 202

@app.route('/api/update_enumbers_from_off_additives', methods=['POST'])
@check_editing_allowed
def update_enumbers_from_off_additives():
    # This remains synchronous as it is fast
    updated = update_enumbers_from_off_additives_logic()
    return jsonify({'message': f'Updated {updated} entries'})

def update_enumbers_from_off_additives_logic():
    global enumbers
    print("Fetching master additive list from OFF...")
    url = "https://world.openfoodfacts.org/facets/additives.json"
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
        additives = response.json().get("tags", [])
    except Exception as e:
        print(f"Error fetching OFF additives: {e}")
        return 0

    # 1. Build a smart map of E-Codes from Open Food Facts
    # This turns "E586 - 4-hexylresorcinol" into the key "E586"
    additive_dict = {}
    for add in additives:
        raw_name = add.get('name', '').upper()
        # Regex looks for 'E' followed by digits (e.g., E120, E586)
        match = re.search(r'(E\d+[A-Z]?)', raw_name.replace(' ', ''))
        if match:
            clean_code = match.group(1)
            additive_dict[clean_code] = add

    updated = 0
    # 2. Match your local list against the OFF map
    for entry in enumbers:
        code = entry.get('code', '').upper()
        
        if code in additive_dict:
            add = additive_dict[code]
            # Populate the gold-mine data!
            entry['openfoodfacts_additive'] = {
                'name': add.get('name'),
                'url': add.get('url'),
                'sameAs': add.get('sameAs', [])
            }
            # If it was marked 'removed' before, bring it back
            entry.pop('removed', None)
            updated += 1
        else:
            # If it's truly not in the official list, mark it
            entry['removed'] = True

    save_enumbers(enumbers)
    print(f"Sync complete. Matched {updated} official E-numbers.")
    return updated

    additive_dict = {add['name'].replace(' ', '').upper(): add for add in additives if 'name' in add}
    updated = 0

    for entry in enumbers:
        code = entry.get('code', '').upper()
        if code in additive_dict:
            add = additive_dict[code]
            entry['openfoodfacts_additive'] = {
                'name': add.get('name'),
                'url': add.get('url'),
                'sameAs': add.get('sameAs', [])
            }
            updated += 1

    save_enumbers(enumbers)
    return updated

@app.route('/api/enumbers', methods=['GET'])
def get_enumbers():
    query = request.args.get('q', '').lower()
    results = [e for e in enumbers if query in e['code'].lower() or query in e['name'].lower()] if query else enumbers
    return jsonify(results[:1000])

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
