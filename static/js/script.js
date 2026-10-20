/**
 * Centralized API fetch wrapper that handles session expiration gracefully.
 * When the session expires, shows a toast notification and redirects to login.
 * 
 * @param {string} url - The URL to fetch
 * @param {Object} options - Fetch options (method, headers, body, etc.)
 * @returns {Promise<Response>} - The fetch response
 * @throws {Error} - Throws an error if session expired (after redirect initiated)
 */
async function apiFetch(url, options = {}) {
    // Every authenticated call carries the Bearer token the browser holds.
    // The token cookie is only transport for page navigations.
    const token = localStorage.getItem('btcmap_token');
    const config = { ...options };
    if (token) {
        config.headers = { ...(options.headers || {}), 'Authorization': `Bearer ${token}` };
    }

    let response;
    try {
        response = await fetch(url, config);
    } catch (networkError) {
        // fetch() only rejects for network-level failures; say so in words the
        // user can act on instead of "Failed to fetch".
        throw new Error('Network error — the server could not be reached. Please try again.');
    }
    
    // Check for 401 status (session expired)
    if (response.status === 401) {
        try {
            const data = await response.clone().json();
            if (data.session_expired) {
                localStorage.removeItem('btcmap_token');
                showToast('Session Expired', 'Your session has expired. Redirecting to login...', 'warning');
                setTimeout(() => {
                    window.location.href = '/login?next=' + encodeURIComponent(window.location.href);
                }, 1500);
                throw new Error('Session expired');
            }
        } catch (e) {
            // If we can't parse JSON or it's our own error, still handle as session expired
            if (e.message === 'Session expired') {
                throw e;
            }
            // For other parse errors, check if we got redirected to login page
            const text = await response.clone().text();
            if (text.includes('Login') || response.url.includes('/login')) {
                localStorage.removeItem('btcmap_token');
                showToast('Session Expired', 'Your session has expired. Redirecting to login...', 'warning');
                setTimeout(() => {
                    window.location.href = '/login?next=' + encodeURIComponent(window.location.href);
                }, 1500);
                throw new Error('Session expired');
            }
        }
    }
    
    // Also check if we were redirected to login page (for cases where 401 isn't returned)
    if (response.redirected && response.url.includes('/login')) {
        localStorage.removeItem('btcmap_token');
        showToast('Session Expired', 'Your session has expired. Redirecting to login...', 'warning');
        setTimeout(() => {
            window.location.href = '/login?next=' + encodeURIComponent(window.location.href);
        }, 1500);
        throw new Error('Session expired');
    }
    
    return response;
}

/**
 * Pull a human-readable message out of an error response body.
 *
 * Server routes answer with `{"error": "<message>"}`; older routes and the
 * API itself may nest it as `{"error": {"code", "message", "data"}}` where the
 * informative text sits in `data` and `message` is the generic "Server error".
 * Every caller gets one string either way.
 *
 * @param {*} body - Parsed JSON response body
 * @param {string} fallback - Message when the body carries nothing useful
 * @returns {string}
 */
function errorText(body, fallback = 'Request failed') {
    if (!body) return fallback;

    let error = body.error ?? body.message ?? body;
    if (typeof error === 'string') {
        return error.trim() || fallback;
    }
    if (typeof error === 'object') {
        const data = error.data;
        if (typeof data === 'string' && data.trim()) return data.trim();
        if (data && typeof data === 'object' && typeof data.message === 'string' && data.message.trim()) {
            return data.message.trim();
        }
        if (typeof error.message === 'string' && error.message.trim()
                && error.message !== 'Server error') {
            return error.message.trim();
        }
        if (typeof error.message === 'string' && error.message.trim()) {
            return error.message.trim();
        }
    }
    return fallback;
}

function editTag(areaId, tagName, tagValue) {
    const newValue = prompt(`Edit ${tagName}:`, tagValue);
    if (newValue !== null && newValue !== tagValue) {
        setAreaTag(areaId, tagName, newValue);
    }
}

function addTag(areaId) {
    const tagName = prompt("Enter tag name:");
    if (tagName) {
        const tagValue = prompt("Enter tag value:");
        if (tagValue) {
            setAreaTag(areaId, tagName, tagValue);
        }
    }
}

function setAreaTag(areaId, tagName, tagValue) {
    apiFetch('/api/set_area_tag', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ id: areaId, name: tagName, value: tagValue }),
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            showToast('Error', errorText(data, 'Failed to update tag'), 'error');
        } else {
            location.reload();
        }
    })
    .catch(error => {
        if (error.message !== 'Session expired') {
            showToast('Error', error.message || 'Failed to update tag', 'error');
        }
    });
}

function removeTag(areaId, tagName) {
    apiFetch('/api/remove_area_tag', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ id: areaId, tag: tagName }),
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            showToast('Error', errorText(data, 'Failed to remove tag'), 'error');
        } else {
            showToast('Success', 'Tag removed successfully', 'success');
            setTimeout(() => location.reload(), 1000);
        }
    })
    .catch(error => {
        if (error.message !== 'Session expired') {
            showToast('Error', error.message || 'Failed to remove tag', 'error');
        }
    });
}

function removeArea(areaId) {
    apiFetch('/api/remove_area', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ id: areaId }),
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            showToast('Error', errorText(data, 'Failed to remove area'), 'error');
        } else {
            showToast('Success', 'Area removed successfully', 'success');
            setTimeout(() => window.location.href = '/select_area', 1500);
        }
    })
    .catch(error => {
        if (error.message !== 'Session expired') {
            showToast('Error', error.message || 'Failed to remove area', 'error');
        }
    });
}
