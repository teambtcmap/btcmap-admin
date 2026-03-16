"""User model for Flask-Login account-based identities."""

from datetime import datetime

from flask_login import UserMixin
from nostr_sdk import PublicKey

from user_store import get_user_store


class User(UserMixin):
    """Flask-Login user backed by internal account_id."""

    def __init__(self, account_id: str):
        self.account_id = account_id
        self._data = None

    def get_id(self):
        return self.account_id

    @property
    def data(self):
        if self._data is None:
            self._data = get_user_store().get_account(self.account_id) or {}
        return self._data

    @property
    def rpc_token(self):
        return self.data.get('rpc_token')

    @property
    def has_rpc_token(self):
        return bool(self.rpc_token)

    @property
    def nostr_pubkey(self):
        return self.data.get('nostr_pubkey')

    @property
    def nostr_npub(self):
        pubkey = self.nostr_pubkey
        if not pubkey:
            return None
        try:
            return PublicKey.parse(pubkey).to_bech32()
        except Exception:
            return None

    @property
    def btcmap_username(self):
        return self.data.get('btcmap_username')

    @property
    def auth_type(self):
        return self.data.get('auth_type')

    @property
    def last_login(self):
        timestamp = self.data.get('last_login')
        if not timestamp:
            return None
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            return dt.strftime('%B %d, %Y at %I:%M %p UTC')
        except (ValueError, AttributeError):
            return timestamp

    def update_token(self, token):
        get_user_store().set_account_token(self.account_id, token)
        self._data = None

    @property
    def account_id_value(self):
        return self.account_id

    @staticmethod
    def load_user(account_id: str):
        account = get_user_store().get_account(account_id)
        if not account:
            return None
        return User(account_id)
