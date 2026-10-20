"""Session helpers for the admin app.

The BTC Map API is the account authority; nothing about a user is stored here.
The browser keeps the Bearer token in ``localStorage`` and sends it as an
``Authorization`` header on every ``/api/*`` call. A page navigation cannot
carry a header, so ``POST /auth/session`` also mirrors the token into a
``btcmap_token`` cookie that server renders read. The Flask session cookie
holds display-only identity (name, npub, roles) refreshed from
``GET /v4/users/me``; it is never consulted for authorisation — the API's
roles decide what an RPC call may do.
"""

import logging
from functools import wraps

import requests
from flask import current_app, g, jsonify, redirect, request, session, url_for

TOKEN_COOKIE = 'btcmap_token'
SESSION_KEY = 'identity'

# The API's baseline role: on its own it grants nothing this app can use, and
# an identity holding only this role is almost always a fresh account created
# by ``POST /v4/auth/nostr`` for an npub that was never linked to a real user.
#
# Roles that may edit areas at all: ``area_manager`` is limited to the ids in
# the account's ``geofence``, while ``admin``/``root`` normally carry an empty
# one — but the API applies a non-empty geofence to every role, so the scope is
# always read from the account rather than assumed from the role.
AREA_EDIT_ROLES = frozenset({'admin', 'root', 'area_manager'})

logger = logging.getLogger(__name__)


class SessionExpired(Exception):
    """The API rejected the Bearer token this request carried."""


def api_base_url() -> str:
    """Trusted API origin, configured once in ``app.py`` from ``API_BASE_URL``."""
    return current_app.config['API_BASE_URL']


def token_from_request():
    """Return the Bearer token: header first (browser fetches), cookie second (navigations)."""
    scheme, _, value = request.headers.get('Authorization', '').partition(' ')
    if scheme.lower() == 'bearer' and value.strip():
        return value.strip()
    return request.cookies.get(TOKEN_COOKIE) or None


def identity():
    """Display identity from the signed cookie session, or ``None``."""
    return session.get(SESSION_KEY)


def store_identity(user: dict) -> None:
    """Persist the display-only parts of a ``GET /v4/users/me`` payload."""
    session[SESSION_KEY] = {
        'id': user.get('id'),
        'name': user.get('name'),
        'npub': user.get('npub'),
        'roles': list(user.get('roles') or []),
        'geofence': [int(area_id) for area_id in user.get('geofence') or []],
    }
    session.permanent = True


def sign_out() -> None:
    session.pop(SESSION_KEY, None)
    session.modified = True


def expire_token_cookie() -> None:
    """Ask the ``after_request`` hook to delete the navigation cookie."""
    g.expire_token_cookie = True


def has_area_edit_role(roles) -> bool:
    """True when the identity holds a role that can edit areas at all.

    ``area_manager`` counts: the API scopes it to the account's geofence, and
    that scope is enforced per area rather than at sign-in.
    """
    return bool(AREA_EDIT_ROLES.intersection(roles or []))


def fetch_me(token):
    """``GET /v4/users/me``.

    Returns the user dict, ``None`` when the token is rejected, and raises
    ``requests.RequestException`` when the API cannot be reached.
    """
    response = requests.get(
        f'{api_base_url()}/v4/users/me',
        headers={'Authorization': f'Bearer {token}'},
        timeout=10,
    )
    if response.status_code == 401:
        return None
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise TypeError('Unexpected /v4/users/me response')
    return data


class CurrentUser:
    """Template shim keeping the attribute names the templates already use."""

    def __init__(self, data):
        self._data = data or {}

    @property
    def is_authenticated(self):
        return bool(self._data)

    @property
    def id(self):
        return self._data.get('id')

    @property
    def name(self):
        return self._data.get('name')

    @property
    def roles(self):
        return self._data.get('roles') or []

    @property
    def geofence(self):
        """Area ids this account may edit; empty means every area."""
        return tuple(self._data.get('geofence') or ())

    @property
    def is_area_restricted(self):
        return bool(self.geofence)

    def can_edit_area(self, area_id):
        """False when the account's geofence excludes this area.

        Viewing is always allowed; the API refuses tag/image/deletion RPCs for
        areas outside the geofence, so the UI should not offer them.
        """
        if not self.is_area_restricted:
            return True
        try:
            return int(area_id) in self.geofence
        except (TypeError, ValueError):
            return False

    @property
    def npub(self):
        return self._data.get('npub')

    @property
    def btcmap_username(self):
        return self.name

    @property
    def nostr_npub(self):
        return self.npub

    @property
    def has_rpc_token(self):
        # Being signed in now means holding a usable token by construction.
        return self.is_authenticated

    @property
    def last_login(self):
        # The API keeps no per-login timestamp; the profile no longer shows one.
        return None


def current_user() -> CurrentUser:
    return CurrentUser(identity())


def login_required(view):
    """Require a display identity: JSON callers get a 401, navigations redirect."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not identity():
            if request.path.startswith('/api/') or request.is_json:
                return jsonify({'error': 'Session expired', 'session_expired': True}), 401
            return redirect(url_for('login', next=request.full_path.rstrip('?')))
        return view(*args, **kwargs)

    return wrapped
