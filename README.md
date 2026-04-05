
# BTC Map Area Administration Tool

A Flask-based web application for managing areas in the BTC Map ecosystem. This tool provides an intuitive interface for administrators to create, edit, and manage geographical areas with associated metadata and validation.

## Overview

This application serves as an administrative interface for BTC Map's area management system. It allows authorized users to:

- Search and browse existing areas
- View detailed area information with interactive maps
- Edit area properties and geographical boundaries
- Add new areas with comprehensive validation
- Manage area tags and metadata

## Key Features

- **Interactive Maps**: Leaflet-based map visualization with GeoJSON editing
- **Real-time Validation**: Client and server-side validation for area data
- **RPC Integration**: Seamless communication with BTC Map's API
- **Responsive Design**: Bootstrap-based UI that works on all devices
- **Session Management**: Secure authentication with session handling

## Technology Stack

- **Backend**: Flask (Python)
- **Frontend**: Bootstrap, Leaflet.js, vanilla JavaScript
- **Maps**: OpenStreetMap tiles with Leaflet
- **Data Format**: GeoJSON for geographical boundaries
- **API**: JSON-RPC for backend communication

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager

Install uv if you don't have it:
```bash
pip install uv
# or via Homebrew
brew install uv
```

### Setup

```bash
# Create virtual environment
uv venv

# Activate and install dependencies
source .venv/bin/activate
uv sync
```

### Run the Application

```bash
./run.sh
```

- Access the interface at `http://localhost:5001` (default port 5000 may be blocked by AirPlay Receiver on macOS)
- Login with your BTC Map admin password
- Start managing areas!

### Troubleshooting

**Port 5000 blocked**: If you get "Address already in use", macOS AirPlay Receiver may be using port 5000. Either:
- Disable it in System Settings → General → AirDrop & Handoff → AirPlay Receiver, or
- Edit `run.sh` to use a different port

**"No module named 'flask'"**: Make sure you've run `uv sync` inside the activated virtual environment.

**Credentials**: Use your BTC Map admin account password to log in. If you don't have one, request access from the BTC Map team.

## Project Structure

- `/app.py` - Main Flask application with all routes and logic
- `/templates/` - Jinja2 templates for the web interface
- `/static/` - CSS, JavaScript, and other static assets
- `/main.py` - Application entry point

For detailed information, see the additional documentation files in this repository.
