/**
 * Map Editor Component
 * 
 * Provides Leaflet map with draw controls for polygon editing,
 * shape editing tools (simplify/buffer/merge), and a raw GeoJSON text editor.
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
 * 
 * Requires:
 *   - Leaflet and Leaflet.draw loaded
 *   - Turf.js loaded (for shape editing)
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
    
    // Shape editor state
    let originalShapeGeoJson = null;    // Original shape before editing
    let shapePreviewLayer = null;       // Preview layer for shape edits
    let originalShapeLayer = null;      // Reference layer showing original

    // DOM Elements
    const elements = {
        mapContainer: document.getElementById(containerId),
        // Raw GeoJSON editor
        editGeoJsonBtn: document.getElementById('edit-geojson-btn'),
        geoJsonEditor: document.getElementById('geojson-editor'),
        geoJsonInput: document.getElementById('geojson-input'),
        showBtn: document.getElementById('show-geojson-btn'),
        saveLocallyBtn: document.getElementById('save-locally-btn'),
        cancelBtn: document.getElementById('cancel-geojson-btn'),
        // Shape editor
        editShapeBtn: document.getElementById('edit-shape-btn'),
        shapeEditor: document.getElementById('shape-editor'),
        shapeSimplifySlider: document.getElementById('shape-simplify-slider'),
        shapeSimplifyValue: document.getElementById('shape-simplify-value'),
        shapeBufferSlider: document.getElementById('shape-buffer-slider'),
        shapeBufferValue: document.getElementById('shape-buffer-value'),
        shapeMegaSimplifyCheckbox: document.getElementById('shape-mega-simplify'),
        shapeTightnessSlider: document.getElementById('shape-tightness-slider'),
        shapeTightnessValue: document.getElementById('shape-tightness-value'),
        shapePointsCount: document.getElementById('shape-points-count'),
        shapeShowOriginal: document.getElementById('shape-show-original'),
        applyShapeBtn: document.getElementById('apply-shape-btn'),
        cancelShapeBtn: document.getElementById('cancel-shape-btn')
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

    // ============================================
    // Shape Editor functionality
    // ============================================

    // Convert linear slider (0-10) to logarithmic tolerance
    function sliderToTolerance(sliderVal) {
        if (sliderVal === 0) return 0;
        const minLog = Math.log10(0.000001);
        const maxLog = Math.log10(0.01);
        const logVal = minLog + (sliderVal / 10) * (maxLog - minLog);
        return Math.pow(10, logVal);
    }

    function formatTolerance(val) {
        if (val === 0) return '0';
        if (val < 0.00001) return val.toExponential(1);
        if (val < 0.0001) return val.toFixed(6);
        if (val < 0.001) return val.toFixed(5);
        if (val < 0.01) return val.toFixed(4);
        return val.toFixed(3);
    }

    // Convert tightness slider (0-10) to concavity for turf.convex()
    // 0 = pure convex (concavity = Infinity)
    // 10 = tighter fit (concavity = 1)
    function sliderToConcavity(sliderVal) {
        if (sliderVal === 0) return Infinity;
        return Math.max(1, 21 - (sliderVal * 2));
    }

    function formatTightness(val) {
        if (val === 0) return 'Loose';
        if (val === 10) return 'Tight';
        return val.toString();
    }

    function countGeojsonPoints(geojson) {
        let count = 0;
        function countCoords(coords) {
            if (typeof coords[0] === 'number') {
                count++;
            } else {
                coords.forEach(c => countCoords(c));
            }
        }
        const geometry = geojson.geometry || geojson;
        if (geometry && geometry.coordinates) {
            countCoords(geometry.coordinates);
        }
        return count;
    }

    function showShapeEditor() {
        if (!currentGeoJson) {
            if (typeof showToast === 'function') {
                showToast('Warning', 'No shape to edit. Draw or import a polygon first.', 'warning');
            }
            return;
        }

        // Store original shape
        originalShapeGeoJson = JSON.parse(JSON.stringify(currentGeoJson));

        // Hide raw GeoJSON editor if open
        hideEditor();

        // Reset sliders to neutral (no changes)
        if (elements.shapeSimplifySlider) {
            elements.shapeSimplifySlider.value = 0;
            elements.shapeSimplifyValue.textContent = '0';
        }
        if (elements.shapeBufferSlider) {
            elements.shapeBufferSlider.value = 0;
            elements.shapeBufferValue.textContent = '0';
        }
        if (elements.shapeMegaSimplifyCheckbox) {
            elements.shapeMegaSimplifyCheckbox.checked = false;
        }
        if (elements.shapeTightnessSlider) {
            elements.shapeTightnessSlider.value = 0;
            elements.shapeTightnessSlider.disabled = true;
            elements.shapeTightnessValue.textContent = 'Loose';
        }

        // Show editor
        if (elements.shapeEditor) {
            elements.shapeEditor.style.display = 'block';
        }

        // Show original shape and initial preview
        updateOriginalShapeLayer();
        processAndPreviewShape();
    }

    function hideShapeEditor() {
        if (elements.shapeEditor) {
            elements.shapeEditor.style.display = 'none';
        }
        // Remove preview layers
        if (shapePreviewLayer) {
            map.removeLayer(shapePreviewLayer);
            shapePreviewLayer = null;
        }
        if (originalShapeLayer) {
            map.removeLayer(originalShapeLayer);
            originalShapeLayer = null;
        }
    }

    function updateOriginalShapeLayer() {
        // Remove existing layer
        if (originalShapeLayer) {
            map.removeLayer(originalShapeLayer);
            originalShapeLayer = null;
        }

        if (!originalShapeGeoJson || !elements.shapeShowOriginal || !elements.shapeShowOriginal.checked) {
            return;
        }

        // Wrap as Feature if needed
        let feature = originalShapeGeoJson;
        if (originalShapeGeoJson.type !== 'Feature' && originalShapeGeoJson.type !== 'FeatureCollection') {
            feature = { type: 'Feature', geometry: originalShapeGeoJson, properties: {} };
        }

        // Create dashed line style for reference
        originalShapeLayer = L.geoJSON(feature, {
            style: {
                color: '#ff6600',
                weight: 2,
                dashArray: '5, 5',
                fillOpacity: 0,
                interactive: false
            }
        }).addTo(map);
    }

    function processAndPreviewShape() {
        if (!originalShapeGeoJson) return;

        try {
            // Wrap as Feature if needed
            let feature = originalShapeGeoJson;
            if (originalShapeGeoJson.type !== 'Feature' && originalShapeGeoJson.type !== 'FeatureCollection') {
                feature = { type: 'Feature', geometry: originalShapeGeoJson, properties: {} };
            }

            const tolerance = sliderToTolerance(parseFloat(elements.shapeSimplifySlider?.value || 0));
            const buffer = parseFloat(elements.shapeBufferSlider?.value || 0);

            let processed = feature;

            // Apply buffer if > 0
            if (buffer > 0 && typeof turf !== 'undefined') {
                processed = turf.buffer(processed, buffer, { units: 'kilometers' });
            }

            // Apply simplification if > 0
            if (tolerance > 0 && typeof turf !== 'undefined') {
                processed = turf.simplify(processed, {
                    tolerance: tolerance,
                    highQuality: true
                });
            }

            // Apply mega simplify if checked
            if (elements.shapeMegaSimplifyCheckbox?.checked && typeof turf !== 'undefined') {
                const concavity = sliderToConcavity(parseFloat(elements.shapeTightnessSlider?.value || 0));

                try {
                    // Use turf.convex with concavity parameter
                    processed = turf.convex(processed, { concavity: concavity });
                    
                    if (!processed) {
                        console.warn('[MapEditor] Convex hull returned null');
                        processed = turf.convex(feature);
                    }
                } catch (e) {
                    console.warn('[MapEditor] Convex hull failed:', e.message);
                    // Keep original processed value
                }
            }

            // Remove existing preview layer
            if (shapePreviewLayer) {
                map.removeLayer(shapePreviewLayer);
            }

            // Hide the main drawn items while previewing
            drawnItems.eachLayer(layer => {
                layer.setStyle({ opacity: 0, fillOpacity: 0 });
            });

            // Add preview layer
            shapePreviewLayer = L.geoJSON(processed, {
                style: {
                    color: '#3388ff',
                    weight: 3,
                    fillColor: '#3388ff',
                    fillOpacity: 0.2
                }
            }).addTo(map);

            // Fit bounds
            map.fitBounds(shapePreviewLayer.getBounds());

            // Update point count
            const count = countGeojsonPoints(processed);
            if (elements.shapePointsCount) {
                elements.shapePointsCount.textContent = `Points: ${count}`;
            }

        } catch (error) {
            console.error('[MapEditor] Error processing shape:', error);
            if (typeof showToast === 'function') {
                showToast('Error', `Error processing: ${error.message}`, 'error');
            }
        }
    }

    function applyShapeChanges() {
        if (!shapePreviewLayer) {
            if (typeof showToast === 'function') {
                showToast('Warning', 'No changes to apply', 'warning');
            }
            return;
        }

        // Get geometry from preview layer
        const previewGeoJson = shapePreviewLayer.toGeoJSON();
        let geometry = previewGeoJson;
        if (previewGeoJson.type === 'FeatureCollection' && previewGeoJson.features.length > 0) {
            geometry = previewGeoJson.features[0].geometry;
        } else if (previewGeoJson.type === 'Feature') {
            geometry = previewGeoJson.geometry;
        }

        // Hide shape editor
        hideShapeEditor();

        // Restore visibility of drawn items
        drawnItems.eachLayer(layer => {
            layer.setStyle({ opacity: 1, fillOpacity: 0.2 });
        });

        // Apply the processed geometry
        updateGeoJson(geometry);

        if (typeof showToast === 'function') {
            showToast('Success', 'Shape changes applied', 'success');
        }
    }

    function cancelShapeEditing() {
        hideShapeEditor();

        // Restore visibility of drawn items
        drawnItems.eachLayer(layer => {
            layer.setStyle({ opacity: 1, fillOpacity: 0.2 });
        });

        // Restore original shape
        if (originalShapeGeoJson) {
            updateGeoJson(originalShapeGeoJson);
        }
        originalShapeGeoJson = null;
    }

    // Set up event listeners - Raw GeoJSON editor
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

    // Set up event listeners - Shape editor
    if (elements.editShapeBtn) {
        elements.editShapeBtn.addEventListener('click', showShapeEditor);
    }
    if (elements.shapeSimplifySlider) {
        elements.shapeSimplifySlider.addEventListener('input', function() {
            const tolerance = sliderToTolerance(parseFloat(this.value));
            elements.shapeSimplifyValue.textContent = formatTolerance(tolerance);
            processAndPreviewShape();
        });
    }
    if (elements.shapeBufferSlider) {
        elements.shapeBufferSlider.addEventListener('input', function() {
            elements.shapeBufferValue.textContent = this.value;
            processAndPreviewShape();
        });
    }
    if (elements.shapeMegaSimplifyCheckbox) {
        elements.shapeMegaSimplifyCheckbox.addEventListener('change', function() {
            if (elements.shapeTightnessSlider) {
                elements.shapeTightnessSlider.disabled = !this.checked;
            }
            processAndPreviewShape();
        });
    }
    if (elements.shapeTightnessSlider) {
        elements.shapeTightnessSlider.addEventListener('input', function() {
            const val = parseInt(this.value);
            if (elements.shapeTightnessValue) {
                elements.shapeTightnessValue.textContent = formatTightness(val);
            }
            processAndPreviewShape();
        });
    }
    if (elements.shapeShowOriginal) {
        elements.shapeShowOriginal.addEventListener('change', updateOriginalShapeLayer);
    }
    if (elements.applyShapeBtn) {
        elements.applyShapeBtn.addEventListener('click', applyShapeChanges);
    }
    if (elements.cancelShapeBtn) {
        elements.cancelShapeBtn.addEventListener('click', cancelShapeEditing);
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
        hideEditor,
        showShapeEditor,
        hideShapeEditor
    };
}

// Export for module systems if available
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { initMapEditor };
}
