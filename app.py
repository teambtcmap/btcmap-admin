import os
from flask import Flask, g, render_template, request, jsonify, redirect, url_for
import requests
import json
from datetime import datetime, timedelta
from geojson_rewind import rewind
from urllib.parse import urlparse
import re
from shapely.geometry import shape
from shapely.ops import transform
import pyproj
from linting import lint_area_dict, lint_cache, LINT_RULES, FIX_ACTIONS, fix_migrate_icon, fix_bump_verified
from rpc_errors import is_not_found, is_transport_error, rpc_error_message
from admin_session import (
    SessionExpired,
    current_user as get_current_user,
    expire_token_cookie,
    fetch_me,
    identity,
    login_required,
    sign_out,
    store_identity,
    token_from_request,
)
from auth import auth_bp

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
# Trusted API origin. Must be absolute and identical to the API's own
# BTCMAP_API_BASE_URL: a NIP-98 event signs this exact origin in its `u` tag.
app.config['API_BASE_URL'] = os.environ.get('API_BASE_URL', 'https://api.btcmap.org').rstrip('/')
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
# Flask's signed cookie session is the storage: display-only identity, no
# server-side session files and no account database.
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

# Register auth blueprint
app.register_blueprint(auth_bp)

API_BASE_URL = app.config['API_BASE_URL']


@app.context_processor
def inject_current_user():
    return {'current_user': get_current_user(), 'api_base_url': API_BASE_URL}


@app.after_request
def clear_expired_token_cookie(response):
    """Delete the navigation cookie when a request proved the token is dead."""
    if g.pop('expire_token_cookie', False):
        response.delete_cookie('btcmap_token', path='/')
    return response


@app.errorhandler(SessionExpired)
def handle_session_expired(_exc):
    """Turn a rejected API token into a login redirect or a JSON 401."""
    sign_out()
    expire_token_cookie()
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Session expired', 'session_expired': True}), 401
    return redirect(url_for('login', next=request.full_path.rstrip('?')))

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
        'contact:geyser': {
            'required': False,
            'type': 'url'
        },
        'contact:eventbrite': {
            'required': False,
            'type': 'url'
        },
        'contact:reddit': {
            'required': False,
            'type': 'url'
        },
        'contact:simplex': {
            'required': False,
            'type': 'url'
        },
        'contact:satlantis': {
            'required': False,
            'type': 'url'
        },
        'tips:lightning_address': {
            'required': False,
            'type': 'text'
        },
        'description': {
            'required': False,
            'type': 'text'
        }
    }
}


PUBLIC_ENDPOINTS = {'login', 'static', 'health', 'auth.create_session', 'auth.logout'}


@app.before_request
def check_token():
    """Everything outside the sign-in surface requires a session."""
    if request.endpoint is None or request.endpoint in PUBLIC_ENDPOINTS:
        return None

    if not identity():
        if (request.path.startswith('/api/')
                or request.is_json
                or request.headers.get('X-Requested-With') == 'XMLHttpRequest'):
            return jsonify({'error': 'Session expired', 'session_expired': True}), 401
        return redirect(url_for('login', next=request.full_path.rstrip('?')))
    return None


@app.route('/health')
def health():
    """Health check endpoint for Railway/container orchestration."""
    return jsonify({'status': 'healthy'}), 200


@app.route('/')
def index():
    if identity():
        return redirect(url_for('select_area'))
    return redirect(url_for('login'))


@app.route('/home')
@login_required
def home():
    return redirect(url_for('select_area'))


@app.route('/login', methods=['GET'])
def login():
    """Show the sign-in page. Authentication happens in the browser."""
    if identity():
        return redirect(url_for('select_area'))
    return render_template('login.html')


@app.route('/profile')
@login_required
def profile():
    """Show the account behind this session, refreshed from BTC Map API."""
    me = dict(identity() or {})
    token = token_from_request()
    if token:
        try:
            fresh = fetch_me(token)
        except (requests.exceptions.RequestException, TypeError):
            app.logger.exception('Failed to refresh identity from BTC Map API')
        else:
            if fresh is None:
                sign_out()
                expire_token_cookie()
                return redirect(url_for('login', next=url_for('profile')))
            store_identity(fresh)
            me = fresh
    return render_template('profile.html', me=me)


@app.route('/select_area')
@login_required
def select_area():
    return render_template('select_area.html')


@app.route('/show_area/<string:area_id>')
@login_required
def show_area(area_id):
    area, area_error = get_area_result(area_id)
    if not area:
        if is_not_found(area_error):
            return render_template('error.html', error="Area not found"), 404
        # A refusal (permission, geofence) is not a missing area: show the
        # API's own explanation rather than pretending the area is gone.
        return render_template(
            'error.html',
            error=area_error or 'This area cannot be loaded for your account'
        ), 403
    # Fetch from REST API to get deleted_at (RPC doesn't return it)
    is_deleted = False
    deleted_at = None
    try:
        api_response = requests.get(f"{API_BASE_URL}/v3/areas/{area_id}", timeout=10)
        if api_response.ok:
            api_data = api_response.json()
            deleted_at = api_data.get('deleted_at')
            is_deleted = bool(deleted_at)
    except requests.exceptions.RequestException:
        pass

    area['is_deleted'] = is_deleted
    area['deleted_at'] = format_date(deleted_at) if deleted_at else None
    area['created_at'] = format_date(area.get('created_at'))
    area['updated_at'] = format_date(area.get('updated_at'))
    area['last_sync'] = format_date(area.get('last_sync'))

    tags = area.get('tags', {})
    if isinstance(tags, str):
        try:
            tags = json.loads(tags)
            if not isinstance(tags, dict):
                app.logger.error(f"Tags parsed to non-dict type in area {area_id}: {type(tags)}")
                tags = {}
        except json.JSONDecodeError:
            app.logger.error(f"Invalid JSON string for tags in area {area_id}")
            tags = {}
    area_type = tags.get('type', '')
    type_requirements = AREA_TYPE_REQUIREMENTS.get(area_type, {})

    geo_json = tags.get('geo_json')
    if geo_json and isinstance(geo_json, str):
        try:
            geo_json = json.loads(geo_json)
        except json.JSONDecodeError:
            app.logger.error(
                f"Invalid JSON string for geo_json in area {area_id}")
            geo_json = None

    # Run lint checks on the area
    lint_issues = lint_area_dict(area)

    # Include cached url-alias-clash issues from global lint cache
    for cached_result in lint_cache.results:
        if cached_result['area_id'] == area_id:
            for issue in cached_result['issues']:
                if issue['rule_id'] == 'url-alias-clash':
                    lint_issues.append(issue)
            break

    # A geofenced account may read any area but the API refuses its edits, so
    # render the page without the controls that could only fail.
    user = get_current_user()
    return render_template('show_area.html',
                           area=area,
                           area_type_requirements=type_requirements,
                           geo_json=geo_json,
                           lint_issues=lint_issues,
                           read_only=not user.can_edit_area(area.get('id')))


@app.route('/add_area', methods=['GET', 'POST'])
@login_required
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
            # Return the area ID so client can upload icon
            area_result = result.get('result', {})
            if not isinstance(area_result, dict):
                app.logger.warning(f"Unexpected result format from add_area RPC: {type(area_result)}")
                return jsonify({'error': {'message': 'Invalid response from server'}}), 500
            area_id = area_result.get('id') or area_result.get('tags', {}).get('url_alias')
            return jsonify({'success': True, 'area_id': area_id})
        app.logger.error(f"Error from RPC call: {result['error']}")
        return jsonify({'error': rpc_error_text(result['error'])}), 400

    # Check for template parameter to pre-fill form
    template_area = None
    template_id = request.args.get('template')
    if template_id:
        template_area = get_area(template_id)
        if template_area:
            # Also fetch geo_json which might need parsing
            geo_json = template_area.get('tags', {}).get('geo_json')
            if geo_json and isinstance(geo_json, str):
                try:
                    template_area['tags']['geo_json'] = json.loads(geo_json)
                except json.JSONDecodeError:
                    pass
    
    return render_template('add_area.html',
                           area_type_requirements=AREA_TYPE_REQUIREMENTS,
                           template_area=template_area)


@app.route('/api/set_area_tag', methods=['POST'])
@login_required
def set_area_tag():
    data = request.json
    if not data:
        return jsonify({'error': 'Invalid request data'}), 400

    area_id = data.get('id')
    key = data.get('name')
    value = data.get('value')

    area, area_error = get_area_result(area_id)
    if not area:
        return area_lookup_error(area_error)

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

        # The API uses json_patch() which merges objects (RFC 7396).
        # To fully replace geo_json, we null out old keys to remove them.
        geo_json_with_nulls = {
            'features': None,  # Remove old FeatureCollection remnants
            'properties': None,  # Remove old Feature remnants
            'geometry': None,  # Remove old Feature remnants
            **geo_json  # Add our actual geometry (type, coordinates)
        }

        geo_result = rpc_call('set_area_tag', {'id': area_id, 'name': 'geo_json', 'value': geo_json_with_nulls})

        if 'error' in geo_result:
            return jsonify({'error': rpc_error_text(geo_result['error'])}), 400

        area_km2 = calculate_area(geo_json)
        area_result = rpc_call('set_area_tag', {'id': area_id, 'name': 'area_km2', 'value': area_km2})

        if 'error' in area_result:
            return jsonify({'error': rpc_error_text(area_result['error'])}), 400

        return jsonify({'success': True, 'message': 'GeoJSON and area updated successfully'})

    result = rpc_call('set_area_tag', {'id': area_id, 'name': key, 'value': value})
    if 'error' in result:
        return jsonify({'error': rpc_error_text(result['error'])}), 400
    return jsonify({'success': True})


@app.route('/api/set_area_image', methods=['POST'])
@login_required
def set_area_image():
    data = request.json
    if not data:
        return jsonify({'error': 'Invalid request data'}), 400

    area_id = data.get('area_id')
    image_base64 = data.get('image_base64')

    if not area_id or not image_base64:
        return jsonify({'error': 'Missing required fields: area_id, image_base64'}), 400

    area, area_error = get_area_result(area_id)
    if not area:
        return area_lookup_error(area_error)

    result = rpc_call('set_area_image', {
        'area_id': area_id,
        'image_base64': image_base64,
    })

    if 'error' in result:
        return jsonify({
            'error': rpc_error_text(result['error'], 'Failed to update image')
        }), 400

    return jsonify({'success': True, 'result': result.get('result')})


@app.route('/api/search_osm')
@login_required
def search_osm():
    """Search OpenStreetMap via Nominatim and return places with GeoJSON polygons."""
    query = request.args.get('q', '')
    if not query:
        return jsonify({'error': 'Query parameter required'}), 400
    
    try:
        response = requests.get(
            'https://nominatim.openstreetmap.org/search',
            params={
                'q': query,
                'format': 'json',
                'polygon_geojson': 1,
                'extratags': 1,
                'limit': 20
            },
            headers={
                'User-Agent': 'BTCMapAdmin/1.0 (btcmap.org admin tool)'
            },
            timeout=15
        )
        response.raise_for_status()
        
        results = response.json()
        
        # Filter to only relations (have proper administrative boundaries)
        # and only include results that have geojson
        relations = [
            r for r in results 
            if r.get('osm_type') == 'relation' and r.get('geojson')
        ]
        
        return jsonify(relations)
    except requests.exceptions.Timeout:
        return jsonify({'error': 'Search request timed out'}), 408
    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code if e.response is not None else 500
        if status_code == 429:
            app.logger.warning(f"Nominatim rate limit reached for query '{query}'")
            return jsonify({'error': 'OpenStreetMap search is temporarily rate-limited. Please try again in a minute.'}), 429
        app.logger.error(f"HTTP error searching OSM: {str(e)}")
        return jsonify({'error': f'Search failed: {str(e)}'}), status_code
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error searching OSM: {str(e)}")
        return jsonify({'error': f'Search failed: {str(e)}'}), 500


@app.route('/api/proxy_image', methods=['POST'])
@login_required
def proxy_image():
    """Proxy endpoint to fetch images from URLs (avoids CORS issues)."""
    data = request.json
    if not data:
        return jsonify({'error': 'Invalid request data'}), 400
    
    url = data.get('url')
    if not url:
        return jsonify({'error': 'Missing URL parameter'}), 400
    
    try:
        # Validate URL
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return jsonify({'error': 'Invalid URL format'}), 400
        
        # Fetch the image
        response = requests.get(url, timeout=30, stream=True)
        response.raise_for_status()
        
        # Validate content type
        content_type = response.headers.get('Content-Type', '')
        if not content_type.startswith('image/'):
            return jsonify({'error': f'URL does not point to an image (got {content_type})'}), 400
        
        # Check file size (max 10MB)
        content_length = response.headers.get('Content-Length')
        if content_length and int(content_length) > 10 * 1024 * 1024:
            return jsonify({'error': 'Image too large (max 10MB)'}), 400
        
        # Read and encode as base64
        import base64
        image_data = response.content
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        
        return jsonify({
            'success': True,
            'image_base64': image_base64,
            'content_type': content_type.split(';')[0].strip()
        })
    
    except requests.exceptions.Timeout:
        return jsonify({'error': 'Request timed out'}), 408
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error fetching image: {str(e)}")
        return jsonify({'error': f'Failed to fetch image: {str(e)}'}), 400
    except Exception as e:
        app.logger.error(f"Error proxying image: {str(e)}")
        return jsonify({'error': f'Error: {str(e)}'}), 500


@app.route('/api/remove_area_tag', methods=['POST'])
@login_required
def remove_area_tag():
    data = request.json
    if not data:
        return jsonify({'error': 'Invalid request data'}), 400

    area_id = data.get('id')
    tag = data.get('tag')

    area, area_error = get_area_result(area_id)
    if not area:
        return area_lookup_error(area_error)

    area_type = area['tags'].get('type')
    if not area_type or area_type not in AREA_TYPES:
        return jsonify({'error': 'Invalid area type'}), 400

    if AREA_TYPE_REQUIREMENTS.get(area_type, {}).get(tag, {}).get('required', False):
        return jsonify({'error': f'Cannot remove required tag: {tag}'}), 400

    result = rpc_call('remove_area_tag', {'id': area_id, 'tag': tag})
    if 'error' in result:
        return jsonify({'error': rpc_error_text(result['error'])}), 400
    return jsonify({'success': True})


@app.route('/api/remove_area', methods=['POST'])
@login_required
def remove_area():
    data = request.json
    if not data:
        return jsonify({'error': 'Invalid request data'}), 400

    result = rpc_call('remove_area', {'id': data.get('id')})
    if 'error' in result:
        return jsonify({'error': rpc_error_text(result['error'])}), 400
    return jsonify({'success': True})


@app.route('/api/search_areas', methods=['POST'])
@login_required
def search_areas():
    try:
        data = request.get_json()
        query = data.get('query', '').lower()

        result = rpc_call('search', {'query': query})

        if result is None:
            app.logger.error("RPC call returned None")
            return jsonify({'error': 'Server communication error'}), 500

        if 'error' in result:
            app.logger.error(f"Error in RPC call: {result['error']}")
            return jsonify({'error': rpc_error_text(result['error'])}), 400

        areas = result.get('result', [])
        filtered_areas = []
        for area in areas:
            if area['type'] != 'area':
                continue

            area_id = area['id']
            is_deleted = False

            # Fetch area from REST API to get deleted_at field
            # (RPC search results don't include deleted_at)
            try:
                api_response = requests.get(f"{API_BASE_URL}/v3/areas/{area_id}", timeout=10)
                if api_response.ok:
                    area_data = api_response.json()
                    is_deleted = bool(area_data.get('deleted_at'))
            except requests.exceptions.RequestException:
                # If we can't fetch, assume not deleted
                pass

            filtered_areas.append({
                'id': area['id'],
                'name': area['name'],
                'type': area['type'],
                'deleted': is_deleted
            })

        return jsonify(filtered_areas)
    except SessionExpired:
        # Must reach the app-level handler, not the catch-all below.
        raise
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Network error in search_areas: {str(e)}")
        return jsonify({'error':
                        "Network error. Please try again later."}), 500
    except Exception as e:
        app.logger.error(f"Error in search_areas: {str(e)}")
        return jsonify({
            'error':
            "An unexpected error occurred. Please try again later."}), 500


# ============================================
# Linting Routes
# ============================================

@app.route('/maintenance')
@login_required
def maintenance():
    """Render the global linting dashboard."""
    return render_template('maintenance.html')


@app.route('/api/lint/area/<string:area_id>')
@login_required
def lint_single_area(area_id):
    """Get lint results for a single area."""
    area, area_error = get_area_result(area_id)
    if not area:
        return area_lookup_error(area_error)
    
    issues = lint_area_dict(area)
    return jsonify({
        'area_id': area_id,
        'issues': issues
    })


@app.route('/api/lint/sync', methods=['POST'])
@login_required
def lint_sync():
    """Sync areas from API and run lint checks.
    
    Fetches areas in batches using updated_since cursor.
    Continues until no new areas are returned.
    """
    import time
    
    INITIAL_SYNC_DATE = '2022-09-01T00:00:00.000Z'
    
    if lint_cache.is_syncing:
        return jsonify({
            'error': 'Sync already in progress',
            'progress': lint_cache.sync_progress
        }), 409
    
    try:
        lint_cache.is_syncing = True
        lint_cache.sync_progress = {'current': 0, 'total': 0}
        
        # Determine sync start point
        is_incremental = lint_cache.last_sync is not None and len(lint_cache.results) > 0
        
        if is_incremental and lint_cache.last_sync_cursor:
            updated_since = lint_cache.last_sync_cursor
            app.logger.info(f"Incremental sync from {updated_since}")
        else:
            updated_since = INITIAL_SYNC_DATE
            lint_cache.results = []
            app.logger.info(f"Full sync from {updated_since}")
        
        batch_size = 100
        total_processed = 0
        total_fetched = 0
        newest_update = None  # Track global newest for final sync cursor
        seen_ids = set(r['area_id'] for r in lint_cache.results)
        batch_count = 0
        
        while True:
            batch_count += 1
            api_url = f"{API_BASE_URL}/v3/areas?updated_since={updated_since}&limit={batch_size}"
            app.logger.info(f"Batch {batch_count}: {api_url}")
            
            try:
                response = requests.get(api_url, timeout=30)
                response.raise_for_status()
                areas = response.json()
            except requests.exceptions.RequestException as e:
                app.logger.error(f"Error fetching areas: {str(e)}")
                break
            
            # No more areas - we're done
            if not areas:
                app.logger.info("No areas returned, sync complete")
                break
            
            total_fetched += len(areas)
            new_in_batch = 0
            batch_last_timestamp = None  # Track last item's timestamp for pagination cursor
            
            for area in areas:
                area_id = str(area.get('id', ''))
                area_updated = area.get('updated_at', '')
                
                # Track newest timestamp globally for final sync cursor storage
                if area_updated:
                    if newest_update is None or area_updated > newest_update:
                        newest_update = area_updated
                    # Track last item's timestamp for pagination
                    batch_last_timestamp = area_updated
                
                # Skip already seen areas
                if area_id in seen_ids:
                    continue
                
                seen_ids.add(area_id)
                new_in_batch += 1
                
                # Cache all areas (including deleted)
                lint_cache.update_area(area_id, area)
                total_processed += 1
            
            lint_cache.sync_progress = {'current': total_processed, 'total': total_processed}
            app.logger.info(f"Batch {batch_count}: {len(areas)} fetched, {new_in_batch} new, {total_processed} communities total")
            
            # If we got fewer than batch_size, no more results available
            if len(areas) < batch_size:
                app.logger.info(f"Received {len(areas)} < {batch_size}, sync complete")
                break
            
            # If no new areas in batch, we've seen them all - advance cursor
            if new_in_batch == 0:
                # Advance cursor by 1ms to move past current batch
                try:
                    dt = datetime.fromisoformat(updated_since.replace('Z', '+00:00'))
                    dt = dt + timedelta(milliseconds=1)
                    new_cursor = dt.strftime('%Y-%m-%dT%H:%M:%S.') + f'{dt.microsecond // 1000:03d}Z'
                    if new_cursor == updated_since:
                        app.logger.info("Cannot advance cursor, sync complete")
                        break
                    updated_since = new_cursor
                    app.logger.info(f"No new areas, advancing cursor to {updated_since}")
                except Exception as e:
                    app.logger.error(f"Error advancing cursor: {e}")
                    break
            else:
                # Use the LAST item's timestamp from this batch as cursor
                # (not the global max, as results may not be sorted by updated_at)
                if batch_last_timestamp:
                    updated_since = batch_last_timestamp
            
            # Pause between batches
            time.sleep(0.3)
        
        # Update cache metadata
        lint_cache.last_sync = datetime.now()
        if newest_update:
            lint_cache.last_sync_cursor = newest_update
        
        # Derive country for all communities based on geo_json centroids
        app.logger.info("Deriving countries for communities...")
        lint_cache.derive_countries_for_all_communities()
        app.logger.info("Country derivation complete")
        
        # Detect URL alias clashes
        app.logger.info("Detecting URL alias clashes...")
        lint_cache.detect_url_alias_clashes()
        app.logger.info("URL alias clash detection complete")
        
        app.logger.info(f"Sync complete: {batch_count} batches, {total_fetched} fetched, {len(seen_ids)} unique, {total_processed} communities")
        
        return jsonify({
            'success': True,
            'processed': total_processed,
            'total_fetched': total_fetched,
            'batches': batch_count,
            'is_incremental': is_incremental,
            'summary': lint_cache.get_summary()
        })
    
    except Exception as e:
        app.logger.error(f"Error in lint sync: {str(e)}")
        return jsonify({'error': str(e)}), 500
    
    finally:
        lint_cache.is_syncing = False


@app.route('/api/lint/results')
@login_required
def lint_results():
    """Get cached lint results with optional filters."""
    rule_filter = request.args.get('rule')
    severity_filter = request.args.get('severity')
    type_filter = request.args.get('type')
    country_filter = request.args.get('country')
    include_deleted = request.args.get('include_deleted', 'false').lower() == 'true'
    issues_only = request.args.get('issues_only', 'true').lower() == 'true'
    
    # Parse tag filters from query params (format: tag.name=value)
    tag_filters = {}
    for key, value in request.args.items():
        if key.startswith('tag.'):
            tag_name = key[4:]  # Remove 'tag.' prefix
            # Empty value means "tag exists" (any value)
            tag_filters[tag_name] = value if value else None
    
    results = lint_cache.get_results(
        rule_filter=rule_filter,
        severity_filter=severity_filter,
        type_filter=type_filter,
        include_deleted=include_deleted,
        issues_only=issues_only,
        tag_filters=tag_filters if tag_filters else None,
        country_id=country_filter
    )
    
    return jsonify({
        'results': results,
        'summary': lint_cache.get_summary(
            rule_filter=rule_filter,
            severity_filter=severity_filter,
            type_filter=type_filter,
            include_deleted=include_deleted,
            issues_only=issues_only,
            tag_filters=tag_filters if tag_filters else None,
            country_id=country_filter
        )
    })


@app.route('/api/lint/summary')
@login_required
def lint_summary():
    """Get lint summary statistics."""
    rule_filter = request.args.get('rule')
    severity_filter = request.args.get('severity')
    type_filter = request.args.get('type')
    country_filter = request.args.get('country')
    include_deleted = request.args.get('include_deleted', 'false').lower() == 'true'
    
    # Parse tag filters from query params (format: tag.name=value)
    tag_filters = {}
    for key, value in request.args.items():
        if key.startswith('tag.'):
            tag_name = key[4:]  # Remove 'tag.' prefix
            # Empty value means "tag exists" (any value)
            tag_filters[tag_name] = value if value else None
    
    return jsonify(lint_cache.get_summary(
        rule_filter=rule_filter,
        severity_filter=severity_filter,
        type_filter=type_filter,
        include_deleted=include_deleted,
        tag_filters=tag_filters if tag_filters else None,
        country_id=country_filter
    ))


@app.route('/api/lint/tags')
@login_required
def lint_tags():
    """Get list of available tags across all cached areas."""
    return jsonify({'tags': lint_cache.get_available_tags()})


@app.route('/api/lint/fix', methods=['POST'])
@login_required
def lint_fix():
    """Execute an auto-fix action for a lint issue."""
    data = request.json
    if not data:
        return jsonify({'error': 'Invalid request data'}), 400
    
    area_id = data.get('area_id')
    fix_action = data.get('fix_action')
    
    if not area_id or not fix_action:
        return jsonify({'error': 'Missing area_id or fix_action'}), 400
    
    if fix_action not in FIX_ACTIONS:
        return jsonify({'error': f'Unknown fix action: {fix_action}'}), 400
    
    # Execute the fix
    if fix_action == 'migrate_icon':
        result = fix_migrate_icon(area_id, rpc_call, get_area)
    elif fix_action == 'bump_verified':
        result = fix_bump_verified(area_id, rpc_call)
    else:
        return jsonify({'error': f'Fix action not implemented: {fix_action}'}), 400
    
    if result.get('success'):
        # Re-lint the area and update cache
        area = get_area(area_id)
        if area:
            lint_cache.update_area(area_id, area)
        return jsonify(result)
    else:
        return jsonify(result), 400


@app.route('/api/lint/rules')
@login_required
def lint_rules():
    """Get available lint rules."""
    rules = [rule.to_dict() for rule in LINT_RULES.values()]
    return jsonify({'rules': rules})


@app.route('/api/lint/countries')
@login_required
def lint_countries():
    """Get list of countries that have at least one community in them."""
    countries = lint_cache.get_countries_with_communities()
    return jsonify({'countries': countries})


@app.route('/api/lint/community-orgs')
@login_required
def lint_community_orgs():
    """Get list of unique community_org tag values."""
    orgs = lint_cache.get_community_orgs()
    return jsonify({'community_orgs': orgs})

@app.route('/api/gitea/get-issue/<int:issue_id>')
@login_required
def get_issue_data(issue_id):
    try:
        req_data = requests.get(
            f"https://gitea.btcmap.org/api/v1/repos/teambtcmap/btcmap-data/issues/{issue_id}",
            timeout=15,
        )
        req_data.raise_for_status()
        return jsonify({'data': req_data.json()})
    except requests.exceptions.Timeout:
        return jsonify({'error': 'Request to Gitea timed out'}), 408
    except requests.exceptions.RequestException as exc:
        app.logger.error(f"Error fetching Gitea issue {issue_id}: {exc}")
        return jsonify({'error': 'Failed to fetch issue data'}), 502

def rpc_error_text(error, fallback='The BTC Map API rejected this request'):
    """Readable message for a JSON-RPC ``error`` member (see ``rpc_errors``)."""
    return rpc_error_message(error, fallback)


def area_lookup_error(area_error):
    """Response for a ``get_area`` that the API refused or could not resolve."""
    if is_not_found(area_error):
        return jsonify({'error': 'Area not found'}), 404
    if is_transport_error(area_error):
        # rpc_call() turns a timeout/network failure into an error message of
        # its own; that is the API being unreachable, not a refusal.
        return jsonify({'error': area_error}), 502
    return jsonify({'error': area_error or 'This area is not available to your account'}), 403


def get_area_result(area_id):
    """``get_area`` with the API's failure message kept.

    Returns ``(area, error_message)``: ``error_message`` explains a refusal
    such as "Area 53 is outside your geofence (allowed areas: [364])", which
    would otherwise be flattened into "Area not found".
    """
    result = rpc_call('get_area', {'id': area_id})
    if 'error' not in result:
        return result.get('result'), None
    error = rpc_error_text(result['error'])
    app.logger.debug(f"get_area({area_id}) returned error: {error}")
    return None, error


def get_area(area_id):
    """Area by id or alias, or ``None`` when it cannot be loaded."""
    area, _error = get_area_result(area_id)
    return area


def _token_rejected(token):
    """True when the API rejects the token outright (not a network failure)."""
    try:
        return fetch_me(token) is None
    except (requests.exceptions.RequestException, TypeError):
        return False


def rpc_call(method, params):
    token = token_from_request()
    if not token:
        raise SessionExpired()

    headers = {'Authorization': f'Bearer {token}'}
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1
    }
    try:
        response = requests.post(f"{API_BASE_URL}/rpc",
                                 json=payload,
                                 headers=headers,
                                 timeout=20)
        if response.status_code in (401, 403):
            raise SessionExpired()
        response.raise_for_status()
        data = response.json()
        if data.get('error') and _token_rejected(token):
            # A revoked or unknown token surfaces here as a JSON-RPC error with
            # HTTP 200 ("Query returned no rows" from the token lookup), not as
            # a 401 — confirm against /users/me before blaming the request.
            raise SessionExpired()
        return data
    except SessionExpired:
        raise
    except requests.exceptions.Timeout:
        error_msg = f"Timeout error in RPC call to {method}"
        app.logger.error(error_msg)
        return {"error": {"message": error_msg}}
    except requests.exceptions.RequestException as e:
        error_msg = f"Network error in RPC call to {method}: {str(e)}"
        app.logger.error(error_msg)
        return {"error": {"message": error_msg}}
    except Exception as e:
        error_msg = f"Unexpected error in RPC call to {method}: {str(e)}"
        app.logger.error(error_msg)
        return {"error": {"message": error_msg}}

def calculate_area(geo_json):
    if isinstance(geo_json, str):
        geo_json = json.loads(geo_json)

    geom = shape(geo_json)

    proj = pyproj.Proj(proj='aea', lat_1=geom.bounds[1], lat_2=geom.bounds[3])

    def project(x, y):
        return proj(x, y)

    geom_proj = transform(project, geom)

    area_m2 = geom_proj.area

    return round(area_m2 / 1_000_000, 2)

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
        app.logger.info("=== SERVER: validate_geo_json called ===")

        if isinstance(value, str):
            geo_json = json.loads(value)
        elif isinstance(value, dict):
            geo_json = value
        else:
            return False, "Invalid GeoJSON: must be a JSON object or a valid JSON string"

        app.logger.info(f"SERVER: Input type: {type(value)}")
        app.logger.info(f"SERVER: Input value: {value}")
        app.logger.info(f"SERVER: geo_json type: {geo_json.get('type')}")
        app.logger.info(f"SERVER: geo_json keys: {list(geo_json.keys()) if isinstance(geo_json, dict) else 'N/A'}")

        if not isinstance(geo_json, dict):
            return False, "Invalid GeoJSON: must be a JSON object"

        # Extract geometry if it's wrapped in a Feature
        if geo_json.get('type') == 'Feature':
            app.logger.info("SERVER: Extracting geometry from Feature")
            geo_json = geo_json.get('geometry', geo_json)
        elif geo_json.get('type') == 'FeatureCollection' and 'features' in geo_json:
            app.logger.info("SERVER: Extracting geometry from FeatureCollection")
            geo_json = geo_json['features'][0].get('geometry', geo_json)

        app.logger.info(f"SERVER: After extraction, type: {geo_json.get('type')}")
        app.logger.info(f"SERVER: After extraction, keys: {list(geo_json.keys())}")

        try:
            geom = shape(geo_json)
            if geom.geom_type not in ['Polygon', 'MultiPolygon']:
                return False, "Invalid GeoJSON: only valid Polygon and MultiPolygon types are accepted"

            # Rewind the GeoJSON to ensure correct orientation
            rewound = rewind(geo_json)

            app.logger.info(f"SERVER: Rewound type: {rewound.get('type')}")
            app.logger.info(f"SERVER: Rewound keys: {list(rewound.keys())}")
            app.logger.info(f"SERVER: Rewound value: {rewound}")

            return True, {
                "geo_json":
                rewound  # Return the object directly, not stringified
            }
        except Exception as e:
            app.logger.error(f"SERVER ERROR: {str(e)}")
            return False, f"Invalid GeoJSON structure: {str(e)}"
    except json.JSONDecodeError as e:
        app.logger.error(f"SERVER JSON ERROR: {str(e)}")
        return False, "Invalid JSON format"
    except Exception as e:
        app.logger.error(f"SERVER EXCEPTION ERROR: {str(e)}")
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
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() in ('1', 'true', 'yes', 'on')
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)
