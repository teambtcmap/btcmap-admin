/**
 * Map Editor Component
 * 
 * Provides Leaflet map with draw controls for polygon editing,
 * and a raw GeoJSON text editor.
 * 
 * Usage:
 *   const mapEditor = initMapEditor({
 *       containerId: 'map',
 *       initialGeoJson: existingGeoJson || null,
 *       onGeoJsonChange: (geometry) => { window.currentGeoJson = geometry; }
 *   });
 * 
 * Returns:
 *   {
 *       map: Leaflet map instance,
 *       drawnItems: FeatureGroup for editing,
 *       getCurrentGeoJson: () => geometry object or null,
 *       updateGeoJson: (geojson) => void,
 *   }
 */

function initMapEditor(options = {}) {
    const {
        containerId = 'map',
        initialGeoJson = null,
        onGeoJsonChange = null
    } = options;

    // State
    let currentGeoJson = null;
    let geoJsonLayer = null;
    let previouslySavedGeoJson = null;

    // DOM Elements
    const elements = {
        mapContainer: document.getElementById(containerId),
        editGeoJsonBtn: document.getElementById('edit-geojson-btn'),
        geoJsonEditor: document.getElementById('geojson-editor'),
        geoJsonInput: document.getElementById('geojson-input'),
        showBtn: document.getElementById('show-geojson-btn'),
        saveLocallyBtn: document.getElementById('save-locally-btn'),
        cancelBtn: document.getElementById('cancel-geojson-btn')
    };

    // Initialize map
    if (!elements.mapContainer) {
        console.error('[MapEditor] Map container not found:', containerId);
        return null;
    }

    const map = L.map(containerId).setView([0, 0], 2);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors'
    }).addTo(map);

    // Initialize draw control
    const drawnItems = new L.FeatureGroup();
    map.addLayer(drawnItems);

    const drawControl = new L.Control.Draw({
        draw: {
            polygon: {
                allowIntersection: false,
                showArea: true,
                shapeOptions: {
                    color: '#3388ff',
                    weight: 3
                }
            },
            rectangle: {
                shapeOptions: {
                    color: '#3388ff',
                    weight: 3
                }
            },
            circle: false,
            circlemarker: false,
            marker: false,
            polyline: false
        },
        edit: {
            featureGroup: drawnItems,
            remove: true,
            edit: true
        }
    });
    map.addControl(drawControl);

    // Update GeoJSON from drawn items
    function updateGeoJsonFromDrawnItems() {
        if (drawnItems.getLayers().length === 0) {
            currentGeoJson = null;
            if (elements.geoJsonInput) {
                elements.geoJsonInput.value = '';
            }
            if (onGeoJsonChange) {
                onGeoJsonChange(null);
            }
            return;
        }

        const layer = drawnItems.getLayers()[0];
        const geoJson = layer.toGeoJSON();
        currentGeoJson = geoJson.geometry;

        // Keep textarea in sync
        if (elements.geoJsonInput) {
            elements.geoJsonInput.value = JSON.stringify(currentGeoJson, null, 2);
        }

        map.fitBounds(drawnItems.getBounds());

        if (onGeoJsonChange) {
            onGeoJsonChange(currentGeoJson);
        }
    }

    // Update map with GeoJSON
    function updateGeoJson(geoJson) {
        try {
            // Remove existing geoJsonLayer
            if (geoJsonLayer) {
                map.removeLayer(geoJsonLayer);
            }

            // Clear drawn items
            drawnItems.clearLayers();

            if (!geoJson) {
                currentGeoJson = null;
                if (elements.geoJsonInput) {
                    elements.geoJsonInput.value = '';
                }
                if (onGeoJsonChange) {
                    onGeoJsonChange(null);
                }
                return true;
            }

            // Handle string input
            if (typeof geoJson === 'string') {
                geoJson = JSON.parse(geoJson);
            }

            // Extract geometry if wrapped in Feature
            let geometry = geoJson;
            if (geoJson.type === 'Feature') {
                geometry = geoJson.geometry;
            } else if (geoJson.type === 'FeatureCollection' && geoJson.features && geoJson.features.length > 0) {
                geometry = geoJson.features[0].geometry;
            }

            // Store just the geometry
            currentGeoJson = geometry;

            // Wrap back as Feature for display in Leaflet
            const featureCollection = {
                "type": "Feature",
                "geometry": geometry
            };

            // Create GeoJSON feature and add to map
            geoJsonLayer = L.geoJSON(featureCollection).addTo(map);
            map.fitBounds(geoJsonLayer.getBounds());

            // Also add to drawnItems for editing
            if (geoJsonLayer.getLayers().length > 0) {
                const layer = geoJsonLayer.getLayers()[0];
                drawnItems.addLayer(layer);
            }

            // Update textarea with current GeoJSON (keep them in sync)
            if (elements.geoJsonInput) {
                elements.geoJsonInput.value = JSON.stringify(currentGeoJson, null, 2);
            }

            if (onGeoJsonChange) {
                onGeoJsonChange(currentGeoJson);
            }

            return true;
        } catch (error) {
            console.error("[MapEditor] Error adding GeoJSON to map:", error);
            if (typeof showToast === 'function') {
                showToast('Error', `Invalid GeoJSON: ${error.message}`, 'error');
            }
            return false;
        }
    }

    // Handle draw created
    map.on(L.Draw.Event.CREATED, function(e) {
        const layer = e.layer;
        // Clear existing and add new
        drawnItems.clearLayers();
        drawnItems.addLayer(layer);
        updateGeoJsonFromDrawnItems();
    });

    // Handle draw edited
    map.on(L.Draw.Event.EDITED, function(e) {
        updateGeoJsonFromDrawnItems();
    });

    // Handle draw deleted
    map.on(L.Draw.Event.DELETED, function(e) {
        currentGeoJson = null;
        if (geoJsonLayer) {
            map.removeLayer(geoJsonLayer);
            geoJsonLayer = null;
        }
        if (elements.geoJsonInput) {
            elements.geoJsonInput.value = '';
        }
        if (onGeoJsonChange) {
            onGeoJsonChange(null);
        }
    });

    // Raw GeoJSON editor functionality
    function showEditor() {
        if (elements.geoJsonEditor) {
            elements.geoJsonEditor.style.display = 'block';
        }
        if (currentGeoJson && elements.geoJsonInput) {
            elements.geoJsonInput.value = JSON.stringify(currentGeoJson, null, 2);
            previouslySavedGeoJson = JSON.parse(JSON.stringify(currentGeoJson));
        }
    }

    function hideEditor() {
        if (elements.geoJsonEditor) {
            elements.geoJsonEditor.style.display = 'none';
        }
    }

    function showGeoJsonPreview() {
        try {
            const geoJson = JSON.parse(elements.geoJsonInput.value);
            if (updateGeoJson(geoJson)) {
                if (typeof showToast === 'function') {
                    showToast('Success', 'GeoJSON preview updated', 'success');
                }
            }
        } catch (error) {
            console.error("[MapEditor] Error parsing GeoJSON:", error);
            if (typeof showToast === 'function') {
                showToast('Error', 'Invalid GeoJSON: ' + error.message, 'error');
            }
        }
    }

    function saveLocally() {
        try {
            const geoJson = JSON.parse(elements.geoJsonInput.value);
            if (updateGeoJson(geoJson)) {
                hideEditor();
                previouslySavedGeoJson = currentGeoJson;
                if (typeof showToast === 'function') {
                    showToast('Success', 'GeoJSON saved locally', 'success');
                }
            }
        } catch (error) {
            console.error("[MapEditor] Error saving GeoJSON:", error);
            if (typeof showToast === 'function') {
                showToast('Error', 'Invalid GeoJSON: ' + error.message, 'error');
            }
        }
    }

    function cancelEditing() {
        hideEditor();
        if (previouslySavedGeoJson) {
            updateGeoJson(previouslySavedGeoJson);
        }
    }

    // Set up event listeners
    if (elements.editGeoJsonBtn) {
        elements.editGeoJsonBtn.addEventListener('click', showEditor);
    }
    if (elements.showBtn) {
        elements.showBtn.addEventListener('click', showGeoJsonPreview);
    }
    if (elements.saveLocallyBtn) {
        elements.saveLocallyBtn.addEventListener('click', saveLocally);
    }
    if (elements.cancelBtn) {
        elements.cancelBtn.addEventListener('click', cancelEditing);
    }

    // Load initial GeoJSON if provided
    if (initialGeoJson) {
        // Delay slightly to ensure map is fully initialized
        setTimeout(() => {
            updateGeoJson(initialGeoJson);
        }, 100);
    }

    // Return public API
    return {
        map,
        drawnItems,
        getCurrentGeoJson: () => currentGeoJson,
        updateGeoJson,
        showEditor,
        hideEditor
    };
}

// Export for module systems if available
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { initMapEditor };
}
