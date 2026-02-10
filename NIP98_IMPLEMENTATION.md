# NIP-98 HTTP Auth Implementation

## Overview

The BTC Map Admin now uses **NIP-98 HTTP Authentication** for secure, standardized Nostr-based login.

## What is NIP-98?

NIP-98 defines an ephemeral event (kind 27235) used to authorize HTTP requests using Nostr events. It's the standard way for HTTP services built for Nostr to authenticate users.

## Implementation Details

### Event Structure

Users sign a kind 27235 event with:
- `kind`: 27235 (NIP-98 HTTP Auth)
- `content`: Empty string
- `tags`:
  - `["u", "<absolute-url>"]` - The exact URL being accessed
  - `["method", "<http-method>"]` - The HTTP method (POST)
- `created_at`: Current Unix timestamp
- `pubkey`: User's Nostr public key
- `sig`: Schnorr signature

### Verification Process

Server validates the event by checking:

1. ✅ **Event ID**: SHA256 hash of serialized event data matches `id` field
2. ✅ **Signature Format**: Valid 128-character hex Schnorr signature
3. ✅ **Kind**: Must be exactly 27235
4. ✅ **Timestamp**: Within 60-second window (prevents replay attacks)
5. ✅ **URL Match**: `u` tag exactly matches request URL
6. ✅ **Method Match**: `method` tag matches HTTP method (POST)
7. ✅ **Empty Content**: Content field must be empty per spec

### Code Flow

#### Frontend (login.html)

```javascript
// 1. Get login URL and method
const loginUrlResp = await fetch('/auth/login-url');
const loginUrlData = await loginUrlResp.json();

// 2. Create NIP-98 event
const event = {
    kind: 27235,
    created_at: Math.floor(Date.now() / 1000),
    tags: [
        ['u', loginUrlData.url],
        ['method', loginUrlData.method]
    ],
    content: '',
    pubkey: await window.nostr.getPublicKey()
};

// 3. Sign with NIP-07 extension
const signedEvent = await window.nostr.signEvent(event);

// 4. Submit to server
await fetch('/auth/verify', {
    method: 'POST',
    body: JSON.stringify({ event: signedEvent })
});
```

#### Backend (auth.py)

```python
# 1. Receive signed event
event_data = request.json.get('event')

# 2. Verify NIP-98 compliance
is_valid, error_msg = verify_nip98_event(
    event_data,
    url_for('auth.verify', _external=True),
    'POST',
    max_age_seconds=60
)

# 3. Extract pubkey and create/load user
pubkey = event_data['pubkey']
user = User(pubkey)
login_user(user, remember=True)
```

### Verification Module (nostr_utils.py)

Uses **nostr-sdk** (Rust bindings) for cryptographic verification:
- `Event.from_json()` - Automatically performs full verification:
  - SHA256 event ID computation and validation
  - Schnorr signature verification via secp256k1
  - Raises exception on invalid ID or signature
- `verify_nip98_event()` - NIP-98 specific validation:
  - Kind must be 27235
  - Timestamp within window
  - URL and method tags match
  - Content is empty
- `get_event_pubkey()` - Extract hex pubkey from verified event

## Security Benefits

### vs Password Auth
- ✅ No shared secrets stored on server
- ✅ Cryptographic proof of identity
- ✅ Per-user authorization
- ✅ Browser extension security model

### vs Custom Challenge/Response
- ✅ Standardized (interoperable with other Nostr apps)
- ✅ Timestamp-based replay protection
- ✅ No server-side nonce storage needed
- ✅ Simpler implementation

### Additional Security
- ✅ 60-second time window prevents stale events
- ✅ URL binding prevents auth token reuse
- ✅ Method binding prevents cross-endpoint attacks
- ✅ Empty content prevents content manipulation

## Browser Extension Compatibility

Works with any NIP-07 compatible extension:
- ✅ Alby
- ✅ nos2x  
- ✅ Flamingo
- ✅ Any extension implementing `window.nostr.signEvent()`

## Testing

Test the flow:

1. Open http://localhost:5000/login
2. Click "Sign in with Nostr"
3. Extension prompts for signature of kind 27235 event
4. Server validates event and creates session
5. Redirects to profile or select_area

Verify event in extension:
- Check `kind: 27235`
- Check `tags` contain correct URL and method
- Check `content` is empty
- Check timestamp is recent

## Cryptographic Verification

✅ **Full signature verification implemented** using `nostr-sdk` (rust-nostr Python bindings)

The `nostr-sdk` library provides:
- Native Rust performance for cryptographic operations
- Full secp256k1 Schnorr signature verification
- NIP-01 event ID computation and validation
- Battle-tested implementation used across the Nostr ecosystem

## Future Enhancements

- [ ] Support optional `payload` tag for POST body validation
- [ ] Add Authorization header support (in addition to JSON body)
- [ ] Implement event caching to prevent duplicate verification
- [ ] Add rate limiting per pubkey

## References

- [NIP-98 Specification](https://github.com/nostr-protocol/nips/blob/master/98.md)
- [NIP-01 Event Format](https://github.com/nostr-protocol/nips/blob/master/01.md)
- [NIP-07 Browser Extension](https://github.com/nostr-protocol/nips/blob/master/07.md)
