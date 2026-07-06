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
- **Session Management**: Flask-Login with server-side filesystem sessions
- **Area Linting**: Automated linting rules for area data quality

## Project Structure

```
├── app.py            # Flask application (routes, validation, RPC)
├── auth.py           # Nostr authentication blueprint
├── main.py           # Application entry point
├── linting.py        # Area linting system and cache
├── models.py         # User model for Flask-Login
├── nostr_utils.py    # NIP-01 & NIP-98 event verification
├── user_store.py     # Encrypted JSON user storage
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
├── flask_session/    # Server-side session storage (auto-generated)
└── users.json        # Encrypted user data (auto-generated)
```

## API Integration

- **Base URL**: `https://api.btcmap.org`
- **Protocol**: JSON-RPC 2.0
- **Auth**: Per-user RPC token via Bearer header
- **Timeout**: 20 seconds per request

### RPC Methods

| Method | Description |
|--------|-------------|
| `search` | Search areas by query |
| `get_area` | Retrieve area details |
| `add_area` | Create new area |
| `set_area_tag` | Update/add area tag |
| `remove_area_tag` | Remove area tag |
| `remove_area` | Delete area |

## Authentication

Uses NIP-98 HTTP Auth with Nostr browser extensions (Alby, nos2x, etc.):

1. User signs a kind 27235 event via `window.nostr.signEvent()`
2. Server validates event (signature, timestamp within 60s, URL/method binding)
3. User's RPC token is stored encrypted at rest with Fernet

### Auth Endpoints

- `GET /login` - Login page
- `POST /auth/nostr/login` - NIP-98 Nostr login
- `POST /auth/btcmap/login` - Login with BTC Map credentials
- `GET /auth/logout` - Logout

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

Core: flask, flask-session, flask-login, requests, geojson-rewind, shapely, pyproj, cryptography, nostr-sdk
