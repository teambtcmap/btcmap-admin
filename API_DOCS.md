
# API Documentation

## BTC Map RPC Integration

This application communicates with the BTC Map backend using JSON-RPC 2.0 protocol.

## Authentication

All RPC calls require authentication using a Bearer token:
```
Authorization: Bearer <password>
```

## RPC Endpoint
```
https://api.btcmap.org/rpc
```

## Available RPC Methods

### 1. `search`
Search for areas by query string.

**Parameters:**
```json
{
  "query": "string"
}
```

**Response:**
```json
{
  "result": [
    {
      "id": "string",
      "name": "string", 
      "type": "area"
    }
  ]
}
```

### 2. `get_area`
Retrieve detailed information about a specific area.

**Parameters:**
```json
{
  "id": "string"
}
```

**Response:**
```json
{
  "result": {
    "id": "string",
    "created_at": "ISO8601",
    "updated_at": "ISO8601", 
    "last_sync": "ISO8601",
    "tags": {
      "name": "string",
      "type": "community|country",
      "geo_json": "object",
      "population": "number",
      "area_km2": "number",
      // ... other tags based on area type
    }
  }
}
```

### 3. `add_area`
Create a new area with specified tags.

**Parameters:**
```json
{
  "tags": {
    "name": "string",
    "type": "community|country", 
    "geo_json": "object",
    // ... other required/optional tags
  }
}
```

**Response:**
```json
{
  "result": {
    "id": "string"
  }
}
```

### 4. `set_area_tag`
Update or add a tag to an existing area.

**Parameters:**
```json
{
  "id": "string",
  "name": "string",
  "value": "any"
}
```

**Response:**
```json
{
  "result": true
}
```

### 5. `remove_area_tag`
Remove a tag from an existing area.

**Parameters:**
```json
{
  "id": "string",
  "tag": "string"
}
```

**Response:**
```json
{
  "result": true
}
```

### 6. `remove_area`
Delete an area completely.

**Parameters:**
```json
{
  "id": "string"
}
```

**Response:**
```json
{
  "result": true
}
```

## Data Formats

### GeoJSON Format
All geographical boundaries must be valid GeoJSON Polygon or MultiPolygon:

```json
{
  "type": "Polygon",
  "coordinates": [
    [
      [longitude, latitude],
      [longitude, latitude],
      // ... more coordinates
      [longitude, latitude]  // Close the polygon
    ]
  ]
}
```

### Area Tags by Type

#### Community Areas
**Required Tags:**
- `name`: Display name
- `type`: "community"
- `url_alias`: URL-friendly identifier
- `continent`: One of: africa, asia, europe, north-america, oceania, south-america
- `icon:square`: Icon identifier
- `population`: Number of residents
- `population:date`: Date in YYYY-MM-DD format
- `geo_json`: GeoJSON geometry

**Optional Tags:**
- `area_km2`: Area in square kilometers (auto-calculated)
- `organization`: Managing organization
- `language`: Primary language
- Contact information: `contact:twitter`, `contact:website`, etc.
- `tips:lightning_address`: Lightning tips address
- `description`: Area description

#### Country Areas
(Future implementation - requirements TBD)

## Error Handling

All RPC calls may return errors in this format:

```json
{
  "error": {
    "message": "Error description"
  }
}
```

Common error scenarios:
- Authentication failure (invalid token)
- Area not found (invalid ID)
- Validation errors (invalid data)
- Network timeouts
- Server errors

## Rate Limiting

The application implements timeout handling:
- 20-second timeout for all RPC calls
- Automatic retry not implemented
- User feedback on timeout errors

## Development Notes

- All numeric values should be sent as actual numbers, not strings
- GeoJSON should be sent as objects, not stringified JSON
- Dates should be in ISO8601 format
- URLs are validated for proper format
- Email addresses are validated with regex
