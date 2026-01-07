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
    const response = await fetch(url, options);
    
    // Check for 401 status (session expired)
    if (response.status === 401) {
        try {
            const data = await response.clone().json();
            if (data.session_expired) {
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
        showToast('Session Expired', 'Your session has expired. Redirecting to login...', 'warning');
        setTimeout(() => {
            window.location.href = '/login?next=' + encodeURIComponent(window.location.href);
        }, 1500);
        throw new Error('Session expired');
    }
    
    return response;
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
            showToast('Error', data.error.message || 'Failed to update tag', 'error');
        } else {
            location.reload();
        }
    })
    .catch(error => {
        if (error.message !== 'Session expired') {
            showToast('Error', 'Failed to update tag', 'error');
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
            showToast('Error', data.error.message || 'Failed to remove tag', 'error');
        } else {
            showToast('Success', 'Tag removed successfully', 'success');
            setTimeout(() => location.reload(), 1000);
        }
    })
    .catch(error => {
        if (error.message !== 'Session expired') {
            showToast('Error', 'Failed to remove tag', 'error');
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
            showToast('Error', data.error.message || 'Failed to remove area', 'error');
        } else {
            showToast('Success', 'Area removed successfully', 'success');
            setTimeout(() => window.location.href = '/select_area', 1500);
        }
    })
    .catch(error => {
        if (error.message !== 'Session expired') {
            showToast('Error', 'Failed to remove area', 'error');
        }
    });
}
