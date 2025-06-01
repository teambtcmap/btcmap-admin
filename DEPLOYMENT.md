
# Deployment Guide

## Overview

This Flask application is designed to run on Replit and communicate with the BTC Map API for area management functionality.

## Configuration

### Environment Setup

The application is configured to run on Replit with the following settings:

- **Python Version**: 3.11
- **Host**: 0.0.0.0 (accessible to external connections)
- **Port**: 5000 (mapped to external ports 80/443)
- **Debug Mode**: Enabled in development

### Required Dependencies

Core dependencies managed through `pyproject.toml`:
- `flask` - Web framework
- `flask-session` - Session management
- `requests` - HTTP client for RPC calls
- `geojson-rewind` - GeoJSON orientation correction
- `shapely` - Geometric operations
- `pyproj` - Map projections for area calculation

System dependencies (managed by Nix):
- `geos` - Geometry engine for Shapely
- `proj` - Cartographic projections library
- `glibcLocales` - Locale support

## BTC Map API Integration

### API Configuration
- **Base URL**: `https://api.btcmap.org`
- **Protocol**: JSON-RPC 2.0
- **Authentication**: Bearer token (user password)
- **Timeout**: 20 seconds per request

### Authentication Flow
1. User enters password on login page
2. Password stored in Flask session
3. Password used as Bearer token for all RPC calls
4. Session expires after 30 minutes of inactivity

## File Structure

```
/
├── app.py              # Main Flask application
├── main.py             # Application entry point
├── pyproject.toml      # Python dependencies
├── .replit             # Replit configuration
├── static/             # Static assets
│   ├── css/
│   │   ├── style.css   # Main styles
│   │   └── map.css     # Map-specific styles
│   └── js/
│       ├── script.js   # Main JavaScript
│       └── validation.js # Validation utilities
├── templates/          # Jinja2 templates
│   ├── base.html       # Base layout
│   ├── login.html      # Authentication
│   ├── select_area.html # Area search
│   ├── show_area.html  # Area details/editing
│   ├── add_area.html   # New area creation
│   └── error.html      # Error display
└── flask_session/      # Session storage (auto-generated)
```

## Session Management

### Configuration
- **Type**: Filesystem-based sessions
- **Location**: `./flask_session/` directory
- **Lifetime**: 30 minutes
- **Security**: Random 24-byte secret key

### Session Data
- `password`: User's authentication token
- `permanent`: True for extended sessions

## Security Configuration

### Authentication
- All routes protected except `/login` and `/static`
- Automatic redirect to login for unauthenticated users
- Session-based authentication with timeout

### Data Protection
- CSRF protection through proper form handling
- Input validation on all user data
- Secure session configuration
- Bearer token authentication for API calls

## External Dependencies

### Frontend Libraries (CDN)
- **Bootstrap 5.1.3**: UI framework
- **Leaflet 1.7.1**: Interactive maps
- **OpenStreetMap**: Map tiles

### Map Configuration
- **Tile Server**: `https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png`
- **Attribution**: OpenStreetMap contributors
- **Default View**: World view (0,0) at zoom level 2

## Development Setup

### Running Locally on Replit
1. Use the Run button (configured to start Flask server)
2. Application starts on `http://localhost:5000`
3. External access via Replit's port forwarding

### Workflow Configuration
The application uses Replit's workflow system:
- **Primary Workflow**: "Flask Server"
- **Command**: `python3 main.py`
- **Port**: 5000 (auto-forwarded)

## Production Considerations

### Performance
- Flask development server (not production-ready)
- Single-threaded request handling
- File-based session storage

### Scalability Limitations
- In-memory session storage
- No load balancing
- Single instance deployment

### Monitoring
- Flask logging to console
- Request logging enabled
- Error tracking through application logs

## Troubleshooting

### Common Issues

**Authentication Failures**
- Check password/token validity
- Verify API endpoint accessibility
- Review session timeout settings

**Map Display Issues**
- Verify Leaflet CDN accessibility
- Check GeoJSON format validity
- Ensure OpenStreetMap tile availability

**RPC Communication Errors**
- Check internet connectivity
- Verify API endpoint status
- Review timeout settings (20s default)

### Debug Mode

Enable debug logging by checking Flask console output:
- Request/response logging
- RPC call debugging
- GeoJSON validation details
- Error stack traces

## Backup and Recovery

### Session Data
- Sessions stored in `./flask_session/`
- Automatic cleanup of expired sessions
- No persistent user data stored locally

### Configuration Backup
- All configuration in version-controlled files
- No database or external storage
- Stateless application design
