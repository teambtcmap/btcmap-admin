"""Client-side sign-in endpoints.

The browser exchanges a BTC Map credential for a Bearer token directly with the
API — NIP-98 for Nostr, ``POST /v4/users/{username}/tokens`` for a password.
This blueprint only validates that token once and stores display identity in
the signed session cookie; no account or token is persisted server-side.
"""

import logging

import requests
from flask import Blueprint, jsonify, redirect, request, url_for

import admin_session

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')
logger = logging.getLogger(__name__)


@auth_bp.route('/session', methods=['POST'])
def create_session():
    """Validate a freshly minted Bearer token and start the app session."""
    scheme, _, token = request.headers.get('Authorization', '').partition(' ')
    token = token.strip()
    if scheme.lower() != 'bearer' or not token:
        return jsonify({'error': 'Missing bearer token'}), 400

    try:
        user = admin_session.fetch_me(token)
    except requests.exceptions.RequestException:
        logger.exception('BTC Map API unreachable during sign-in')
        return jsonify({'error': 'Unable to reach BTC Map API'}), 502
    except TypeError:
        logger.exception('Unexpected /v4/users/me payload during sign-in')
        return jsonify({'error': 'Unexpected response from BTC Map API'}), 502

    if user is None:
        return jsonify({'error': 'That token was rejected by BTC Map API'}), 401

    roles = user.get('roles') or []
    if not admin_session.has_area_edit_role(roles):
        return jsonify({
            'error': (
                'This account has no area-editing role (admin, root or '
                'area_manager). Sign in with BTC Map credentials, then link '
                'your Nostr key from the profile page.'
            )
        }), 403

    admin_session.store_identity(user)
    response = jsonify({
        'name': user.get('name'),
        'npub': user.get('npub'),
        'roles': roles,
    })
    # Transport for page navigations only; /api/* calls send the header.
    response.set_cookie(
        admin_session.TOKEN_COOKIE,
        token,
        max_age=60 * 60 * 24 * 7,
        secure=True,
        httponly=True,
        samesite='Lax',
        path='/',
    )
    return response


@auth_bp.route('/logout', methods=['POST'])
def logout():
    """Clear the app session. POST only: a GET logout is CSRF-able."""
    admin_session.sign_out()
    response = redirect(url_for('login'))
    response.delete_cookie(admin_session.TOKEN_COOKIE, path='/')
    return response
