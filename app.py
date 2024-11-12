import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
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
import secrets

app = Flask(__name__)
# Use a strong secret key
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(32))
# Configure server-side session
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = 'flask_session'
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
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
    # If user is already logged in, redirect to select_area
    if 'password' in session:
        return redirect(url_for('select_area'))
    
    if request.method == 'POST':
        password = request.form.get('password')
        if not password:
            flash('Password is required', 'error')
            return render_template('login.html'), 400
        
        # Verify password by making a test RPC call
        try:
            test_response = requests.post(
                f"{API_BASE_URL}/rpc",
                json={
                    "jsonrpc": "2.0",
                    "method": "search",
                    "params": {"password": password, "query": ""},
                    "id": 1
                },
                timeout=10
            )
            
            if test_response.status_code == 200 and 'error' not in test_response.json():
                # Set session
                session.clear()
                session['password'] = password
                session.permanent = True
                
                # Get the next URL or default to select_area
                next_page = request.args.get('next')
                # Ensure the next_page is a relative URL to prevent open redirect
                if next_page and urlparse(next_page).netloc == '':
                    return redirect(next_page)
                return redirect(url_for('select_area'))
            else:
                flash('Invalid password', 'error')
                return render_template('login.html'), 401
        except requests.exceptions.RequestException:
            flash('Error connecting to the server', 'error')
            return render_template('login.html'), 500
    
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

        # Get raw GeoJSON data
        raw_geo_json = area['tags'].get('geo_json')
        app.logger.info(f"Raw GeoJSON data for area {area_id}: {raw_geo_json}")

        geo_json = None
        if raw_geo_json:
            try:
                # Handle string GeoJSON
                if isinstance(raw_geo_json, str):
                    try:
                        geo_json = json.loads(raw_geo_json)
                        app.logger.info(f"Parsed GeoJSON from string: {geo_json}")
                    except json.JSONDecodeError as e:
                        app.logger.error(f"Invalid JSON format in string GeoJSON: {e}")
                        raise ValueError("Invalid JSON format")
                else:
                    geo_json = raw_geo_json
                    app.logger.info(f"Using raw GeoJSON object: {geo_json}")

                # Validate GeoJSON structure
                is_valid, result = validate_geo_json(geo_json)
                if is_valid:
                    geo_json = result['geo_json']
                    app.logger.info(f"Validated and processed GeoJSON: {geo_json}")
                else:
                    app.logger.error(f"Invalid GeoJSON structure: {result}")
                    geo_json = None

            except Exception as e:
                app.logger.error(f"Error processing GeoJSON for area {area_id}: {str(e)}")
                geo_json = None
        else:
            app.logger.info(f"No GeoJSON data found for area {area_id}")

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

        geo_json = result['geo_json']
        area_km2 = result['area_km2']

        result = rpc_call('set_area_tag', {
            'id': area_id,
            'name': 'geo_json',
            "value": f"'{geo_json}'"
        })

        if 'error' in result:
            return jsonify({'error': f'Failed to update geo_json: {result["error"]}'}), 400

        area_result = rpc_call('set_area_tag', {
            'id': area_id,
            'name': 'area_km2',
            'value': area_km2
        })

        if 'error' in area_result:
            return jsonify({'error': f'Failed to update area: {area_result["error"]}'}), 400

        return jsonify({'success': True, 'message': 'GeoJSON and area updated successfully'})
    else:
        result = rpc_call('set_area_tag', {
            'id': area_id,
            'name': key,
            'value': value
        })
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
                                 timeout=10)
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
        app.logger.info(f"Validating GeoJSON input: {value}")
        
        if isinstance(value, str):
            try:
                geo_json = json.loads(value)
                app.logger.info("Successfully parsed GeoJSON string")
            except json.JSONDecodeError as e:
                app.logger.error(f"Failed to parse GeoJSON string: {e}")
                return False, "Invalid GeoJSON: must be a valid JSON string"
        elif isinstance(value, dict):
            geo_json = value
            app.logger.info("Using GeoJSON object directly")
        else:
            app.logger.error(f"Invalid GeoJSON type: {type(value)}")
            return False, "Invalid GeoJSON: must be a JSON object or a valid JSON string"

        if not isinstance(geo_json, dict):
            app.logger.error("GeoJSON is not a dictionary")
            return False, "Invalid GeoJSON: must be a JSON object"

        try:
            # Validate GeoJSON structure
            if 'type' not in geo_json or 'coordinates' not in geo_json:
                app.logger.error("Missing required GeoJSON properties")
                return False, "Invalid GeoJSON: missing required properties"

            if geo_json['type'] not in ['Polygon', 'MultiPolygon']:
                app.logger.error(f"Invalid GeoJSON type: {geo_json['type']}")
                return False, "Invalid GeoJSON: type must be Polygon or MultiPolygon"

            # Validate geometry
            geom = shape(geo_json)
            if not geom.is_valid:
                app.logger.error("Invalid geometry")
                return False, "Invalid GeoJSON: geometry is not valid"

            # Calculate area
            area_km2 = calculate_area(geo_json)
            app.logger.info(f"Calculated area: {area_km2} km²")

            # Apply right-hand rule
            geo_json = rewind(geo_json)
            app.logger.info("Applied right-hand rule to GeoJSON")

            return True, {
                'geo_json': geo_json,
                'area_km2': area_km2
            }

        except Exception as e:
            app.logger.error(f"Error validating GeoJSON structure: {str(e)}")
            return False, f"Invalid GeoJSON: {str(e)}"

    except Exception as e:
        app.logger.error(f"Unexpected error in validate_geo_json: {str(e)}")
        return False, f"Error processing GeoJSON: {str(e)}"

validation_functions = {
    'number': [validate_non_negative_number],
    'integer': [validate_non_negative_integer],
    'date': [validate_date],
    'select': [validate_allowed_values]
}