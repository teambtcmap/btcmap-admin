
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

1. Run the application: `python3 main.py`
2. Access the interface at `http://localhost:5000`
3. Login with your credentials
4. Start managing areas!

## Project Structure

- `/app.py` - Main Flask application with all routes and logic
- `/templates/` - Jinja2 templates for the web interface
- `/static/` - CSS, JavaScript, and other static assets
- `/main.py` - Application entry point

For detailed information, see the additional documentation files in this repository.
