# BTC Map Area Administration Tool

A Flask-based web application for managing areas in the BTC Map ecosystem. Provides an administrative interface for creating, editing, and validating geographical areas with metadata.

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager

```bash
pip install uv
```

### Setup

```bash
uv venv
source .venv/bin/activate
uv sync
```

### Run

```bash
python3 main.py
```

Or via run script: `./run.sh`

Production (gunicorn):

```bash
gunicorn app:app
```

## Key Features

- **Interactive Maps**: Leaflet-based map visualization with GeoJSON editing
- **Real-time Validation**: Client and server-side validation for area data
- **RPC Integration**: JSON-RPC communication with BTC Map API
- **Nostr Authentication**: NIP-98 HTTP Auth via NIP-07 browser extensions
- **Session Management**: signed-cookie session holding display identity only; the BTC Map API is the account authority and keeps all accounts and tokens
- **Area Linting**: Automated linting rules for area data quality

## Project Structure

```
├── app.py            # Flask application (routes, validation, RPC)
├── admin_session.py  # Session helpers: token transport, display identity
├── auth.py           # Nostr authentication blueprint
├── rpc_errors.py     # JSON-RPC error → user-facing message
├── main.py           # Application entry point
├── linting.py        # Area linting system and cache
├── pyproject.toml    # Dependencies (uv)
├── static/
│   ├── css/
│   └── js/
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── select_area.html
│   ├── show_area.html
│   ├── add_area.html
│   ├── profile.html
│   ├── error.html
│   ├── maintenance.html
│   └── components/
└── run.sh
```

## API Integration

- **Base URL**: `https://api.btcmap.org`
- **Protocol**: JSON-RPC 2.0
- **Auth**: Per-user RPC token via Bearer header
- **Timeout**: 20 seconds per request

### RPC Methods

| Method | Description |
|--------|-------------|
| `signin` | Exchange credentials for an API key (Bearer token) |
| `search` | Search areas by query |
| `get_area` | Retrieve area details |
| `add_area` | Create new area |
| `set_area_tag` | Update/add area tag |
| `set_area_image` | Attach an image to an area |
| `remove_area_tag` | Remove area tag |
| `remove_area` | Delete area |

## Authentication

Sign-in happens in the browser against the BTC Map API; this app stores no
accounts and no tokens. Two credentials are accepted:

- **BTC Map username + password** — the browser mints a Bearer token with
  `POST {API_BASE_URL}/v4/users/{username}/tokens`.
- **Nostr (NIP-98)** — the browser signs a kind 27235 event for
  `{API_BASE_URL}/v4/auth/nostr` and exchanges it for a Bearer token. The key
  must already be linked to a BTC Map account: the API auto-creates a
  role-`user` account for an unknown npub, and this app refuses those at
  sign-in. Three signer transports are offered side by side in one dialog
  (opened from the Nostr button), all implemented in
  `static/js/nostr-signer.js`:

  - a NIP-07 browser extension (Alby, nos2x) signing in the page;
  - a NIP-46 signer app via a pasted `bunker://` URI or NIP-05 address;
  - a NIP-46 signer app paired by QR: the page shows a `nostrconnect://` URI
    to scan (Amber, Opal, nsec.app), with the URI also copyable and linkable
    for signers on the same device.

  A completed signer-app pairing is kept in `localStorage` (`btcmap_bunker`)
  so the next visit is one click; **Forget signer** removes it. That record is
  a credential at rest — it lets this browser ask the signer for signatures,
  not sign without it.

  nostr-tools is loaded from jsDelivr on demand, so a CDN failure only
  disables the signer-app transports; the extension path keeps working.

The token is kept in `localStorage`, sent as `Authorization: Bearer` on every
`/api/*` call, and mirrored into a `btcmap_token` cookie so server-rendered
pages can authenticate (a navigation cannot carry a header). The Flask session
cookie holds display-only identity and is never used for authorisation.

`API_BASE_URL` must be absolute and identical to the API's own
`BTCMAP_API_BASE_URL`, because the NIP-98 `u` tag signs that exact origin.

### Auth Endpoints

- `GET /login` - Login page (credentials, then Nostr)
- `POST /auth/session` - Validate a minted Bearer token and start the session
- `POST /auth/logout` - End the session

## Roles and area scope

The API decides what an account may edit; this app only reflects that decision.

- Sign-in requires one of `admin`, `root` or `area_manager`
  (`admin_session.AREA_EDIT_ROLES`). Everything else is refused with an
  explanation instead of failing later on an RPC call.
- `area_manager` accounts carry a **geofence**: the list of area ids they may
  edit (`GET /v4/users/me` → `geofence`). An empty geofence means unrestricted;
  the API applies a non-empty one to every role, so the app reads the scope
  from the account and never from the role name.
- Reading is unrestricted: any area opens. Editing outside the geofence is
  refused by the API (`Area <id> is outside your geofence (allowed areas: …)`),
  so the area page hides its editing controls and says why, search results mark
  such areas **Read-only**, and Maintenance disables its lint fixes for them.

### Error messages

The API answers a failed RPC with HTTP 200 and a JSON-RPC error whose
`message` is usually the generic `Server error` and whose `data` carries the
real text. `rpc_errors.rpc_error_message()` flattens both shapes into one line;
every route returns `{"error": "<message>"}` and every page shows it through
`errorText()` in `static/js/script.js`. A refusal such as an out-of-geofence
edit or a missing permission therefore reaches the user verbatim, and a
`get_area` refusal renders as an explanation rather than "Area not found".

## Area Type Requirements

### Community Areas (Required Fields)

| Field | Type | Notes |
|-------|------|-------|
| `name` | text | Non-empty |
| `type` | select | Must be "community" |
| `url_alias` | text | URL-friendly identifier |
| `continent` | select | africa, asia, europe, north-america, oceania, south-america |
| `icon:square` | text | Icon identifier |
| `population` | number | Non-negative integer |
| `population:date` | date | YYYY-MM-DD format |
| `geo_json` | GeoJSON | Valid Polygon/MultiPolygon |

### Optional Fields

Contact fields (`contact:website`, `contact:email`, `contact:phone`, etc.), `area_km2` (auto-calculated), `organization`, `language`, `description`, `tips:lightning_address`.

## Validation

Validation functions in `app.py` return `(is_valid, error_message)`. GeoJSON validation uses Shapely for geometry checking and `geojson-rewind` for correct orientation. Client-side validation in `static/js/validation.js` mirrors server logic.

## Linting System (`linting.py`)

- `LintRule` / `LintResult` dataclasses for rule definitions and issue reporting
- `LintCache` for global area linting
- Auto-fix functions in `FIX_ACTIONS` dict
- Add new rules: define in `LINT_RULES`, create check function, add to `lint_area()` check list

## Code Style

- Python: `snake_case` for functions/variables, `PascalCase` for classes, type hints where beneficial
- Flask: Clear endpoint names, `app.logger` for logging, proper HTTP status codes
- JS: Vanilla JS, follow existing patterns in `static/js/`
- Templates: Jinja2 with Bootstrap 5 classes, Leaflet.js maps via CDN

## Dependencies

Core: flask, requests, geojson-rewind, shapely, pyproj; gunicorn for serving
