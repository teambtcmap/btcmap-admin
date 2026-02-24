# AGENTS.md - BTC Map Admin Development Guide

## Overview

This is a Flask-based web application for managing areas in the BTC Map ecosystem. It communicates with the BTC Map API via JSON-RPC and provides an administrative interface for creating, editing, and validating geographical areas.

## Project Structure

```
/Users/user/data/src/btc/btcmap-admin/
├── app.py              # Main Flask application (routes, validation, RPC)
├── main.py             # Application entry point
├── linting.py          # Area linting system and cache
├── pyproject.toml      # Python dependencies (uv)
├── static/             # CSS, JavaScript assets
│   ├── css/
│   └── js/
├── templates/          # Jinja2 templates
│   ├── base.html
│   ├── login.html
│   ├── select_area.html
│   ├── show_area.html
│   ├── add_area.html
│   ├── error.html
│   ├── maintenance.html
│   └── components/
└── flask_session/     # Session storage (auto-generated)
```

## Commands

### Running the Application

```bash
# Development
python3 main.py

# Or with debug mode
FLASK_DEBUG=1 python3 main.py

# Using the run script (requires .venv)
./run.sh

# Production (gunicorn)
gunicorn app:app
```

### Dependencies

```bash
# Create virtual environment (if not exists)
uv venv

# Activate and install dependencies with uv
source .venv/bin/activate
uv sync

# Or pip
pip install -r requirements.txt  # if generated
```

### No Test Framework

This project currently has **no tests**. If adding tests:

```bash
# Recommended: add pytest
uv add pytest

# Run all tests
pytest

# Run single test file
pytest tests/test_linting.py

# Run single test function
pytest tests/test_linting.py::test_lint_area
```

### Linting/Formatting

Python linting with Ruff:

```bash
# Install dependencies
uv sync --dev

# Run linting
uv run ruff check .

# Auto-fix issues
uv run ruff check . --fix
```

Frontend linting with Biome (JavaScript/CSS):

```bash
npm install
npm run lint
npm run format
```

## Code Style Guidelines

### General Principles

- Follow existing patterns in the codebase
- Keep functions focused and concise
- Use meaningful variable names
- Add docstrings for complex functions

### Python Style

- **Naming**: `snake_case` for functions/variables, `PascalCase` for classes
- **Type Hints**: Use where beneficial (especially in `linting.py`)
- **Imports**: Organize in groups: stdlib, third-party, local
  ```python
  import os
  from flask import Flask, render_template, request
  from geojson_rewind import rewind
  from linting import lint_area_dict, lint_cache
  ```

### Flask Conventions

- Route handlers in `app.py` with clear endpoint names
- Use `app.logger` for logging (not print statements)
- Return proper HTTP status codes (200, 400, 404, etc.)
- Use `jsonify()` for JSON responses

### Error Handling

- Return error responses as JSON with descriptive messages
- Use try/except blocks for external calls (RPC, HTTP requests)
- Log errors with context for debugging

### Validation Patterns

See `VALIDATION_RULES.md` for validation function details:

- Validation functions return `(is_valid: bool, error_message: str | None)`
- GeoJSON validation uses Shapely for geometry checking
- Client-side validation in `static/js/validation.js` mirrors server logic

### RPC Communication

- All RPC calls go through `rpc_call(method, params)` in `app.py`
- Uses Bearer token auth from session
- Timeout: 20 seconds
- Endpoint: `https://api.btcmap.org/rpc`

### Linting System

The `linting.py` module provides:

- `LintRule` dataclass for rule definitions
- `LintResult` dataclass for issue reporting
- `LintCache` class for global area linting
- Auto-fix functions in `FIX_ACTIONS` dict

When adding new lint rules:

1. Add rule to `LINT_RULES` dict
2. Create check function returning `LintResult | None`
3. Add to `lint_area()` check list

### Templates

- Jinja2 templates in `/templates`
- Use Bootstrap 5 classes for styling
- Leaflet.js for maps (CDN loaded)

### JavaScript

- Vanilla JS (no frameworks)
- Follow existing patterns in `static/js/script.js`
- Validation functions in `static/js/validation.js`

## Development Workflow

1. Make changes to `app.py` or `linting.py`
2. Test manually: `python3 main.py` and open `http://localhost:5000`
3. Check validation rules in `VALIDATION_RULES.md`
4. Review architecture in `ARCHITECTURE.md`

## API Integration

- **Base URL**: `https://api.btcmap.org`
- **Protocol**: JSON-RPC 2.0
- **Auth**: Session password as Bearer token
- **Timeout**: 20 seconds per request

## Security Notes

- All routes except `/login`, `/health`, `/static` require auth
- Session expires after 30 minutes
- Input validation on all user data
- GeoJSON validated server-side before RPC calls
