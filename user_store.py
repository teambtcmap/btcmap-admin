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
            key = Fernet.generate_key().decode()
            print('WARNING: Generated ephemeral cipher key. Set TOKEN_CIPHER_KEY env var for production.')
            print(f'Generated key: {key}')
        self.cipher = Fernet(key.encode())

    def _read_raw(self) -> Dict[str, Any]:
        if not os.path.exists(self.storage_path):
            return {}
        with open(self.storage_path, 'r') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                return json.load(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def _write_raw(self, data: Dict[str, Any]) -> None:
        with open(self.storage_path, 'w') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                json.dump(data, f, indent=2)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def _encrypt_token(self, token: str) -> str:
        return self.cipher.encrypt(token.encode()).decode()

    def _decrypt_token(self, encrypted_token: str) -> Optional[str]:
        try:
            return self.cipher.decrypt(encrypted_token.encode()).decode()
        except (InvalidToken, Exception):
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

    def _load_store(self) -> Dict[str, Any]:
        raw = self._read_raw()
        if self._is_v2(raw):
            return raw
        migrated = self._migrate_legacy(raw)
        self._write_raw(migrated)
        return migrated

    def _save_store(self, store: Dict[str, Any]) -> None:
        self._write_raw(store)

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
        store = self._load_store()
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
        self._save_store(store)
        return self._account_with_decrypted_token(account)

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
        store = self._load_store()
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
        self._save_store(store)

    def link_btcmap(self, account_id: str, username: str) -> None:
        uname = username.strip()
        lower = uname.lower()

        store = self._load_store()
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
        self._save_store(store)

    def set_account_token(self, account_id: str, token: Optional[str]) -> None:
        store = self._load_store()
        account = store['accounts'].get(account_id)
        if not account:
            raise ValueError('Account not found')

        if token:
            account['rpc_token_encrypted'] = self._encrypt_token(token)
        else:
            account.pop('rpc_token_encrypted', None)
        account['updated_at'] = _utc_now_iso()
        self._save_store(store)

    def update_account_metadata(self, account_id: str, **updates: Any) -> None:
        store = self._load_store()
        account = store['accounts'].get(account_id)
        if not account:
            raise ValueError('Account not found')

        for key, value in updates.items():
            account[key] = value
        account['updated_at'] = _utc_now_iso()
        self._save_store(store)


_user_store: Optional[UserStore] = None


def get_user_store() -> UserStore:
    global _user_store
    if _user_store is None:
        _user_store = UserStore()
    return _user_store
