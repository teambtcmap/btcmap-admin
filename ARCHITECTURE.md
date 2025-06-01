
# Application Architecture

## Overview

The BTC Map Area Administration tool follows a traditional Flask MVC pattern with additional layers for API communication and data validation.

## Application Structure

### Flask Application (`app.py`)

The main application file contains:

- **Route Handlers**: All HTTP endpoints for the web interface
- **API Integration**: RPC communication with BTC Map backend
- **Validation Logic**: Server-side data validation functions
- **Session Management**: Authentication and session handling

### Key Components

#### 1. Authentication Layer
- Session-based authentication using Flask-Session
- Password protection for all routes (except login)
- 30-minute session timeout for security

#### 2. Area Management Routes
- `/` - Home redirect to area selection
- `/select_area` - Search and browse areas
- `/show_area/<id>` - View/edit specific area
- `/add_area` - Create new areas

#### 3. API Endpoints
- `/api/search_areas` - Search functionality
- `/api/set_area_tag` - Update area properties
- `/api/remove_area_tag` - Remove area properties
- `/api/remove_area` - Delete areas

#### 4. RPC Communication
The `rpc_call()` function handles all communication with the BTC Map backend:
- JSON-RPC 2.0 protocol
- Bearer token authentication
- Error handling and timeout management
- Endpoint: `https://api.btcmap.org/rpc`

## Data Flow

1. **User Request** → Flask Route Handler
2. **Authentication Check** → Session validation
3. **Data Processing** → Validation and formatting
4. **Backend Communication** → RPC call to BTC Map API
5. **Response Processing** → Format and return to client
6. **Frontend Update** → JavaScript handles UI updates

## Validation Architecture

### Server-Side Validation
- Type-specific validation functions
- Area type requirements enforcement
- GeoJSON geometry validation
- URL, email, and phone format validation

### Client-Side Validation
- Real-time form validation
- Interactive feedback
- GeoJSON preview and editing
- Map-based geographical validation

## Area Type System

The application supports different area types with specific requirements:

- **Community Areas**: Full metadata with population, contacts, etc.
- **Country Areas**: Basic geographical and political information

Each type has:
- Required fields that must be present
- Optional fields that can be added
- Custom fields for additional metadata
- Type-specific validation rules

## Frontend Architecture

### Templates (`/templates/`)
- `base.html` - Common layout and navigation
- `login.html` - Authentication interface
- `select_area.html` - Area search and selection
- `show_area.html` - Area details and editing
- `add_area.html` - New area creation
- `error.html` - Error handling page

### Static Assets (`/static/`)
- `css/style.css` - Main application styles
- `css/map.css` - Map-specific styling
- `js/script.js` - Main application JavaScript
- `js/validation.js` - Validation utilities

### JavaScript Architecture
- Modular functions for different features
- Event-driven UI updates
- AJAX communication with backend
- Map integration with Leaflet.js
- Real-time validation feedback

## Security Considerations

- Session-based authentication
- CSRF protection through Flask-WTF patterns
- Input validation on both client and server
- Secure RPC communication with bearer tokens
- Timeout handling for all external requests
