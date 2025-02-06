import os
import requests
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_session import Session
import json
from datetime import timedelta
import constants
from helper import (format_date, validate_geo_json, calculate_area, rpc_call,
                    validation_functions)

FLASK_CONFIG = {
    'SECRET_KEY': os.urandom(24),
    'SESSION_TYPE': 'filesystem',
    'SESSION_PERMANENT': True,
    'PERMANENT_SESSION_LIFETIME': timedelta(minutes=30)
}

app = Flask(__name__)
app.config.update(FLASK_CONFIG)
Session(app)


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
        type_requirements = constants.AREA_TYPE_REQUIREMENTS.get(area_type, {})

        geo_json = area['tags'].get('geo_json')
        if geo_json and isinstance(geo_json, str):
            try:
                geo_json = json.loads(geo_json)
            except json.JSONDecodeError:
                app.logger.error(
                    f"Invalid JSON string for geo_json in area {area_id}")
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
            app.logger.info(f"GeoJSON data type: {type(tags.get('geo_json'))}")
            app.logger.info(f"GeoJSON content: {tags.get('geo_json')}")
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
        if area_type not in constants.AREA_TYPES:
            app.logger.error(f"Invalid area type: {area_type}")
            return jsonify(
                {'error': {
                    'message': f'Invalid area type: {area_type}'
                }}), 400

        validation_errors = []

        for key, requirements in constants.AREA_TYPE_REQUIREMENTS.get(
                area_type, {}).items():
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
            app.logger.info("Validating GeoJSON...")
            is_valid, result = validate_geo_json(tags['geo_json'])
            if not is_valid:
                app.logger.error(f"GeoJSON validation failed: {result}")
                return jsonify({'error': {'message': result}}), 400
            app.logger.info(f"Valid GeoJSON result: {result}")
            tags['geo_json'] = result['geo_json']

            area_km2 = calculate_area(tags['geo_json'])
            tags['area_km2'] = area_km2

        app.logger.info(f"Sending to RPC: {tags}")
        result = rpc_call('add_area', {'tags': tags})
        app.logger.info(f"RPC response: {result}")

        if 'error' not in result:
            return jsonify({'success': True})
        app.logger.error(f"Error from RPC call: {result['error']}")
        return jsonify({'error': result['error']}), 400

    return render_template(
        'add_area.html',
        area_type_requirements=constants.AREA_TYPE_REQUIREMENTS)


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
    if not area_type or area_type not in constants.AREA_TYPES:
        return jsonify({'error': 'Invalid area type'}), 400

    requirements = constants.AREA_TYPE_REQUIREMENTS.get(area_type,
                                                        {}).get(key, {})

    validation_funcs = validation_functions.get(
        requirements.get('type', 'text'), [validate_general])
    for validation_func in validation_funcs:
        is_valid, error_message = validation_func(
            value, requirements.get('allowed_values'))
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
            return jsonify(
                {'error':
                 f'Failed to update geo_json: {result["error"]}'}), 400

        area_km2 = calculate_area(value)
        area_result = rpc_call('set_area_tag', {
            'id': area_id,
            'name': 'area_km2',
            'value': area_km2
        })

        if 'error' in area_result:
            return jsonify(
                {'error':
                 f'Failed to update area: {area_result["error"]}'}), 400

        return jsonify({
            'success': True,
            'message': 'GeoJSON and area updated successfully'
        })

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
    if not area_type or area_type not in constants.AREA_TYPES:
        return jsonify({'error': 'Invalid area type'}), 400

    if constants.AREA_TYPE_REQUIREMENTS.get(area_type,
                                            {}).get(tag,
                                                    {}).get('required', False):
        return jsonify({'error': f'Cannot remove required tag: {tag}'}), 400

    result = rpc_call('remove_area_tag', {'id': area_id, 'tag': tag})
    return jsonify(result)



@app.route('/api/set_area_icon', methods=['POST'])
def set_area_icon():
    data = request.json
    if not data:
        return jsonify({'error': 'Invalid request data'}), 400
        
    area_id = data.get('id')
    icon_base64 = data.get('icon_base64')
    icon_ext = data.get('icon_ext', 'png')
    
    if not all([area_id, icon_base64, icon_ext]):
        return jsonify({'error': 'Missing required fields'}), 400
        
    # Validate and process image
    is_valid, error_message = validate_image(icon_base64)
    if not is_valid:
        return jsonify({'error': error_message}), 400
        
    processed_image = process_image(icon_base64)
    
    # Call RPC to set the icon
    result = rpc_call('set_area_icon', {
        'id': area_id,
        'icon_base64': processed_image,
        'icon_ext': icon_ext
    })
    
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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
