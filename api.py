from flask import Flask, jsonify, request, abort, send_from_directory
import json
import os
import requests
import csv
import io
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
TASK_STATUS_DEFAULTS = {
    "is_running": False,
    "current": 0,
    "total": 0,
    "last_completed": None,
    "last_off_sync_started": None,
    "last_off_sync_completed": None,
    "last_off_sync_success": None,
    "last_off_sync_updated_count": 0,
    "last_off_sync_error": None,
    "last_off_sync_source": None
}
task_status = dict(TASK_STATUS_DEFAULTS)

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
STATUS_FILE = 'sync_status.json'
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

def load_task_status():
    if not os.path.exists(STATUS_FILE):
        return dict(TASK_STATUS_DEFAULTS)
    try:
        with open(STATUS_FILE, encoding='utf-8') as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"Error loading sync status: {e}")
        return dict(TASK_STATUS_DEFAULTS)

    if not isinstance(payload, dict):
        print("Error loading sync status: invalid format")
        return dict(TASK_STATUS_DEFAULTS)

    merged = dict(TASK_STATUS_DEFAULTS)
    for key in TASK_STATUS_DEFAULTS:
        if key in payload:
            merged[key] = payload[key]
    return merged

def save_task_status():
    try:
        temp_file = f"{STATUS_FILE}.tmp"
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(task_status, f, ensure_ascii=False, indent=2)
        os.replace(temp_file, STATUS_FILE)
    except OSError as e:
        print(f"Error saving sync status: {e}")

task_status = load_task_status()

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

def find_enumber_by_code(code):
    normalized_code = sanitize_code(code)
    for entry in enumbers:
        if sanitize_code(entry.get('code', '')) == normalized_code:
            return entry
    return None

# --- Background Task Logic ---

def run_deep_scan():
    global enumbers, task_status
    task_status["is_running"] = True
    task_status["total"] = len(enumbers)
    task_status["current"] = 0
    save_task_status()
    
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
    save_task_status()
    print(f"Deep Scan Complete. Updated {updated_count} entries.")

# --- Routes ---

@app.route('/api/update_status', methods=['GET'])
def get_status():
    status = dict(task_status)
    job = scheduler.get_job('off-additives-sync')
    status['next_off_sync_due'] = job.next_run_time.isoformat() if job and job.next_run_time else None
    return jsonify(status)

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

@app.route('/api/admin/enumbers', methods=['GET'])
@check_editing_allowed
def admin_get_enumbers():
    query = sanitize_string(request.args.get('q', ''), 100).lower()
    limit = request.args.get('limit', type=int, default=1000)
    limit = min(max(1, limit), 5000)

    if query:
        results = [
            e for e in enumbers
            if query in (e.get('code', '').lower()) or query in (e.get('name', '').lower())
        ]
    else:
        results = enumbers

    return jsonify(results[:limit])

@app.route('/api/admin/enumbers/<code>/removed', methods=['PUT'])
@check_editing_allowed
def admin_set_removed(code):
    entry = find_enumber_by_code(code)
    if not entry:
        return jsonify({'error': 'E-number not found'}), 404

    data = request.get_json()
    if not isinstance(data, dict):
        return jsonify({'error': 'Invalid JSON payload'}), 400

    if 'removed' not in data or not isinstance(data.get('removed'), bool):
        return jsonify({'error': '"removed" must be a boolean'}), 400

    removed = data.get('removed')
    reason = sanitize_string(data.get('reason', ''), 500)
    timestamp = datetime.now().isoformat()

    if removed:
        entry['removed'] = True
        if reason:
            entry['removed_reason'] = reason
        else:
            entry.pop('removed_reason', None)
        entry['removed_last_checked'] = timestamp
        entry['removed_source'] = 'admin'
    else:
        entry.pop('removed', None)
        entry.pop('removed_reason', None)
        entry.pop('removed_last_checked', None)
        entry.pop('removed_source', None)

    save_enumbers(enumbers)
    return jsonify({
        'message': 'Removed status updated',
        'code': entry.get('code'),
        'removed': bool(entry.get('removed'))
    })

def _extract_ecodes_from_off_tag(add):
    """Extract E-code(s) from OFF tag. Uses 'id' (canonical e.g. en:e472a-...) and 'name'."""
    codes = set()
    tag_id = add.get('id', '')

    # 1. Tag id: try to extract canonical numeric portion (handles e1414, e14xx, e472a, e160bii)
    m = re.search(r'e(\d+)([a-z]{0,4})?(?:-|$)', tag_id, re.I)
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

    # 2. Parse the human-readable name for explicit codes like "E472a", "E 472a", "E160bii"
    raw_name = add.get('name', '') or ''
    for m in re.finditer(r'E\s*(\d{1,4})([A-Za-z]{0,4})', raw_name, re.I):
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

def _find_record_value(record, names):
    normalized = {re.sub(r'[^a-z0-9]', '', key.lower()): value
                  for key, value in record.items()}
    for name in names:
        value = normalized.get(re.sub(r'[^a-z0-9]', '', name.lower()))
        if isinstance(value, (str, int, float)) and str(value).strip():
            return str(value).strip()
    return ''

def _eu_records_from_payload(payload):
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []

    for key in ('value', 'data', 'results', 'items', 'additives', 'records'):
        records = payload.get(key)
        if isinstance(records, list):
            return records

    # Some exports use the E-number as the object key.
    records = []
    for key, value in payload.items():
        if isinstance(value, dict):
            record = dict(value)
            record.setdefault('code', key)
            records.append(record)
    return records

def _normalize_eu_additives(response):
    try:
        payload = response.json()
        records = _eu_records_from_payload(payload)
    except ValueError:
        reader = csv.DictReader(io.StringIO(response.text))
        records = list(reader)

    additives = []
    for record in records:
        if not isinstance(record, dict):
            continue
        code = _find_record_value(record, (
            'e_number', 'enumber', 'e_code', 'additive_code', 'additive_e_code',
            'code', 'number'
        ))
        if not re.search(r'\bE\s*\d{1,4}[A-Za-z]{0,4}\b', code, re.I):
            for value in record.values():
                if isinstance(value, str):
                    match = re.search(r'\bE\s*\d{1,4}[A-Za-z]{0,4}\b', value, re.I)
                    if match:
                        code = match.group(0)
                        break
        name = _find_record_value(record, (
            'name', 'additive_name', 'substance_name', 'denomination'
        ))
        if not code or not name:
            continue
        additives.append({
            'id': code.replace(' ', '').lower(),
            'name': name,
            'eu_source': 'https://developer.datalake.sante.service.ec.europa.eu/api-details#api=294321de-6daf-480b-9c7a-b7b19eeff462'
        })
    return additives

def _fetch_eu_additives():
    url = "https://api.datalake.sante.service.ec.europa.eu/food-additives/food-additives-list"
    headers = {
        'User-Agent': USER_AGENT,
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }
    all_additives = []
    try:
        next_url = url
        params = {'api-version': 'v2.0', 'format': 'json'}
        for _ in range(100):
            response = requests.get(next_url, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            all_additives.extend(_normalize_eu_additives(response))
            payload = response.json()
            next_url = payload.get('nextLink') if isinstance(payload, dict) else None
            if not next_url:
                break
            params = None

        if all_additives:
            print(f"Loaded {len(all_additives)} additives from the EU Food Additives API.")
            return all_additives, "eu-food-additives"
        print("EU Food Additives API returned no usable additives.")
    except Exception as e:
        print(f"EU Food Additives fetch failed: {e}")
    return [], "none"

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
            return tags, "primary"
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
        return additives, "fallback"
    except Exception as e:
        print(f"Fallback OFF fetch failed: {e}")
        return [], "none"

def update_enumbers_from_off_additives_logic():
    global enumbers, task_status
    print("Fetching master additive list from the EU Food Additives API...")
    task_status["last_off_sync_started"] = datetime.now().isoformat()
    task_status["last_off_sync_error"] = None
    save_task_status()
    additives, sync_source = _fetch_eu_additives()
    if not additives:
        print("Falling back to Open Food Facts additives...")
        additives, sync_source = _fetch_off_additives()
    task_status["last_off_sync_source"] = sync_source
    if not additives:
        error_message = "Error fetching EU Food Additives and Open Food Facts sources."
        task_status["last_off_sync_completed"] = datetime.now().isoformat()
        task_status["last_off_sync_success"] = False
        task_status["last_off_sync_updated_count"] = 0
        task_status["last_off_sync_error"] = error_message
        task_status["last_completed"] = task_status["last_off_sync_completed"]
        save_task_status()
        print(error_message)
        return 0

    # 1. Build a map of E-codes from the selected source.
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
        add = None
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

        if matched and add:
            if sync_source == 'eu-food-additives':
                entry['eu_additive'] = {
                    'name': add.get('name'),
                    'source': add.get('eu_source')
                }
                # EU authorization is authoritative; clear stale source-based flags.
                if entry.get('removed_source') != 'admin':
                    entry.pop('removed', None)
                    entry.pop('removed_reason', None)
                    entry.pop('removed_last_checked', None)
                    entry.pop('removed_source', None)
            else:
                entry['openfoodfacts_additive'] = {
                    'name': add.get('name'),
                    'url': add.get('url'),
                    'sameAs': add.get('sameAs', [])
                }
            updated += 1

    if sync_source == 'eu-food-additives':
        # EU data is authoritative; old source-based removal flags are stale.
        for entry in enumbers:
            if entry.get('removed_source') != 'admin':
                entry.pop('removed', None)
                entry.pop('removed_reason', None)
                entry.pop('removed_last_checked', None)
                entry.pop('removed_source', None)

    save_enumbers(enumbers)
    task_status["last_off_sync_completed"] = datetime.now().isoformat()
    task_status["last_off_sync_success"] = True
    task_status["last_off_sync_updated_count"] = updated
    task_status["last_off_sync_error"] = None
    task_status["last_completed"] = task_status["last_off_sync_completed"]
    save_task_status()
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

@app.route('/admin.html')
def admin_dashboard():
    return send_from_directory('.', 'admin.html')

# --- Startup ---

enumbers = load_enumbers()
scheduler = BackgroundScheduler()
scheduler.add_job(update_enumbers_from_off_additives_logic, 'interval', days=1, id='off-additives-sync')
scheduler.start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
