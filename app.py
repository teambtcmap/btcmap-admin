import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_session import Session
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

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

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
        'contact:geyser': {
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


@app.before_request
def check_auth():
    if request.endpoint and request.endpoint not in [
            'login', 'static', 'health'
    ] and 'password' not in session:
        # For API requests, return JSON 401 instead of redirect
        # This allows JavaScript to detect session expiration and handle it gracefully
        if request.path.startswith('/api/') or request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'Session expired', 'session_expired': True}), 401
        return redirect(url_for('login', next=request.url))


@app.route('/')
def index():
    if 'password' in session:
        return redirect(url_for('select_area'))
    return redirect(url_for('login'))


@app.route('/home')
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

        area_type = area['tags'].get('type', '')
        type_requirements = AREA_TYPE_REQUIREMENTS.get(area_type, {})

        geo_json = area['tags'].get('geo_json')
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

        return render_template('show_area.html',
                               area=area,
                               area_type_requirements=type_requirements,
                               geo_json=geo_json,
                               lint_issues=lint_issues)
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
            area_id = area_result.get('id') or area_result.get('tags', {}).get('url_alias')
            return jsonify({'success': True, 'area_id': area_id})
        app.logger.error(f"Error from RPC call: {result['error']}")
        return jsonify({'error': result['error']}), 400

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

        # The API uses json_patch() which merges objects (RFC 7396).
        # To fully replace geo_json, we null out old keys to remove them.
        geo_json_with_nulls = {
            'features': None,  # Remove old FeatureCollection remnants
            'properties': None,  # Remove old Feature remnants
            'geometry': None,  # Remove old Feature remnants
            **geo_json  # Add our actual geometry (type, coordinates)
        }

        geo_result = rpc_call('set_area_tag', {'id': area_id, 'name': 'geo_json', 'value': geo_json_with_nulls})

        if isinstance(geo_result, tuple):
            return geo_result

        area_km2 = calculate_area(geo_json)
        area_result = rpc_call('set_area_tag', {'id': area_id, 'name': 'area_km2', 'value': area_km2})

        if isinstance(area_result, tuple):
            return area_result

        return jsonify({'success': True, 'message': 'GeoJSON and area updated successfully'})

    result = rpc_call('set_area_tag', {'id': area_id, 'name': key, 'value': value})
    if isinstance(result, tuple):
        return result
    return jsonify({'success': True})


@app.route('/api/set_area_icon', methods=['POST'])
def set_area_icon():
    data = request.json
    if not data:
        return jsonify({'error': 'Invalid request data'}), 400

    area_id = data.get('id')
    icon_base64 = data.get('icon_base64')
    icon_ext = data.get('icon_ext')

    if not area_id or not icon_base64 or not icon_ext:
        return jsonify({'error': 'Missing required fields: id, icon_base64, icon_ext'}), 400

    # Validate extension
    allowed_extensions = ['png', 'jpg', 'jpeg', 'webp']
    if icon_ext.lower() not in allowed_extensions:
        return jsonify({'error': f'Invalid file extension. Allowed: {", ".join(allowed_extensions)}'}), 400

    area = get_area(area_id)
    if not area:
        return jsonify({'error': 'Area not found'}), 404

    result = rpc_call('set_area_icon', {
        'id': area_id,
        'icon_base64': icon_base64,
        'icon_ext': icon_ext.lower()
    })
    
    if isinstance(result, tuple):
        return result
    if 'error' in result:
        return jsonify({'error': result['error'].get('message', 'Failed to update icon')}), 400
    
    return jsonify({'success': True, 'result': result.get('result')})


@app.route('/api/proxy_image', methods=['POST'])
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

    if AREA_TYPE_REQUIREMENTS.get(area_type, {}).get(tag, {}).get('required', False):
        return jsonify({'error': f'Cannot remove required tag: {tag}'}), 400

    result = rpc_call('remove_area_tag', {'id': area_id, 'tag': tag})
    if isinstance(result, tuple):
        return result
    return jsonify({'success': True})


@app.route('/api/remove_area', methods=['POST'])
def remove_area():
    data = request.json
    if not data:
        return jsonify({'error': 'Invalid request data'}), 400
        
    result = rpc_call('remove_area', {'id': data.get('id')})
    if isinstance(result, tuple):
        return result
    return jsonify({'success': True})


@app.route('/api/search_areas', methods=['POST'])
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
            return jsonify({'error': result['error']}), 400

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
def maintenance():
    """Render the global linting dashboard."""
    return render_template('maintenance.html')


@app.route('/api/lint/area/<string:area_id>')
def lint_single_area(area_id):
    """Get lint results for a single area."""
    area = get_area(area_id)
    if not area:
        return jsonify({'error': 'Area not found'}), 404
    
    issues = lint_area_dict(area)
    return jsonify({
        'area_id': area_id,
        'issues': issues
    })


@app.route('/api/lint/sync', methods=['POST'])
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
def lint_tags():
    """Get list of available tags across all cached areas."""
    return jsonify({'tags': lint_cache.get_available_tags()})


@app.route('/api/lint/fix', methods=['POST'])
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
def lint_rules():
    """Get available lint rules."""
    rules = [rule.to_dict() for rule in LINT_RULES.values()]
    return jsonify({'rules': rules})


@app.route('/api/lint/countries')
def lint_countries():
    """Get list of countries that have at least one community in them."""
    countries = lint_cache.get_countries_with_communities()
    return jsonify({'countries': countries})


@app.route('/api/lint/community-orgs')
def lint_community_orgs():
    """Get list of unique community_org tag values."""
    orgs = lint_cache.get_community_orgs()
    return jsonify({'community_orgs': orgs})


def get_area(area_id):
    result = rpc_call('get_area', {'id': area_id})
    if 'error' not in result:
        return result.get('result')
    # Log the error for debugging
    app.logger.debug(f"get_area({area_id}) returned error: {result.get('error')}")
    return None

def rpc_call(method, params):
    headers = {
        'Authorization': f'Bearer {session.get("password")}'
    }
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
        response.raise_for_status()
        return response.json()
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
    app.run(host='0.0.0.0', port=5000, debug=False)
