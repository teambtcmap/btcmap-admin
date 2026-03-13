"""Authentication blueprint for Nostr and BTC Map credential login."""

import json
import os
from datetime import datetime

import requests
from flask import Blueprint, request, jsonify, redirect, url_for
from flask_login import login_user, logout_user, login_required
from nostr_sdk import Event

from nostr_utils import verify_nip98_event, get_event_pubkey
from user_store import get_user_store


auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

API_BASE_URL = os.environ.get('API_BASE_URL', 'https://api.btcmap.org')


def create_btcmap_api_key(username, password, label=None):
    """Create a BTC Map API token using username/password credentials."""
    params = {
        'username': username,
        'password': password,
    }
    if label:
        params['label'] = label

    payload = {
        'jsonrpc': '2.0',
        'method': 'create_api_key',
        'params': params,
        'id': 1,
    }

    response = requests.post(
        f'{API_BASE_URL}/rpc',
        json=payload,
        timeout=20,
    )
    response.raise_for_status()
    result = response.json()

    if 'error' in result:
        message = result['error'].get('message', 'Failed to create BTC Map API key')
        raise ValueError(message)

    token = result.get('result', {}).get('token')
    if not token:
        raise ValueError('BTC Map API key response did not include a token')

    return token


@auth_bp.route('/nostr/login', methods=['POST'])
def nostr_login():
    """Verify a NIP-98 signed Nostr event and authenticate the user.
    
    Expected JSON body:
        {
            "event": <signed NIP-98 event>
        }
    
    Returns:
        JSON with success status and user info
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Invalid request data'}), 400
    
    event_data = data.get('event')
    if not event_data:
        return jsonify({'error': 'Missing event'}), 400
    
    try:
        verify_url = request.url
        
        # Verify NIP-98 event
        is_valid, error_msg = verify_nip98_event(
            event_data, 
            verify_url, 
            'POST',
            max_age_seconds=60,
        )
        
        if not is_valid:
            return jsonify({'error': f'Invalid NIP-98 event: {error_msg}'}), 400
        
        # Parse event with nostr-sdk to extract pubkey
        event = Event.from_json(json.dumps(event_data))
        pubkey_hex = get_event_pubkey(event)
        
        # Load or create user
        user_store = get_user_store()
        user_data = user_store.get_user(pubkey_hex)
        
        if not user_data:
            # Create new user
            user_data = {
                'pubkey': pubkey_hex,
                'auth_type': 'nostr',
                'rpc_token': None,
                'last_login': datetime.utcnow().isoformat() + 'Z',
                'last_login_method': 'nostr',
            }
            user_store.save_user(pubkey_hex, user_data)
        else:
            # Update last login
            user_data['last_login'] = datetime.utcnow().isoformat() + 'Z'
            user_data['last_login_method'] = 'nostr'
            user_data['auth_type'] = user_data.get('auth_type', 'nostr')
            user_store.save_user(pubkey_hex, user_data)
        
        # Create user object and log in
        from models import User
        user = User(pubkey_hex)
        login_user(user)
        
        return jsonify({
            'success': True,
            'pubkey': pubkey_hex,
            'has_token': bool(user_data.get('rpc_token')),
        })
    
    except Exception as e:
        return jsonify({'error': f'Verification failed: {str(e)}'}), 400


@auth_bp.route('/btcmap/login', methods=['POST'])
def btcmap_login():
    """Login using BTC Map credentials and create a fresh API key."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Invalid request data'}), 400

    username = (data.get('username') or '').strip()
    password = data.get('password') or ''

    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400

    user_id = f'btcmap:{username}'
    label = f'btcmap-admin:btcmap-login:{datetime.utcnow().isoformat()}Z'

    try:
        token = create_btcmap_api_key(username=username, password=password, label=label)
    except requests.exceptions.RequestException:
        return jsonify({'error': 'Unable to reach BTC Map API'}), 502
    except ValueError as e:
        return jsonify({'error': str(e)}), 401

    user_store = get_user_store()
    user_data = user_store.get_user(user_id) or {}
    user_data.update({
        'pubkey': user_id,
        'auth_type': 'btcmap',
        'btcmap_username': username,
        'rpc_token': token,
        'last_login': datetime.utcnow().isoformat() + 'Z',
        'last_login_method': 'btcmap',
    })
    user_store.save_user(user_id, user_data)

    from models import User
    user = User(user_id)
    login_user(user)

    return jsonify({'success': True, 'has_token': True})


@auth_bp.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    """Log out the current user."""
    logout_user()
    return redirect(url_for('login'))
