// Common validation functions
function validateKey(key, existingKeys) {
    key = key ? key.trim() : '';
    if (!key) {
        return { isValid: false, message: 'Key cannot be empty' };
    }
    if (existingKeys && existingKeys.includes(key)) {
        return { isValid: false, message: 'Key already exists' };
    }
    if (!/^[a-zA-Z][a-zA-Z0-9_:]*$/.test(key)) {
        return { isValid: false, message: 'Key must start with a letter and contain only letters, numbers, underscores, and colons' };
    }
    return { isValid: true };
}

function validateNumericValue(value, type) {
    if (!value || value.trim() === '') {
        return { isValid: false, message: 'Value cannot be empty' };
    }

    if (type === 'integer') {
        const num = parseInt(value, 10);
        if (isNaN(num) || !Number.isInteger(parseFloat(value))) {
            return { isValid: false, message: 'Value must be a valid integer' };
        }
        if (num < 0) {
            return { isValid: false, message: 'Value must be non-negative' };
        }
        return { isValid: true, value: num };
    } else {
        const num = parseFloat(value);
        if (isNaN(num)) {
            return { isValid: false, message: 'Value must be a valid number' };
        }
        if (num < 0) {
            return { isValid: false, message: 'Value must be non-negative' };
        }
        return { isValid: true, value: num };
    }
}

function validateValue(value, requirements) {
    if (!value || value.trim() === '') {
        return { isValid: false, message: 'Value cannot be empty' };
    }

    if (requirements) {
        if (requirements.type === 'integer' || requirements.key === 'population') {
            return validateNumericValue(value, 'integer');
        } else if (requirements.type === 'number' || requirements.key === 'area_km2') {
            return validateNumericValue(value, 'number');
        } else if (requirements.allowed_values) {
            if (!requirements.allowed_values.includes(value)) {
                return { isValid: false, message: `Value must be one of: ${requirements.allowed_values.join(', ')}` };
            }
        }
    }

    return { isValid: true, value: value.trim() };
}
