"""User account storage with encrypted token support.

This module stores accounts keyed by internal account_id and maintains
separate identity indexes for Nostr pubkeys and BTC Map usernames.
"""

import fcntl
import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet, InvalidToken


def _utc_now_iso() -> str:
    return datetime.utcnow().isoformat() + 'Z'


class UserStore:
    """Handles account persistence with encrypted token storage."""

    def __init__(self, storage_path: str = 'users.json', cipher_key: Optional[str] = None):
        self.storage_path = storage_path

        key = cipher_key or os.environ.get('TOKEN_CIPHER_KEY')
        if not key:
            raise ValueError(
                'TOKEN_CIPHER_KEY environment variable is required. '
                'Generate one with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
            )
        self.cipher = Fernet(key.encode())

    def _load_store(self) -> Dict[str, Any]:
        """Load store under a lock, auto-migrating legacy shape if needed."""
        if not os.path.exists(self.storage_path):
            return self._empty_store()

        with open(self.storage_path, 'r+') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                content = f.read().strip()
                raw = json.loads(content) if content else {}
                if self._is_v2(raw):
                    return raw
                migrated = self._migrate_legacy(raw)
                f.seek(0)
                f.truncate()
                json.dump(migrated, f, indent=2)
                return migrated
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def _save_store(self, store: Dict[str, Any]) -> None:
        """Save full store under exclusive lock."""
        with open(self.storage_path, 'w') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                json.dump(store, f, indent=2)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def _encrypt_token(self, token: str) -> str:
        return self.cipher.encrypt(token.encode()).decode()

    def _decrypt_token(self, encrypted_token: str) -> Optional[str]:
        try:
            return self.cipher.decrypt(encrypted_token.encode()).decode()
        except InvalidToken:
            return None

    def _empty_store(self) -> Dict[str, Any]:
        return {
            'accounts': {},
            'index_nostr': {},
            'index_btcmap': {},
            'schema_version': 2,
            'migrated_at': _utc_now_iso(),
        }

    def _is_v2(self, data: Dict[str, Any]) -> bool:
        return isinstance(data, dict) and 'accounts' in data and 'index_nostr' in data and 'index_btcmap' in data

    def _migrate_legacy(self, legacy_data: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate legacy identity-keyed records to account model."""
        new_store = self._empty_store()
        if not legacy_data:
            return new_store

        for legacy_key, legacy_user in legacy_data.items():
            if not isinstance(legacy_user, dict):
                continue

            account_id = str(uuid.uuid4())
            is_btcmap = isinstance(legacy_key, str) and legacy_key.startswith('btcmap:')
            btcmap_username = legacy_key.split(':', 1)[1] if is_btcmap else legacy_user.get('btcmap_username')
            nostr_pubkey = None if is_btcmap else legacy_key

            account = {
                'account_id': account_id,
                'auth_type': legacy_user.get('auth_type', 'btcmap' if is_btcmap else 'nostr'),
                'nostr_pubkey': nostr_pubkey,
                'btcmap_username': btcmap_username,
                'last_login': legacy_user.get('last_login'),
                'last_login_method': legacy_user.get('last_login_method'),
                'created_at': legacy_user.get('created_at', _utc_now_iso()),
                'updated_at': legacy_user.get('updated_at', _utc_now_iso()),
            }

            if legacy_user.get('rpc_token_encrypted'):
                account['rpc_token_encrypted'] = legacy_user['rpc_token_encrypted']
            elif legacy_user.get('rpc_token'):
                account['rpc_token_encrypted'] = self._encrypt_token(legacy_user['rpc_token'])

            new_store['accounts'][account_id] = account
            if nostr_pubkey:
                new_store['index_nostr'][nostr_pubkey] = account_id
            if btcmap_username:
                new_store['index_btcmap'][btcmap_username.lower()] = account_id

        new_store['migrated_at'] = _utc_now_iso()
        return new_store

    def with_store_update(self, updater):
        """Run read-modify-write atomically under one exclusive file lock."""
        if not os.path.exists(self.storage_path):
            with open(self.storage_path, 'w') as f:
                json.dump(self._empty_store(), f, indent=2)

        with open(self.storage_path, 'r+') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                content = f.read().strip()
                raw = json.loads(content) if content else {}
                store = raw if self._is_v2(raw) else self._migrate_legacy(raw)
                result = updater(store)
                f.seek(0)
                f.truncate()
                json.dump(store, f, indent=2)
                return result
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def _account_with_decrypted_token(self, account: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(account)
        encrypted = data.get('rpc_token_encrypted')
        data['rpc_token'] = self._decrypt_token(encrypted) if encrypted else None
        return data

    def get_account(self, account_id: str) -> Optional[Dict[str, Any]]:
        store = self._load_store()
        account = store['accounts'].get(account_id)
        if not account:
            return None
        return self._account_with_decrypted_token(account)

    def create_account(self, auth_type: str = 'nostr') -> Dict[str, Any]:
        def updater(store):
            account_id = str(uuid.uuid4())
            account = {
                'account_id': account_id,
                'auth_type': auth_type,
                'nostr_pubkey': None,
                'btcmap_username': None,
                'last_login': None,
                'last_login_method': None,
                'created_at': _utc_now_iso(),
                'updated_at': _utc_now_iso(),
            }
            store['accounts'][account_id] = account
            return self._account_with_decrypted_token(account)

        return self.with_store_update(updater)

    def find_account_by_nostr(self, nostr_pubkey: str) -> Optional[Dict[str, Any]]:
        store = self._load_store()
        account_id = store['index_nostr'].get(nostr_pubkey)
        if not account_id:
            return None
        account = store['accounts'].get(account_id)
        return self._account_with_decrypted_token(account) if account else None

    def find_account_by_btcmap(self, username: str) -> Optional[Dict[str, Any]]:
        store = self._load_store()
        account_id = store['index_btcmap'].get(username.lower())
        if not account_id:
            return None
        account = store['accounts'].get(account_id)
        return self._account_with_decrypted_token(account) if account else None

    def link_nostr(self, account_id: str, nostr_pubkey: str) -> None:
        def updater(store):
            mapped = store['index_nostr'].get(nostr_pubkey)
            if mapped and mapped != account_id:
                raise ValueError('Nostr pubkey is already linked to another account')

            account = store['accounts'].get(account_id)
            if not account:
                raise ValueError('Account not found')

            previous = account.get('nostr_pubkey')
            if previous and previous != nostr_pubkey:
                store['index_nostr'].pop(previous, None)

            account['nostr_pubkey'] = nostr_pubkey
            account['updated_at'] = _utc_now_iso()
            store['index_nostr'][nostr_pubkey] = account_id

        self.with_store_update(updater)

    def link_btcmap(self, account_id: str, username: str) -> None:
        uname = username.strip()
        lower = uname.lower()

        def updater(store):
            mapped = store['index_btcmap'].get(lower)
            if mapped and mapped != account_id:
                raise ValueError('BTC Map username is already linked to another account')

            account = store['accounts'].get(account_id)
            if not account:
                raise ValueError('Account not found')

            previous = account.get('btcmap_username')
            if previous and previous.lower() != lower:
                store['index_btcmap'].pop(previous.lower(), None)

            account['btcmap_username'] = uname
            account['updated_at'] = _utc_now_iso()
            store['index_btcmap'][lower] = account_id

        self.with_store_update(updater)

    def set_account_token(self, account_id: str, token: Optional[str]) -> None:
        def updater(store):
            account = store['accounts'].get(account_id)
            if not account:
                raise ValueError('Account not found')

            if token:
                account['rpc_token_encrypted'] = self._encrypt_token(token)
            else:
                account.pop('rpc_token_encrypted', None)
            account['updated_at'] = _utc_now_iso()

        self.with_store_update(updater)

    def update_account_metadata(self, account_id: str, **updates: Any) -> None:
        def updater(store):
            account = store['accounts'].get(account_id)
            if not account:
                raise ValueError('Account not found')

            for key, value in updates.items():
                account[key] = value
            account['updated_at'] = _utc_now_iso()

        self.with_store_update(updater)


_user_store: Optional[UserStore] = None


def get_user_store() -> UserStore:
    global _user_store
    if _user_store is None:
        _user_store = UserStore()
    return _user_store
