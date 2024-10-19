import json
from shapely.geometry import shape
import geojson_rewind
import logging
from datetime import datetime

def get_area(area_id):
    # More realistic placeholder function
    return {
        'id': area_id,
        'tags': {
            'type': 'country',
            'name': 'Example Country',
            'population': 1000000,
            'area_km2': 100000.5
        },
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat(),
        'last_sync': datetime.now().isoformat()
    }

def rpc_call(method, params):
    # More realistic placeholder function
    if method == 'add_area':
        return {'success': True, 'id': '12345'}
    elif method == 'set_area_tag':
        return {'success': True}
    elif method == 'search_areas':
        return {
            'areas': [
                {
                    'id': '12345',
                    'name': 'Example Area',
                    'type': 'city',
                    'population': 500000,
                    'area_km2': 500.75
                }
            ]
        }
    else:
        return {'error': 'Unknown method'}

def validate_geo_json(geo_json_str):
    try:
        geo_json = json.loads(geo_json_str)
        if geo_json['type'] not in ['Polygon', 'MultiPolygon']:
            return False, 'GeoJSON must be a Polygon or MultiPolygon'
        
        # Rewind to ensure correct orientation
        geo_json = geojson_rewind.rewind(geo_json)
        
        # Calculate area
        area_km2 = shape(geo_json).area / 1_000_000  # Convert m^2 to km^2
        
        return True, {'geo_json': geo_json, 'area_km2': area_km2}
    except Exception as e:
        return False, str(e)

def validate_general(value, allowed_values=None):
    if allowed_values and value not in allowed_values:
        return False, f'Value must be one of: {", ".join(allowed_values)}'
    return True, None

def search_areas(query):
    logging.info(f"Searching for areas with query: {query}")
    try:
        result = rpc_call('search_areas', {'query': query})
        if 'error' in result:
            logging.error(f"Error in RPC call: {result['error']}")
            raise Exception(f"Error searching areas: {result['error']}")
        areas = result.get('areas', [])
        logging.info(f"Found {len(areas)} areas")
        return areas
    except Exception as e:
        logging.exception(f"Unexpected error in search_areas: {str(e)}")
        raise

AREA_TYPES = ['country', 'state', 'city', 'neighborhood']

AREA_TYPE_REQUIREMENTS = {
    'country': {
        'name': {'type': 'text', 'required': True},
        'population': {'type': 'integer', 'required': False},
        'area_km2': {'type': 'number', 'required': False},
        'capital': {'type': 'text', 'required': False},
    },
    'state': {
        'name': {'type': 'text', 'required': True},
        'country': {'type': 'text', 'required': True},
        'population': {'type': 'integer', 'required': False},
        'area_km2': {'type': 'number', 'required': False},
    },
    'city': {
        'name': {'type': 'text', 'required': True},
        'state': {'type': 'text', 'required': True},
        'country': {'type': 'text', 'required': True},
        'population': {'type': 'integer', 'required': False},
        'area_km2': {'type': 'number', 'required': False},
    },
    'neighborhood': {
        'name': {'type': 'text', 'required': True},
        'city': {'type': 'text', 'required': True},
        'state': {'type': 'text', 'required': True},
        'country': {'type': 'text', 'required': True},
        'population': {'type': 'integer', 'required': False},
        'area_km2': {'type': 'number', 'required': False},
    },
}

validation_functions = {
    'text': [validate_general],
    'integer': [lambda v, _: (isinstance(v, int) or (isinstance(v, str) and v.isdigit()), 'Must be an integer')],
    'number': [lambda v, _: (isinstance(v, (int, float)) or (isinstance(v, str) and v.replace('.', '', 1).isdigit()), 'Must be a number')],
}
