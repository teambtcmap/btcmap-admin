"""User models for Flask-Login integration."""

from datetime import datetime
from flask_login import UserMixin
from user_store import get_user_store


class User(UserMixin):
    """User model for Flask-Login.
    
    Wraps user data from the JSON store.
    """
    
    def __init__(self, pubkey: str):
        """Initialize user with pubkey.
        
        Args:
            pubkey: Nostr public key (hex format)
        """
        self.pubkey = pubkey
        self._data = None
    
    def get_id(self):
        """Return the pubkey as the user ID."""
        return self.pubkey
    
    @property
    def data(self):
        """Lazy load user data from store."""
        if self._data is None:
            store = get_user_store()
            self._data = store.get_user(self.pubkey) or {}
        return self._data
    
    @property
    def rpc_token(self):
        """Get the decrypted RPC token."""
        return self.data.get('rpc_token')
    
    @property
    def has_rpc_token(self):
        """Check if user has an RPC token set."""
        return bool(self.rpc_token)
    
    @property
    def last_login(self):
        """Get last login timestamp formatted for humans."""
        timestamp = self.data.get('last_login')
        if not timestamp:
            return None
        try:
            # Parse ISO format and convert to human-readable
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            return dt.strftime('%B %d, %Y at %I:%M %p UTC')
        except (ValueError, AttributeError):
            return timestamp
    
    def update_token(self, token: str):
        """Update the user's RPC token.
        
        Args:
            token: The new RPC token
        """
        store = get_user_store()
        user_data = self.data.copy()
        user_data['pubkey'] = self.pubkey
        user_data['rpc_token'] = token
        store.save_user(self.pubkey, user_data)
        # Invalidate cached data
        self._data = None
    
    @staticmethod
    def load_user(pubkey: str):
        """Load a user by pubkey (for Flask-Login user_loader).
        
        Args:
            pubkey: Nostr public key (hex format)
            
        Returns:
            User instance if found, None otherwise
        """
        store = get_user_store()
        user_data = store.get_user(pubkey)
        
        if user_data:
            return User(pubkey)
        
        return None
