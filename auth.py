"""Nostr authentication blueprint.

Handles NIP-98 HTTP Auth based authentication.
"""

import time
import json
from datetime import datetime
from flask import Blueprint, request, jsonify, redirect, url_for
from flask_login import login_user, logout_user, login_required

from user_store import get_user_store
from nostr_utils import verify_nip98_event, get_event_pubkey
from nostr_sdk import Event


auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/login-url', methods=['GET'])
def login_url():
    """Get the URL and method for NIP-98 auth.
    
    Returns:
        JSON with url and method for signing
    """
    # Get the full verify URL
    verify_url = url_for('auth.verify', _external=True)
    
    return jsonify({
        'url': verify_url,
        'method': 'POST'
    })


@auth_bp.route('/verify', methods=['POST'])
def verify():
    """Verify a NIP-98 signed Nostr event and authenticate the user.
    
    Expected JSON body:
        {
            "event": <signed NIP-98 event>
        }
    
    Returns:
        JSON with success status and user info
    """
    data = request.json
    if not data:
        return jsonify({'error': 'Invalid request data'}), 400
    
    event_data = data.get('event')
    if not event_data:
        return jsonify({'error': 'Missing event'}), 400
    
    try:
        # Get the verify URL for NIP-98 validation
        verify_url = url_for('auth.verify', _external=True)
        
        # Verify NIP-98 event
        is_valid, error_msg = verify_nip98_event(
            event_data, 
            verify_url, 
            'POST',
            max_age_seconds=60
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
                'rpc_token': None,
                'last_login': datetime.utcnow().isoformat() + 'Z'
            }
            user_store.save_user(pubkey_hex, user_data)
        else:
            # Update last login
            user_data['last_login'] = datetime.utcnow().isoformat() + 'Z'
            user_store.save_user(pubkey_hex, user_data)
        
        # Create user object and log in
        from models import User
        user = User(pubkey_hex)
        login_user(user, remember=True)
        
        return jsonify({
            'success': True,
            'pubkey': pubkey_hex,
            'has_token': bool(user_data.get('rpc_token'))
        })
    
    except Exception as e:
        return jsonify({'error': f'Verification failed: {str(e)}'}), 400


@auth_bp.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    """Log out the current user."""
    logout_user()
    return redirect(url_for('login'))
