
from datetime import datetime
import requests
import constants
import json
import re
from urllib.parse import urlparse
import requests
from flask import session
from shapely.geometry import shape, mapping
from shapely.ops import transform
import pyproj
from geojson_rewind import rewind

def format_date(date_string):
    if date_string:
        try:
            date = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
            return date.strftime('%Y-%m-%d %H:%M:%S UTC')
        except ValueError:
            return date_string
    return 'N/A'

def validate_non_negative_number(value, allowed_values=None):
    if not isinstance(value, (int, float)) and not (isinstance(value, str) and value.replace('.', '', 1).isdigit()):
        return False, "Value must be a non-negative number"
    try:
        num = float(value)
        return num >= 0, "Value must be a non-negative number"
    except ValueError:
        return False, "Value must be a number"

def validate_non_negative_integer(value, allowed_values=None):
    if not isinstance(value, int) and not (isinstance(value, str) and value.isdigit()):
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
    return False, f"Invalid value. Please choose from {', '.join(allowed_values)}"

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

            rewound = rewind(geo_json)
            return True, {"geo_json": rewound}
        except Exception as e:
            return False, f"Invalid GeoJSON structure: {str(e)}"
    except json.JSONDecodeError:
        return False, "Invalid JSON format"
    except Exception as e:
        return False, f"Error validating GeoJSON: {str(e)}"

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
    headers = {'Authorization': f'Bearer {session.get("password")}'}
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1
    }
    try:
        response = requests.post(f"{constants.API_BASE_URL}/rpc",
                               json=payload,
                               headers=headers,
                               timeout=20)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        raise requests.exceptions.RequestException("Request timed out")
    except requests.exceptions.RequestException as e:
        raise
    except Exception as e:
        raise

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
