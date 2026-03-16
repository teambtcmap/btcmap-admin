"""Authentication blueprint for Nostr and BTC Map credential login."""

import json
import os
from datetime import datetime

import logging

import requests
from flask import Blueprint, jsonify, redirect, request, url_for
from flask_login import login_required, login_user, logout_user
from nostr_sdk import Event

from models import User
from nostr_utils import get_event_pubkey, verify_nip98_event
from user_store import get_user_store


auth_bp = Blueprint('auth', __name__, url_prefix='/auth')
API_BASE_URL = os.environ.get('API_BASE_URL', 'https://api.btcmap.org')
logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.utcnow().isoformat() + 'Z'


def external_request_url(req) -> str:
    """Build request URL honoring reverse-proxy forwarded proto/host headers."""
    forwarded_proto = (req.headers.get('X-Forwarded-Proto') or '').split(',')[0].strip()
    forwarded_host = (req.headers.get('X-Forwarded-Host') or '').split(',')[0].strip()

    scheme = forwarded_proto or req.scheme
    host = forwarded_host or req.host
    path = req.full_path if req.query_string else req.path
    if path.endswith('?'):
        path = path[:-1]
    return f'{scheme}://{host}{path}'


def create_btcmap_api_key(username, password, label=None):
    """Create a BTC Map API token using username/password credentials."""
    params = {'username': username, 'password': password}
    if label:
        params['label'] = label

    payload = {
        'jsonrpc': '2.0',
        'method': 'create_api_key',
        'params': params,
        'id': 1,
    }

    response = requests.post(f'{API_BASE_URL}/rpc', json=payload, timeout=20)
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
    """Verify signed NIP-98 event and login using linked/internal account."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Invalid request data'}), 400

    event_data = data.get('event')
    if not event_data:
        return jsonify({'error': 'Missing event'}), 400

    try:
        is_valid, error_msg = verify_nip98_event(
            event_data,
            external_request_url(request),
            'POST',
            max_age_seconds=60,
        )
        if not is_valid:
            return jsonify({'error': f'Invalid NIP-98 event: {error_msg}'}), 400

        event = Event.from_json(json.dumps(event_data))
        nostr_pubkey = get_event_pubkey(event)

        store = get_user_store()
        account = store.find_account_by_nostr(nostr_pubkey)
        if not account:
            account = store.create_account(auth_type='nostr')
            store.link_nostr(account['account_id'], nostr_pubkey)

        store.update_account_metadata(
            account['account_id'],
            auth_type=account.get('auth_type', 'nostr'),
            last_login=_utc_now_iso(),
            last_login_method='nostr',
        )

        user = User(account['account_id'])
        login_user(user)

        return jsonify({
            'success': True,
            'nostr_pubkey': nostr_pubkey,
            'has_token': user.has_rpc_token,
        })
    except Exception:
        logger.exception('NIP-98 verification/login failed')
        return jsonify({'error': 'Verification failed'}), 400


@auth_bp.route('/btcmap/login', methods=['POST'])
def btcmap_login():
    """Login with BTC Map credentials, create fresh key, and overwrite token."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Invalid request data'}), 400

    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400

    label = f'btcmap-admin:btcmap-login:{_utc_now_iso()}'
    try:
        token = create_btcmap_api_key(username=username, password=password, label=label)
    except requests.exceptions.RequestException:
        return jsonify({'error': 'Unable to reach BTC Map API'}), 502
    except ValueError as e:
        return jsonify({'error': str(e)}), 401

    store = get_user_store()
    account = store.find_account_by_btcmap(username)
    if not account:
        account = store.create_account(auth_type='btcmap')
        store.link_btcmap(account['account_id'], username)

    store.set_account_token(account['account_id'], token)
    store.update_account_metadata(
        account['account_id'],
        auth_type=account.get('auth_type', 'btcmap'),
        last_login=_utc_now_iso(),
        last_login_method='btcmap',
    )

    user = User(account['account_id'])
    login_user(user)
    return jsonify({'success': True, 'has_token': True})


@auth_bp.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))
