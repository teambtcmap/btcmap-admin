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
    if (confirm(`Are you sure you want to remove the tag "${tagName}"?`)) {
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
                alert(`Error: ${data.error.message}`);
            } else {
                location.reload();
            }
        });
    }
}

function removeArea(areaId) {
    if (confirm(`Are you sure you want to remove this area?`)) {
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
                alert(`Error: ${data.error.message}`);
            } else {
                window.location.href = '/select_area';
            }
        });
    }
}
