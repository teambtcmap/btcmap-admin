"""User storage module with encrypted token support.

Manages user data in a JSON file with encrypted RPC tokens.
"""

import os
import json
import fcntl
from datetime import datetime
from typing import Optional, Dict, Any
from cryptography.fernet import Fernet, InvalidToken


class UserStore:
    """Handles user data persistence with encrypted token storage."""
    
    def __init__(self, storage_path: str = 'users.json', cipher_key: Optional[str] = None):
        """Initialize the user store.
        
        Args:
            storage_path: Path to the JSON storage file
            cipher_key: Base64-encoded Fernet key for token encryption
        """
        self.storage_path = storage_path
        
        # Initialize cipher for token encryption
        if cipher_key:
            self.cipher = Fernet(cipher_key.encode())
        else:
            # Generate a key if none provided (should be set via env var in production)
            key = os.environ.get('TOKEN_CIPHER_KEY')
            if not key:
                # Generate and warn - this is not secure for production
                key = Fernet.generate_key().decode()
                print(f"WARNING: Generated ephemeral cipher key. Set TOKEN_CIPHER_KEY env var for production.")
                print(f"Generated key: {key}")
            self.cipher = Fernet(key.encode())
    
    def _read_store(self) -> Dict[str, Any]:
        """Read the entire user store from disk with file locking."""
        if not os.path.exists(self.storage_path):
            return {}
        
        with open(self.storage_path, 'r') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                data = json.load(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        
        return data
    
    def _write_store(self, data: Dict[str, Any]) -> None:
        """Write the entire user store to disk with file locking."""
        with open(self.storage_path, 'w') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                json.dump(data, f, indent=2)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    
    def _encrypt_token(self, token: str) -> str:
        """Encrypt an RPC token."""
        return self.cipher.encrypt(token.encode()).decode()
    
    def _decrypt_token(self, encrypted_token: str) -> Optional[str]:
        """Decrypt an RPC token. Returns None if decryption fails."""
        try:
            return self.cipher.decrypt(encrypted_token.encode()).decode()
        except (InvalidToken, Exception) as e:
            print(f"Failed to decrypt token: {e}")
            return None
    
    def get_user(self, pubkey: str) -> Optional[Dict[str, Any]]:
        """Get user data by pubkey.
        
        Args:
            pubkey: Nostr public key (hex format)
            
        Returns:
            User dict with decrypted rpc_token, or None if not found
        """
        store = self._read_store()
        user_data = store.get(pubkey)
        
        if not user_data:
            return None
        
        # Decrypt the token if present
        if 'rpc_token_encrypted' in user_data:
            decrypted = self._decrypt_token(user_data['rpc_token_encrypted'])
            user_data['rpc_token'] = decrypted
            # Remove encrypted version from returned dict
            user_data = {k: v for k, v in user_data.items() if k != 'rpc_token_encrypted'}
        
        return user_data
    
    def save_user(self, pubkey: str, user_data: Dict[str, Any]) -> None:
        """Save user data with encrypted token.
        
        Args:
            pubkey: Nostr public key (hex format)
            user_data: User data dict. If 'rpc_token' is present, it will be encrypted
        """
        store = self._read_store()
        
        # Prepare data for storage
        storage_data = user_data.copy()
        
        # Encrypt token if present
        if 'rpc_token' in storage_data and storage_data['rpc_token']:
            encrypted = self._encrypt_token(storage_data['rpc_token'])
            storage_data['rpc_token_encrypted'] = encrypted
            del storage_data['rpc_token']
        
        # Update timestamps
        storage_data['updated_at'] = datetime.utcnow().isoformat() + 'Z'
        if pubkey not in store:
            storage_data['created_at'] = storage_data['updated_at']
        
        store[pubkey] = storage_data
        self._write_store(store)
    
    def delete_user(self, pubkey: str) -> bool:
        """Delete a user from the store.
        
        Args:
            pubkey: Nostr public key (hex format)
            
        Returns:
            True if user was deleted, False if not found
        """
        store = self._read_store()
        
        if pubkey in store:
            del store[pubkey]
            self._write_store(store)
            return True
        
        return False
    
    def list_users(self) -> list[str]:
        """List all user pubkeys in the store."""
        store = self._read_store()
        return list(store.keys())


# Global instance
_user_store: Optional[UserStore] = None


def get_user_store() -> UserStore:
    """Get the global UserStore instance."""
    global _user_store
    if _user_store is None:
        _user_store = UserStore()
    return _user_store
