import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_session import Session
import requests
import json
from datetime import datetime, timedelta
from collections import Counter
from geojson_rewind import rewind
from urllib.parse import urlparse
import re
from shapely.geometry import shape, mapping
from shapely.ops import transform
import pyproj

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)
Session(app)

API_BASE_URL = "https://api.btcmap.org"

CONTINENTS = [
    'africa', 'asia', 'europe', 'north-america', 'oceania', 'south-america'
]
AREA_TYPES = ['community', 'country']

AREA_TYPE_REQUIREMENTS = {
    'community': {
        'name': {
            'required': True,
            'type': 'text'
        },
        'url_alias': {
            'required': True,
            'type': 'text'
        },
        'continent': {
            'required': True,
            'type': 'select',
            'allowed_values': CONTINENTS
        },
        'icon:square': {
            'required': True,
            'type': 'text'
        },
        'population': {
            'required': True,
            'type': 'number'
        },
        'population:date': {
            'required': True,
            'type': 'date'
        },
        'area_km2': {
            'required': False,
            'type': 'number'
        },
        'organization': {
            'required': False,
            'type': 'text'
        },
        'language': {
            'required': False,
            'type': 'text'
        },
        'contact:twitter': {
            'required': False,
            'type': 'url'
        },
        'contact:website': {
            'required': False,
            'type': 'url'
        },
        'contact:email': {
            'required': False,
            'type': 'email'
        },
        'contact:telegram': {
            'required': False,
            'type': 'url'
        },
        'contact:signal': {
            'required': False,
            'type': 'url'
        },
        'contact:whatsapp': {
            'required': False,
            'type': 'url'
        },
        'contact:nostr': {
            'required': False,
            'type': 'text'
        },
        'contact:meetup': {
            'required': False,
            'type': 'url'
        },
        'contact:discord': {
            'required': False,
            'type': 'url'
        },
        'contact:instagram': {
            'required': False,
            'type': 'url'
        },
        'contact:youtube': {
            'required': False,
            'type': 'url'
        },
        'contact:facebook': {
            'required': False,
            'type': 'url'
        },
        'contact:linkedin': {
            'required': False,
            'type': 'url'
        },
        'contact:rss': {
            'required': False,
            'type': 'url'
        },
        'contact:phone': {
            'required': False,
            'type': 'tel'
        },
        'contact:github': {
            'required': False,
            'type': 'url'
        },
        'contact:matrix': {
            'required': False,
            'type': 'url'
        },
        'tips:lightning_address': {
            'required': False,
            'type': 'text'
        },
        'tips:url': {
            'required': False,
            'type': 'url'
        },
        'description': {
            'required': False,
            'type': 'text'
        }
    }
}

@app.before_request
def check_auth():
    if request.endpoint and request.endpoint not in [
            'login', 'static'
    ] and 'password' not in session:
        return redirect(url_for('login', next=request.url))

@app.route('/')
def home():
    return redirect(url_for('select_area'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'password' in session:
        return redirect(url_for('select_area'))
    if request.method == 'POST':
        password = request.form.get('password')
        session['password'] = password
        session.permanent = True
        next_page = request.args.get('next')
        return redirect(next_page or url_for('select_area'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('password', None)
    return redirect(url_for('login'))

@app.route('/select_area')
def select_area():
    return render_template('select_area.html')

@app.route('/show_area/<string:area_id>')
def show_area(area_id):
    area = get_area(area_id)
    if area:
        area['created_at'] = format_date(area.get('created_at'))
        area['updated_at'] = format_date(area.get('updated_at'))
        area['last_sync'] = format_date(area.get('last_sync'))

        area_type = area['tags'].get('type', '')
        type_requirements = AREA_TYPE_REQUIREMENTS.get(area_type, {})

        geo_json = area['tags'].get('geo_json')
        if geo_json and isinstance(geo_json, str):
            try:
                geo_json = json.loads(geo_json)
            except json.JSONDecodeError:
                app.logger.error(f"Invalid JSON string for geo_json in area {area_id}")
                geo_json = None

        return render_template('show_area.html',
                               area=area,
                               area_type_requirements=type_requirements,
                               geo_json=geo_json)
    return render_template('error.html', error="Area not found"), 404

@app.route('/add_area', methods=['GET', 'POST'])
def add_area():
    if request.method == 'POST':
        app.logger.info(
            f"Received POST request to add_area. Request data: {request.data}")
        try:
            tags = request.json
            app.logger.info(f"Parsed JSON data: {tags}")
        except Exception as e:
            app.logger.error(f"Error parsing JSON data: {str(e)}")
            return jsonify({'error': {'message': 'Invalid JSON data'}}), 400

        if not tags:
            app.logger.error("Invalid request data: tags are empty")
            return jsonify(
                {'error': {
                    'message': 'Invalid request data: tags are empty'
                }}), 400

        app.logger.info(f"Tags object: {tags}")
        area_type = tags.get('type')
        app.logger.info(f"Extracted area type: {area_type}")

        if not area_type:
            app.logger.error("Missing area type")
            return jsonify({'error': {'message': 'Missing area type'}}), 400
        if area_type not in AREA_TYPES:
            app.logger.error(f"Invalid area type: {area_type}")
            return jsonify(
                {'error': {
                    'message': f'Invalid area type: {area_type}'
                }}), 400

        validation_errors = []

        for key, requirements in AREA_TYPE_REQUIREMENTS.get(area_type,
                                                            {}).items():
            if requirements['required'] and key not in tags:
                validation_errors.append(f'Missing required field: {key}')
            elif key in tags:
                value = tags[key]
                validation_funcs = validation_functions.get(
                    requirements['type'], [validate_general])
                for validation_func in validation_funcs:
                    is_valid, error_message = validation_func(
                        value, requirements.get('allowed_values'))
                    if not is_valid:
                        validation_errors.append(f'{key}: {error_message}')

        if validation_errors:
            app.logger.error(f"Validation errors: {validation_errors}")
            return jsonify(
                {'error': {
                    'message': '; '.join(validation_errors)
                }}), 400

        if 'geo_json' in tags:
            is_valid, result = validate_geo_json(tags['geo_json'])
            if not is_valid:
                return jsonify({'error': {'message': result}}), 400
            tags['geo_json'] = result['geo_json']
            tags['area_km2'] = result['area_km2']

        result = rpc_call('add_area', {'tags': tags})

        if 'error' not in result:
            return jsonify({'success': True})
        app.logger.error(f"Error from RPC call: {result['error']}")
        return jsonify({'error': result['error']}), 400

    return render_template('add_area.html',
                           area_type_requirements=AREA_TYPE_REQUIREMENTS)

@app.route('/api/set_area_tag', methods=['POST'])
def set_area_tag():
    data = request.json
    print(data)

    if not data:
        return jsonify({'error': 'Invalid request data'}), 400

    area_id = data.get('id')
    key = data.get('name')
    value = data.get('value')

    area = get_area(area_id)
    if not area:
        return jsonify({'error': 'Area not found'}), 404

    area_type = area['tags'].get('type')
    if not area_type or area_type not in AREA_TYPES:
        return jsonify({'error': 'Invalid area type'}), 400

    requirements = AREA_TYPE_REQUIREMENTS.get(area_type, {}).get(key, {})

    validation_funcs = validation_functions.get(requirements.get('type', 'text'), [validate_general])
    for validation_func in validation_funcs:
        is_valid, error_message = validation_func(value, requirements.get('allowed_values'))
        if not is_valid:
            return jsonify({'error': f'{key}: {error_message}'}), 400

    if key == 'geo_json':
        is_valid, result = validate_geo_json(value)
        if not is_valid:
            return jsonify({'error': result}), 400

        result = rpc_call('set_area_tag', {
            'id': area_id,
            'name': 'geo_json',
            'value': value
        })

        if 'error' in result:
            return jsonify({'error': f'Failed to update geo_json: {result["error"]}'}), 400

        area_km2 = calculate_area(value)
        area_result = rpc_call('set_area_tag', {
            'id': area_id,
            'name': 'area_km2',
            'value': area_km2
        })

        if 'error' in area_result:
            return jsonify({'error': f'Failed to update area: {area_result["error"]}'}), 400

        return jsonify({'success': True, 'message': 'GeoJSON and area updated successfully'})

        return jsonify(result)

@app.route('/api/remove_area_tag', methods=['POST'])
def remove_area_tag():
    data = request.json
    if not data:
        return jsonify({'error': 'Invalid request data'}), 400

    area_id = data.get('id')
    tag = data.get('tag')

    area = get_area(area_id)
    if not area:
        return jsonify({'error': 'Area not found'}), 404

    area_type = area['tags'].get('type')
    if not area_type or area_type not in AREA_TYPES:
        return jsonify({'error': 'Invalid area type'}), 400

    if AREA_TYPE_REQUIREMENTS.get(area_type,
                                  {}).get(tag, {}).get('required', False):
        return jsonify({'error': f'Cannot remove required tag: {tag}'}), 400

    result = rpc_call('remove_area_tag', {'id': area_id, 'tag': tag})
    return jsonify(result)

@app.route('/api/remove_area', methods=['POST'])
def remove_area():
    data = request.json
    if not data:
        return jsonify({'error': 'Invalid request data'}), 400
    result = rpc_call('remove_area', {'id': data.get('id')})
    return jsonify(result)

@app.route('/api/search_areas', methods=['POST'])
def search_areas():
    try:
        data = request.get_json()
        query = data.get('query', '').lower()

        result = rpc_call('search', {'query': query})

        if 'error' in result:
            app.logger.error(f"Error in RPC call: {result['error']}")
            return jsonify({'error': result['error']}), 400

        areas = result.get('result', [])
        filtered_areas = [{
            'id': area['id'],
            'name': area['name'],
            'type': area['type']
        } for area in areas if area['type'] == 'area']
        return jsonify(filtered_areas)
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Network error in search_areas: {str(e)}")
        return jsonify({'error':
                        "Network error. Please try again later."}), 500
    except Exception as e:
        app.logger.error(f"Error in search_areas: {str(e)}")
        return jsonify({
            'error':
            f"An unexpected error occurred. Please try again later."
        }), 500

def get_area(area_id):
    result = rpc_call('get_area', {'id': area_id})
    if 'error' not in result:
        return result['result']
    return None

def calculate_area(geo_json):
    if isinstance(geo_json, str):
        geo_json = json.loads(geo_json)

    geom = shape(geo_json)

    proj = pyproj.Proj(proj='aea', lat_1=geom.bounds[1], lat_2=geom.bounds[3])

    project = lambda x, y: proj(x, y)

    geom_proj = transform(project, geom)

    area_m2 = geom_proj.area

    return round(area_m2 / 1_000_000, 2)

def rpc_call(method, params):
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": {
            "password": session.get('password'),
            **params
        },
        "id": 1
    }
    try:
        response = requests.post(f"{API_BASE_URL}/rpc",
                                 json=payload,
                                 timeout=20)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        app.logger.error(f"Timeout error in RPC call to {method}")
        raise requests.exceptions.RequestException("Request timed out")
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Network error in RPC call to {method}: {str(e)}")
        raise
    except Exception as e:
        app.logger.error(f"Unexpected error in RPC call to {method}: {str(e)}")
        raise

def format_date(date_string):
    if date_string:
        try:
            date = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
            return date.strftime('%Y-%m-%d %H:%M:%S UTC')
        except ValueError:
            return date_string
    return 'N/A'

def validate_non_negative_number(value, allowed_values=None):
    if not isinstance(value, (int, float)) and not (isinstance(
            value, str) and value.replace('.', '', 1).isdigit()):
        return False, "Value must be a non-negative number"
    try:
        num = float(value)
        return num >= 0, "Value must be a non-negative number"
    except ValueError:
        return False, "Value must be a number"

def validate_non_negative_integer(value, allowed_values=None):
    if not isinstance(value, int) and not (isinstance(value, str)
                                           and value.isdigit()):
        return False, "Value must be a non-negative integer"
    try:
        num = int(value)
        return num >= 0, "Value must be a non-negative integer"
    except ValueError:
        return False, "Value must be an integer"

def validate_date(value, allowed_values=None):
    try:
        datetime.strptime(value, '%Y-%m-%d')
        return True, None
    except ValueError:
        return False, "Invalid date format. Please use YYYY-MM-DD"

def validate_allowed_values(value, allowed_values):
    if allowed_values and value.lower() in allowed_values:
        return True, None
    else:
        return False, f"Invalid value. Please choose from {', '.join(allowed_values)}"

def validate_geo_json(value):
    try:
        if isinstance(value, str):
            geo_json = json.loads(value)
        elif isinstance(value, dict):
            geo_json = value
        else:
            return False, "Invalid GeoJSON: must be a JSON object or a valid JSON string"

        if not isinstance(geo_json, dict):
            return False, "Invalid GeoJSON: must be a JSON object"

        try:
            geom = shape(geo_json)
            if geom.geom_type not in ['Polygon', 'MultiPolygon']:
                return False, "Invalid GeoJSON: only valid Polygon and MultiPolygon types are accepted"
            # Calculate area after validation
            area_km2 = calculate_area(geo_json)
            rewound = rewind(geo_json)

            return True, {
                "geo_json": json.dumps(rewound),
                "area_km2": area_km2
            }
        except Exception as e:
            return False, f"Invalid GeoJSON structure: {str(e)}"
    except json.JSONDecodeError:
        return False, "Invalid JSON format"
    except Exception as e:
        return False, f"Error validating GeoJSON: {str(e)}"

def validate_general(value, allowed_values=None):
    if allowed_values:
        return validate_allowed_values(value, allowed_values)
    return len(str(value).strip()) > 0, "Value cannot be empty"

def validate_url(value, allowed_values=None):
    try:
        result = urlparse(value)
        return all([result.scheme, result.netloc]), "Invalid URL format"
    except:
        return False, "Invalid URL"

def validate_email(value, allowed_values=None):
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(email_regex, value)), "Invalid email format"

def validate_phone(value, allowed_values=None):
    phone_regex = r'^\+?1?\d{9,15}$'
    return bool(re.match(phone_regex, value)), "Invalid phone number format"

validation_functions = {
    'number': [validate_non_negative_number],
    'integer': [validate_non_negative_integer],
    'date': [validate_date],
    'select': [validate_allowed_values],
    'geo_json': [validate_geo_json],
    'text': [validate_general],
    'url': [validate_url],
    'email': [validate_email],
    'tel': [validate_phone]
}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)