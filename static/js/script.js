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


function setupImageHandling() {
    const imageInput = document.getElementById('imageInput');
    const previewImage = document.getElementById('previewImage');
    const cropContainer = document.getElementById('cropContainer');
    const zoomSlider = document.getElementById('zoomSlider');
    const cropButton = document.getElementById('cropButton');
    const croppedCanvas = document.getElementById('croppedCanvas');
    
    let currentScale = 1;
    let currentX = 0;
    let currentY = 0;
    let isDragging = false;
    let startX, startY;
    
    imageInput.addEventListener('change', function(e) {
        const file = e.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = function(e) {
                previewImage.src = e.target.result;
                cropContainer.style.display = 'block';
                
                // Reset transform values
                currentScale = 1;
                currentX = 0;
                currentY = 0;
                updateImageTransform();
            };
            reader.readAsDataURL(file);
        }
    });
    
    zoomSlider.addEventListener('input', function(e) {
        currentScale = e.target.value;
        updateImageTransform();
    });
    
    previewImage.addEventListener('mousedown', function(e) {
        isDragging = true;
        startX = e.clientX - currentX;
        startY = e.clientY - currentY;
    });
    
    document.addEventListener('mousemove', function(e) {
        if (isDragging) {
            currentX = e.clientX - startX;
            currentY = e.clientY - startY;
            updateImageTransform();
        }
    });
    
    document.addEventListener('mouseup', function() {
        isDragging = false;
    });
    
    function updateImageTransform() {
        previewImage.style.transform = `translate(${currentX}px, ${currentY}px) scale(${currentScale})`;
    }
    
    cropButton.addEventListener('click', function() {
        const ctx = croppedCanvas.getContext('2d');
        croppedCanvas.width = 300;
        croppedCanvas.height = 300;
        
        const previewRect = previewImage.getBoundingClientRect();
        const containerRect = document.getElementById('imagePreview').getBoundingClientRect();
        
        ctx.drawImage(
            previewImage,
            (containerRect.left - previewRect.left) / currentScale,
            (containerRect.top - previewRect.top) / currentScale,
            containerRect.width / currentScale,
            containerRect.height / currentScale,
            0, 0, 300, 300
        );
        
        const base64Data = croppedCanvas.toDataURL('image/png');
        
        // Set the icon:square tag value
        const tagsTable = document.getElementById('tags-table').querySelector('tbody');
        let iconRow = Array.from(tagsTable.querySelectorAll('tr')).find(row => {
            const keyCell = row.querySelector('td:first-child');
            return keyCell.textContent.trim() === 'icon:square';
        });
        
        if (iconRow) {
            const valueInput = iconRow.querySelector('input');
            if (valueInput) {
                valueInput.value = `https://static.btcmap.org/images/areas/${areaId}.png`;
            }
        }
        
        // Call RPC to set the icon
        fetch('/api/set_area_icon', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                id: areaId,
                icon_base64: base64Data.split(',')[1],
                icon_ext: 'png'
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showToast('Error', data.error.message, 'error');
            } else {
                showToast('Success', 'Icon updated successfully', 'success');
            }
        })
        .catch(error => {
            showToast('Error', error.message, 'error');
        });
    });
}

document.addEventListener('DOMContentLoaded', function() {
    setupImageHandling();
});
