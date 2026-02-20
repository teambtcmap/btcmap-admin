# Nostr Authentication Setup Guide

This application uses **NIP-98 HTTP Auth** for Nostr-based authentication instead of password-based auth.

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Generate a TOKEN_CIPHER_KEY:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Add the generated key to your `.env` file.

### 3. Run the Application

```bash
python app.py
```

## User Workflow

### For End Users

1. **Install a Nostr Browser Extension**
   - [Alby](https://getalby.com) - Recommended
   - [nos2x](https://github.com/fiatjaf/nos2x)
   - Any NIP-07 compatible extension

2. **Login Process**
   - Visit `/login`
   - Click "Sign in with Nostr"
   - Approve the signature request in your Nostr extension
   - On first login, you'll be redirected to the profile page

3. **Add BTC Map API Token**
   - Go to Profile (nav bar or automatic redirect on first login)
   - Enter your BTC Map API token (npub or hex format)
   - Token is encrypted before storage
   - Save

4. **Start Using the Admin Panel**
   - All RPC calls now use your encrypted token
   - Token is decrypted on-demand for each API request

## Technical Details

### Architecture

- **Authentication**: NIP-98 HTTP Auth with NIP-07 browser extensions
- **Session Management**: Flask-Login with server-side filesystem sessions
- **Token Storage**: Encrypted JSON file (`users.json`) with Fernet symmetric encryption
- **User Identification**: Nostr public key (hex format)
- **Event Verification**: NIP-01 event ID and signature validation

### Security Features

1. **NIP-98 Compliance**: Events must match exact URL, method, and be within 60-second time window
2. **Event Verification**: ID computed from serialized event data, signature validated
3. **Replay Protection**: Timestamp validation prevents replay attacks
4. **Token Encryption**: All RPC tokens encrypted at rest with Fernet
5. **Session Security**: HttpOnly, Secure, SameSite=Lax cookies
6. **No Timeout**: Sessions persist until explicit logout (configurable if needed)

### File Structure

```
/
├── app.py                  # Main Flask application
├── auth.py                 # NIP-98 authentication blueprint
├── models.py               # User model for Flask-Login
├── user_store.py           # Encrypted JSON user storage
├── nostr_utils.py          # NIP-01 & NIP-98 verification
├── users.json              # User data (auto-created, encrypted tokens)
├── flask_session/          # Server-side session storage (auto-created)
└── templates/
    ├── login.html          # NIP-98 Nostr login page
    └── profile.html        # Token management page
```

### API Endpoints

#### Authentication
- `GET /login` - NIP-98 Nostr login page
- `GET /auth/login-url` - Get URL and method for NIP-98 signing
- `POST /auth/verify` - Verify NIP-98 signed event
- `GET /auth/logout` - Logout current user

#### Profile
- `GET /profile` - View/edit profile and RPC token
- `POST /profile` - Update RPC token
- `POST /profile/delete-token` - Remove RPC token

## Migration from Password Auth

The old password-based authentication has been completely removed:
- Session storage no longer uses client-side cookies for auth data
- All routes now require Nostr login via `@login_required`
- RPC calls use per-user encrypted tokens instead of shared password

## Troubleshooting

### "No Nostr extension detected"
Install Alby or another NIP-07 extension and refresh the page.

### "Event timestamp outside valid window"
NIP-98 events must be signed within 60 seconds. Try again.

### "RPC token not set"
Go to Profile and add your BTC Map API token.

### "Failed to decrypt token"
Token encryption key may have changed. Contact admin to reset your token.

## Development Notes

### Running Tests
```bash
# Manual testing with Nostr extension
python app.py
# Visit http://localhost:5000
```

### Generating Test Users
Users are created automatically on first Nostr login. No seed data needed.

### Rotating Encryption Keys
If `TOKEN_CIPHER_KEY` changes, existing tokens cannot be decrypted. Users must re-enter tokens.
