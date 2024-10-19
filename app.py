from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from flask_session import Session
import os
import json
from datetime import datetime
from urllib.parse import urlparse

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key')
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

from utils import (
    get_area, rpc_call, validate_geo_json, validate_general,
    AREA_TYPES, AREA_TYPE_REQUIREMENTS, validation_functions,
    search_areas
)

@app.route('/')
def home():
    return redirect(url_for('select_area'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Add login logic here
        return redirect(url_for('home'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

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
            'value': geo_json
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
        if key == 'area_km2':
            try:
                value = float(value)
            except ValueError:
                return jsonify({'error': f'{key}: Invalid numeric value'}), 400
        elif key == 'population':
            try:
                value = int(value)
            except ValueError:
                return jsonify({'error': f'{key}: Invalid integer value'}), 400

        result = rpc_call('set_area_tag', {
            'id': area_id,
            'name': key,
            'value': value
        })
        return jsonify(result)

@app.route('/add_area', methods=['GET', 'POST'])
def add_area():
    if request.method == 'POST':
        app.logger.info(f"Received POST request to add_area. Request data: {request.data}")
        try:
            tags = request.json
            app.logger.info(f"Parsed JSON data: {tags}")
        except Exception as e:
            app.logger.error(f"Error parsing JSON data: {str(e)}")
            return jsonify({'error': {'message': 'Invalid JSON data'}}), 400

        if not tags:
            app.logger.error("Invalid request data: tags are empty")
            return jsonify({'error': {'message': 'Invalid request data: tags are empty'}}), 400

        app.logger.info(f"Tags object: {tags}")
        area_type = tags.get('type')
        app.logger.info(f"Extracted area type: {area_type}")

        if not area_type:
            app.logger.error("Missing area type")
            return jsonify({'error': {'message': 'Missing area type'}}), 400
        if area_type not in AREA_TYPES:
            app.logger.error(f"Invalid area type: {area_type}")
            return jsonify({'error': {'message': f'Invalid area type: {area_type}'}}), 400

        validation_errors = []

        for key, requirements in AREA_TYPE_REQUIREMENTS.get(area_type, {}).items():
            if requirements['required'] and key not in tags:
                validation_errors.append(f'Missing required field: {key}')
            elif key in tags:
                value = tags[key]
                validation_funcs = validation_functions.get(requirements['type'], [validate_general])
                for validation_func in validation_funcs:
                    is_valid, error_message = validation_func(value, requirements.get('allowed_values'))
                    if not is_valid:
                        validation_errors.append(f'{key}: {error_message}')

        if validation_errors:
            app.logger.error(f"Validation errors: {validation_errors}")
            return jsonify({'error': {'message': '; '.join(validation_errors)}}), 400

        if 'geo_json' in tags:
            is_valid, result = validate_geo_json(tags['geo_json'])
            if not is_valid:
                return jsonify({'error': {'message': result}}), 400
            tags['geo_json'] = result['geo_json']
            tags['area_km2'] = result['area_km2']

        if 'area_km2' in tags:
            try:
                tags['area_km2'] = float(tags['area_km2'])
            except ValueError:
                return jsonify({'error': {'message': 'Invalid area_km2 value'}}), 400
        if 'population' in tags:
            try:
                tags['population'] = int(tags['population'])
            except ValueError:
                return jsonify({'error': {'message': 'Invalid population value'}}), 400

        result = rpc_call('add_area', {'tags': tags})

        if 'error' not in result:
            return jsonify({'success': True})
        app.logger.error(f"Error from RPC call: {result['error']}")
        return jsonify({'error': result['error']}), 400

    return render_template('add_area.html', area_type_requirements=AREA_TYPE_REQUIREMENTS)

@app.route('/select_area')
def select_area():
    return render_template('select_area.html')

@app.route('/api/search_areas', methods=['POST'])
def search_areas_api():
    data = request.json
    if not data or 'query' not in data:
        return jsonify({'error': 'Invalid request data'}), 400

    query = data['query']
    app.logger.info(f"Searching for areas with query: {query}")

    results = search_areas(query)
    return jsonify(results)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
