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

def _extract_ecodes_from_off_tag(add):
    """Extract E-code(s) from OFF tag. Uses 'id' (canonical e.g. en:e472a-...) and 'name'."""
    codes = set()
    tag_id = add.get('id', '')

    # 1. Tag id: try to extract canonical numeric portion (handles e1414, e14xx, e472a)
    m = re.search(r'e(\d+)([a-z]{0,2})?(?:-|$)', tag_id, re.I)
    if m:
        digits = m.group(1)
        suffix = (m.group(2) or '').upper()
        # If suffix contains 'X' (e.g. 'XX'), treat as a range prefix (E14 -> matches E1400-E1499)
        if 'X' in suffix:
            codes.add('E' + digits + 'XX')
        elif suffix:
            codes.add('E' + digits + suffix)
        else:
            codes.add('E' + digits)

    # 2. Parse the human-readable name for explicit codes like "E472a" or "E 472a"
    raw_name = add.get('name', '') or ''
    for m in re.finditer(r'E\s*(\d{1,4})([A-Za-z]{0,2})', raw_name, re.I):
        digits = m.group(1)
        suffix = (m.group(2) or '').upper()
        if 'X' in suffix:
            codes.add('E' + digits + 'XX')
        elif suffix:
            codes.add('E' + digits + suffix)
        else:
            codes.add('E' + digits)

    return codes

def _pick_off_name(name_field):
    if isinstance(name_field, str):
        return name_field
    if isinstance(name_field, dict):
        preferred_keys = ('en', 'xx')
        for key in preferred_keys:
            val = name_field.get(key)
            if isinstance(val, str) and val.strip():
                return val
        for val in name_field.values():
            if isinstance(val, str) and val.strip():
                return val
    return ''

def _fetch_off_additives():
    """Fetch additives from OFF facets endpoint, with fallback to static taxonomy."""
    primary_url = "https://world.openfoodfacts.org/facets/additives.json"
    fallback_url = "https://static.openfoodfacts.org/data/taxonomies/additives.json"

    # Primary source: facets endpoint (already in the expected 'tags' format)
    try:
        response = requests.get(primary_url, headers={"User-Agent": USER_AGENT}, timeout=20)
        response.raise_for_status()
        payload = response.json()
        tags = payload.get("tags", [])
        if isinstance(tags, list) and tags:
            print(f"Loaded {len(tags)} additives from OFF facets endpoint.")
            return tags
        print("OFF facets endpoint returned no tags. Falling back to static taxonomy...")
    except Exception as e:
        print(f"Primary OFF fetch failed: {e}. Falling back to static taxonomy...")

    # Fallback source: static taxonomy (dict keyed by 'en:e1440', etc.)
    try:
        response = requests.get(fallback_url, headers={"User-Agent": USER_AGENT}, timeout=20)
        response.raise_for_status()
        payload = response.json()

        if not isinstance(payload, dict):
            print("Fallback OFF taxonomy response is not a dictionary.")
            return []

        additives = []
        for raw_key, meta in payload.items():
            if not isinstance(raw_key, str):
                continue
            if not isinstance(meta, dict):
                meta = {}

            tag_id = raw_key.split(':', 1)[1] if ':' in raw_key else raw_key
            if not tag_id:
                continue

            name = _pick_off_name(meta.get('name')) or tag_id.upper()
            additives.append({
                'id': tag_id,
                'name': name,
                'url': f"https://world.openfoodfacts.org/facets/additives/{tag_id}",
                'sameAs': meta.get('sameAs', []) if isinstance(meta.get('sameAs'), list) else []
            })

        print(f"Loaded {len(additives)} additives from OFF static taxonomy fallback.")
        return additives
    except Exception as e:
        print(f"Fallback OFF fetch failed: {e}")
        return []

def update_enumbers_from_off_additives_logic():
    global enumbers
    print("Fetching master additive list from OFF...")
    additives = _fetch_off_additives()
    if not additives:
        print("Error fetching OFF additives from both primary and fallback sources.")
        return 0

    # 1. Build map of E-Codes from Open Food Facts (id + name, normalize case)
    additive_dict = {}
    for add in additives:
        for code in _extract_ecodes_from_off_tag(add):
            if code:
                additive_dict[code.upper()] = add

    updated = 0
    # Build a set of prefixes for range tags (e.g. E14XX -> prefix 'E14') to match local codes
    range_prefixes = set()
    for k in additive_dict.keys():
        if k.endswith('XX'):
            # store 'E14' for 'E14XX'
            range_prefixes.add(k[:-2])

    # 2. Match your local list against the OFF map
    for entry in enumbers:
        code = entry.get('code', '').upper()

        matched = False
        # 1) Exact match
        if code in additive_dict:
            add = additive_dict[code]
            matched = True
        else:
            # 2) Prefix match for range tags (E14XX should match E1414, E1420 etc.)
            for prefix in range_prefixes:
                if code.startswith(prefix):
                    add = additive_dict.get(prefix + 'XX')
                    if add:
                        matched = True
                        break

        if matched:
            entry['openfoodfacts_additive'] = {
                'name': add.get('name'),
                'url': add.get('url'),
                'sameAs': add.get('sameAs', [])
            }
            entry.pop('removed', None)
            updated += 1
        else:
            entry['removed'] = True

    save_enumbers(enumbers)
    print(f"Sync complete. Matched {updated} official E-numbers.")
    return updated

@app.route('/api/enumbers', methods=['GET'])
def get_enumbers():
    query = request.args.get('q', '').strip().lower()
    limit = request.args.get('limit', type=int, default=1000)
    limit = min(max(1, limit), 5000)  # clamp 1-5000
    results = [e for e in enumbers if query in e['code'].lower() or query in e['name'].lower()] if query else enumbers
    return jsonify(results[:limit])

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
