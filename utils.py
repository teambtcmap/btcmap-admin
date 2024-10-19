import json
from shapely.geometry import shape
import geojson_rewind

def get_area(area_id):
    # Placeholder function, replace with actual implementation
    return {'id': area_id, 'tags': {'type': 'country'}}

def rpc_call(method, params):
    # Placeholder function, replace with actual implementation
    return {'success': True}

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
    # Use RPC call to search for areas
    result = rpc_call('search_areas', {'query': query})
    if 'error' in result:
        raise Exception(f"Error searching areas: {result['error']}")
    return result.get('areas', [])

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
