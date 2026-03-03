# Nostr Authentication Migration - Summary

## Overview

Successfully migrated BTC Map Admin from password-based authentication to Nostr-based authentication with encrypted token storage.

## What Changed

### Authentication Flow
**Before**: Single shared password stored in client cookie
**After**: Individual Nostr public keys with NIP-07 browser extension authentication

### Token Storage
**Before**: Password in signed (but readable) session cookie
**After**: Per-user RPC tokens encrypted with Fernet, stored server-side in JSON

### Session Management
**Before**: 30-minute timeout, client-side cookie storage
**After**: No timeout (session until logout), server-side filesystem storage

## New Files Created

1. **`auth.py`** - Nostr authentication blueprint
   - `/auth/challenge` - Issues time-limited nonces
   - `/auth/verify` - Validates signed Nostr events
   - `/auth/logout` - Clears user session

2. **`models.py`** - User model for Flask-Login
   - Loads user data from encrypted JSON store
   - Provides `rpc_token` property with decryption

3. **`user_store.py`** - Encrypted user storage
   - JSON file backend with file locking
   - Fernet symmetric encryption for RPC tokens
   - Automatic key generation with warnings

4. **`templates/profile.html`** - Token management UI
   - Display Nostr public key
   - Add/update/remove RPC token
   - Visual warnings for missing tokens

5. **`.env.example`** - Environment configuration template
   - `SECRET_KEY` - Flask session signing
   - `TOKEN_CIPHER_KEY` - Fernet encryption key

6. **`NOSTR_AUTH_SETUP.md`** - Complete setup and usage guide

## Modified Files

### `app.py`
- Added Flask-Login and Flask-Session initialization
- Registered auth blueprint
- Removed old password-based routes (`/login` POST, `/logout`)
- Updated `rpc_call()` to use `current_user.rpc_token`
- Added `@login_required` decorators to protected routes
- Added `check_token()` middleware for token validation
- New routes: `/profile`, `/profile/delete-token`

### `templates/login.html`
- Complete redesign for Nostr authentication
- NIP-07 extension integration JavaScript
- Challenge/verify flow implementation
- Fallback instructions for manual authentication
- Progressive status messaging

### `templates/base.html`
- Updated navbar to use `current_user.is_authenticated`
- Added Profile link with badge for missing tokens
- Changed logout link to `auth.logout` route

### `requirements.txt`
- Added `flask-login` - User session management
- Added `cryptography` - Token encryption
- Added `nostr` - Nostr event verification

### `.gitignore`
- Added `users.json` - User data with encrypted tokens
- Added `.env` - Environment secrets

## Security Improvements

1. **No Readable Credentials**: RPC tokens encrypted at rest with Fernet
2. **Challenge-Response Auth**: Time-limited nonces prevent replay attacks
3. **Server-Side Sessions**: Auth data never sent to client
4. **Per-User Tokens**: Individual access control vs shared password
5. **Cryptographic Signatures**: Nostr key pairs for authentication

## Migration Path

### For Administrators
1. Set `TOKEN_CIPHER_KEY` environment variable
2. Install dependencies: `pip install -r requirements.txt`
3. Deploy updated code
4. Users re-authenticate with Nostr on first visit

### For End Users
1. Install Nostr browser extension (Alby, nos2x, etc.)
2. Visit `/login` and click "Sign in with Nostr"
3. Approve signature request in extension
4. Add BTC Map API token in Profile page
5. Start using admin panel

## Breaking Changes

- **Password login removed**: Old sessions invalid
- **Shared authentication removed**: Each user needs individual token
- **Client-side sessions removed**: Requires server-side storage

## Testing Checklist

- [ ] Login flow with Nostr extension
- [ ] Challenge expiry (2 minutes)
- [ ] Profile token save/update/delete
- [ ] RPC calls with encrypted token
- [ ] Session persistence across page reloads
- [ ] Logout functionality
- [ ] Missing token warnings/redirects
- [ ] First login flow (auto-redirect to profile)

## Rollback Plan

If issues arise:
1. Checkout previous commit
2. Redeploy
3. Users continue with password auth

Database/storage impact: `users.json` file created but not used by old code.

## Next Steps

- [ ] Test in staging environment
- [ ] User acceptance testing with Nostr extensions
- [ ] Monitor for decryption errors
- [ ] Document token rotation procedure
- [ ] Consider adding session activity timeout (optional)
