"""Nostr utilities using nostr-sdk for signature verification.

Implements NIP-98 HTTP Auth validation with full cryptographic verification
via the rust-nostr library.
"""

import json
import time
from typing import Tuple
from nostr_sdk import Event, Kind


def verify_nip98_event(event_data: dict, url: str, method: str, 
                       max_age_seconds: int = 60) -> Tuple[bool, str]:
    """Verify NIP-98 HTTP Auth event using nostr-sdk.
    
    The Event.from_json() method automatically performs:
    - Event ID computation and verification (SHA256)
    - Schnorr signature verification (secp256k1)
    
    This function adds NIP-98 specific validations:
    - Kind must be 27235
    - Timestamp within acceptable window
    - URL tag matches request URL
    - Method tag matches HTTP method
    - Content is empty
    
    Args:
        event_data: The Nostr event dict
        url: The absolute URL being accessed
        method: The HTTP method (GET, POST, etc.)
        max_age_seconds: Maximum age of the event in seconds
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        # Deserialize and verify event (ID + signature verification happens here)
        event = Event.from_json(json.dumps(event_data))
        
        # Check kind is 27235 (NIP-98)
        if event.kind().as_u16() != 27235:
            return False, f"Invalid kind: expected 27235, got {event.kind().as_u16()}"
        
        # Check timestamp (within max_age_seconds window)
        created_at = event.created_at().as_secs()
        now = int(time.time())
        age = abs(now - created_at)
        
        if age > max_age_seconds:
            return False, f"Event timestamp outside valid window ({max_age_seconds}s): age={age}s"
        
        # Extract tags into a dict
        tags = event.tags().to_vec()  # Convert Tags object to list
        tag_dict = {}
        for tag in tags:
            tag_vec = tag.as_vec()
            if len(tag_vec) >= 2:
                tag_dict[tag_vec[0]] = tag_vec[1]
        
        # Verify URL tag
        if 'u' not in tag_dict:
            return False, "Missing 'u' (URL) tag"
        if tag_dict['u'] != url:
            return False, f"URL mismatch: expected {url}, got {tag_dict['u']}"
        
        # Verify method tag
        if 'method' not in tag_dict:
            return False, "Missing 'method' tag"
        if tag_dict['method'].upper() != method.upper():
            return False, f"Method mismatch: expected {method}, got {tag_dict['method']}"
        
        # Content should be empty for NIP-98
        if event.content() != '':
            return False, "Content should be empty for NIP-98 events"
        
        return True, ""
        
    except Exception as e:
        return False, f"Event verification failed: {str(e)}"


def get_event_pubkey(event: Event) -> str:
    """Get the public key from an event in hex format.
    
    Args:
        event: The nostr-sdk Event object
        
    Returns:
        Public key as hex string
    """
    return event.author().to_hex()
