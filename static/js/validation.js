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
        return { isValid: false, message: `${type === 'integer' ? 'Integer' : 'Number'} value cannot be empty` };
    }

    value = value.toString().trim();
    
    if (type === 'integer') {
        if (!/^\d+$/.test(value)) {
            return { isValid: false, message: 'Value must be a whole number (no decimal points or special characters)' };
        }
        const num = parseInt(value, 10);
        if (num < 0) {
            return { isValid: false, message: 'Value must be a positive number (0 or greater)' };
        }
        if (num > 1000000000) {
            return { isValid: false, message: 'Value is too large (maximum: 1,000,000,000)' };
        }
        return { isValid: true, value: num };
    } else if (type === 'number') {
        if (!/^\d*\.?\d*$/.test(value)) {
            return { isValid: false, message: 'Value must be a valid number (only digits and at most one decimal point)' };
        }
        const num = parseFloat(value);
        if (isNaN(num)) {
            return { isValid: false, message: 'Value must be a valid number' };
        }
        if (num < 0) {
            return { isValid: false, message: 'Value must be a positive number (0 or greater)' };
        }
        if (num > 1000000000) {
            return { isValid: false, message: 'Value is too large (maximum: 1,000,000,000)' };
        }
        // Round to 2 decimal places for floating-point numbers
        return { isValid: true, value: Math.round(num * 100) / 100 };
    }

    return { isValid: true, value: value.trim() };
}

function validateValue(value, requirements) {
    if (!value || value.trim() === '') {
        const fieldType = requirements?.type || 'text';
        return { isValid: false, message: `${fieldType.charAt(0).toUpperCase() + fieldType.slice(1)} value cannot be empty` };
    }

    if (requirements && requirements.type) {
        if (requirements.type === 'integer' || requirements.type === 'number') {
            return validateNumericValue(value, requirements.type);
        } else if (requirements.allowed_values) {
            if (!requirements.allowed_values.includes(value)) {
                return { 
                    isValid: false, 
                    message: `Value must be one of the following: ${requirements.allowed_values.join(', ')}`
                };
            }
        }
    }

    return { isValid: true, value: value.trim() };
}
