
# Validation Rules and Requirements

## Overview

The application implements comprehensive validation at both client and server levels to ensure data integrity and consistency with BTC Map requirements.

## Area Type Requirements

### Community Areas

#### Required Fields

| Field | Type | Validation Rules |
|-------|------|------------------|
| `name` | text | Non-empty string |
| `type` | select | Must be "community" |
| `url_alias` | text | Non-empty, URL-friendly string |
| `continent` | select | One of: africa, asia, europe, north-america, oceania, south-america |
| `icon:square` | text | Non-empty string |
| `population` | number | Non-negative integer |
| `population:date` | date | YYYY-MM-DD format |
| `geo_json` | object | Valid GeoJSON Polygon/MultiPolygon |

#### Optional Fields

| Field | Type | Validation Rules |
|-------|------|------------------|
| `area_km2` | number | Non-negative decimal (auto-calculated from GeoJSON) |
| `organization` | text | Any non-empty string |
| `language` | text | Any non-empty string |
| `description` | text | Any non-empty string |

#### Contact Fields (All Optional)
| Field | Type | Validation Rules |
|-------|------|------------------|
| `contact:website` | url | Valid URL format |
| `contact:email` | email | Valid email format |
| `contact:phone` | tel | Valid phone number format |
| `contact:twitter` | url | Valid URL format |
| `contact:telegram` | url | Valid URL format |
| `contact:signal` | url | Valid URL format |
| `contact:whatsapp` | url | Valid URL format |
| `contact:discord` | url | Valid URL format |
| `contact:instagram` | url | Valid URL format |
| `contact:youtube` | url | Valid URL format |
| `contact:facebook` | url | Valid URL format |
| `contact:linkedin` | url | Valid URL format |
| `contact:github` | url | Valid URL format |
| `contact:matrix` | url | Valid URL format |
| `contact:geyser` | url | Valid URL format |
| `contact:rss` | url | Valid URL format |
| `contact:meetup` | url | Valid URL format |
| `contact:nostr` | text | Any non-empty string |
| `tips:lightning_address` | text | Any non-empty string |

## Validation Functions

### Server-Side Validation (`app.py`)

#### `validate_general(value, allowed_values=None)`
- Validates against allowed values if provided
- Ensures non-empty strings
- Used for basic text fields

#### `validate_non_negative_number(value, allowed_values=None)`
- Accepts integers, floats, or numeric strings
- Must be >= 0
- Used for `area_km2` field

#### `validate_non_negative_integer(value, allowed_values=None)`
- Accepts integers or integer strings
- Must be >= 0
- Used for `population` field

#### `validate_date(value, allowed_values=None)`
- Must match YYYY-MM-DD format
- Uses `datetime.strptime` for validation
- Used for `population:date` field

#### `validate_url(value, allowed_values=None)`
- Uses `urllib.parse.urlparse`
- Requires valid scheme and netloc
- Used for all contact URL fields

#### `validate_email(value, allowed_values=None)`
- Regex pattern: `^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$`
- Standard email format validation

#### `validate_phone(value, allowed_values=None)`
- Regex pattern: `^\+?1?\d{9,15}$`
- Allows optional country code
- 9-15 digits total

#### `validate_geo_json(value)`
- Accepts string or object input
- Validates JSON structure
- Uses Shapely for geometry validation
- Only allows Polygon and MultiPolygon types
- Applies `geojson_rewind` for correct orientation
- Returns rewound GeoJSON object

#### `validate_allowed_values(value, allowed_values)`
- Case-insensitive matching against allowed list
- Used for select/dropdown fields

### Client-Side Validation (`validation.js`)

#### Key Validation
- Checks for duplicate keys
- Validates custom key format
- Ensures required fields are present

#### Value Validation
- Real-time feedback on input
- Type-specific validation (numbers, URLs, emails)
- Visual feedback with Bootstrap validation classes

#### GeoJSON Validation
- JSON syntax validation
- Geometry type checking
- Interactive map preview
- Error highlighting and messages

## Area Calculation

When a valid GeoJSON is provided:
1. Geometry is converted using Shapely
2. Projected to Albers Equal Area for accurate measurement
3. Area calculated in square meters
4. Converted to square kilometers
5. Rounded to 2 decimal places
6. Automatically set as `area_km2` tag

## Validation Workflow

### Adding New Areas
1. Client-side validation on form submission
2. Server-side validation of all fields
3. GeoJSON geometry validation and rewinding
4. Area calculation from geometry
5. RPC call to backend with validated data

### Updating Existing Areas
1. Field-specific validation based on type
2. Special handling for GeoJSON updates
3. Automatic area recalculation for geometry changes
4. Individual tag updates via RPC

### Error Handling
- Validation errors prevent form submission
- Clear error messages displayed to user
- Server errors returned with descriptive messages
- Client provides immediate feedback for invalid input

## Custom Field Support

Users can add custom fields beyond the predefined schema:
- Custom key validation (no duplicates, valid format)
- Value validation based on inferred type
- Full CRUD operations on custom tags
- Removal restrictions for required fields

## Security Considerations

- All user input is validated on both client and server
- SQL injection prevention through proper data handling
- XSS prevention through template escaping
- Input sanitization for all text fields
- Geometry validation prevents malicious GeoJSON
