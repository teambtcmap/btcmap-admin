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
    fetch('/api/set_area_tag', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ id: areaId, name: tagName, value: tagValue }),
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            alert(`Error: ${data.error.message}`);
        } else {
            location.reload();
        }
    });
}

function removeTag(areaId, tagName) {
    fetch('/api/remove_area_tag', {
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
        showToast('Error', 'Failed to remove tag', 'error');
    });
}

function removeArea(areaId) {
    fetch('/api/remove_area', {
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
        showToast('Error', 'Failed to remove area', 'error');
    });
}
