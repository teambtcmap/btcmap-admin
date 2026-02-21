/**
 * OSM GeoJSON Generator Component
 *
 * Provides OSM search functionality with Turf.js processing
 * for simplification and buffering of boundaries.
 *
 * Usage:
 *   initOsmGeojsonGenerator({
 *       mapEditor: mapEditorInstance,
 *       onApply: (geometry) => mapEditor.updateGeoJson(geometry),
 *       onPopulationFound: (population, date) => { ... }
 *   });
 *
 * Requires:
 *   - Turf.js loaded
 *   - mapEditor instance from map-editor.js
 *   - apiFetch function for API calls
 *   - showToast function for notifications
 */

function initOsmGeojsonGenerator(options = {}) {
	const {
		mapEditor = null,
		onApply = null,
		onPopulationFound = null,
	} = options;

	if (!mapEditor) {
		console.error('[OsmGeojsonGenerator] mapEditor is required');
		return null;
	}

	// DOM Elements
	const elements = {
		searchInput: document.getElementById('osm-search-input'),
		searchBtn: document.getElementById('osm-search-btn'),
		resultsContainer: document.getElementById('search-results-container'),
		resultsSelect: document.getElementById('search-results'),
		controls: document.getElementById('geojson-controls'),
		simplifySlider: document.getElementById('simplify-slider'),
		simplifyValue: document.getElementById('simplify-value'),
		bufferSlider: document.getElementById('buffer-slider'),
		bufferValue: document.getElementById('buffer-value'),
		megaSimplifyCheckbox: document.getElementById('mega-simplify'),
		tightnessSlider: document.getElementById('tightness-slider'),
		tightnessValue: document.getElementById('tightness-value'),
		pointsCount: document.getElementById('points-count'),
		showOriginalBoundary: document.getElementById('show-original-boundary'),
		applyBtn: document.getElementById('apply-geojson-btn'),
		loading: document.getElementById('geojson-loading'),
		error: document.getElementById('geojson-error'),
	};

	// State
	let originalOsmGeojson = null; // Full-detail from Nominatim
	let processedGeojson = null; // After simplification/buffer
	let originalBoundaryLayer = null; // Reference layer showing original
	let previewLayer = null; // Preview layer for processed result
	let osmSearchResults = []; // Store search results

	// Helper functions
	function showError(message) {
		if (elements.error) {
			elements.error.textContent = message;
			elements.error.style.display = 'block';
		}
	}

	function hideError() {
		if (elements.error) {
			elements.error.style.display = 'none';
		}
	}

	function showLoading(show) {
		if (elements.loading) {
			elements.loading.style.display = show ? 'block' : 'none';
		}
	}

	function countGeojsonPoints(geojson) {
		let count = 0;

		function countCoords(coords) {
			if (typeof coords[0] === 'number') {
				count++;
			} else {
				coords.forEach((c) => countCoords(c));
			}
		}

		const geometry = geojson.geometry || geojson;
		if (geometry && geometry.coordinates) {
			countCoords(geometry.coordinates);
		}

		return count;
	}

	// Convert linear slider (0-10) to logarithmic tolerance
	// 0 = 0 (no simplification), 1 = 0.000001, 5 = 0.0001, 10 = 0.01
	function sliderToTolerance(sliderVal) {
		if (sliderVal === 0) return 0;
		// Map 1-10 to 0.000001-0.01 logarithmically (6 orders of magnitude)
		const minLog = Math.log10(0.000001); // -6
		const maxLog = Math.log10(0.01); // -2
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
		if (sliderVal === 0) return Infinity; // Pure convex hull
		// Map 1-10 to concavity values (higher = looser, lower = tighter)
		// 1 = 20 (loose), 10 = 1 (tight)
		return Math.max(1, 21 - sliderVal * 2);
	}

	function formatTightness(val) {
		if (val === 0) return 'Loose';
		if (val === 10) return 'Tight';
		return val.toString();
	}

	// Search OSM via Nominatim
	async function searchOSM() {
		const query = elements.searchInput.value.trim();
		if (!query) {
			if (typeof showToast === 'function') {
				showToast('Warning', 'Please enter a search term', 'warning');
			}
			return;
		}

		hideError();
		elements.resultsContainer.style.display = 'none';
		elements.controls.style.display = 'none';
		showLoading(true);

		try {
			const response = await apiFetch(
				`/api/search_osm?q=${encodeURIComponent(query)}`,
			);
			const results = await response.json();

			if (results.error) {
				throw new Error(results.error);
			}

			if (results.length === 0) {
				showError(
					'No administrative areas found. Try a different search term.',
				);
				return;
			}

			// Store results and populate dropdown
			osmSearchResults = results;
			elements.resultsSelect.innerHTML =
				'<option value="">Select a place...</option>';
			results.forEach((r, index) => {
				const option = document.createElement('option');
				option.value = index;
				option.textContent = r.display_name;
				elements.resultsSelect.appendChild(option);
			});

			elements.resultsContainer.style.display = 'block';
		} catch (error) {
			console.error('[OsmGeojsonGenerator] Search error:', error);
			showError(error.message || 'Search failed');
		} finally {
			showLoading(false);
		}
	}

	// Handle search result selection
	async function onSearchResultSelect() {
		const index = elements.resultsSelect.value;
		if (index === '') return;

		const result = osmSearchResults[parseInt(index)];
		if (!result || !result.geojson) {
			showError('Selected place has no boundary data');
			return;
		}

		// Check if there's already a polygon, confirm before replacing
		const currentGeoJson = mapEditor.getCurrentGeoJson();
		if (currentGeoJson && mapEditor.drawnItems.getLayers().length > 0) {
			const confirmed = await confirmPolygonReplacement();
			if (!confirmed) {
				elements.resultsSelect.value = '';
				return;
			}
		}

		// Store the original GeoJSON
		originalOsmGeojson = result.geojson;

		// Handle population data from OSM extratags
		if (
			result.extratags &&
			result.extratags.population &&
			onPopulationFound
		) {
			const populationValue = parseInt(result.extratags.population, 10);
			if (!isNaN(populationValue)) {
				const today = new Date().toISOString().split('T')[0];
				onPopulationFound(populationValue, today);
			}
		}

		// Reset sliders to defaults
		elements.simplifySlider.value = 5; // Maps to ~0.001 tolerance
		elements.simplifyValue.textContent = formatTolerance(
			sliderToTolerance(5),
		);
		elements.bufferSlider.value = 0.1;
		elements.bufferValue.textContent = '0.1';

		// Reset mega simplify controls
		if (elements.megaSimplifyCheckbox) {
			elements.megaSimplifyCheckbox.checked = false;
		}
		if (elements.tightnessSlider) {
			elements.tightnessSlider.value = 0;
			elements.tightnessSlider.disabled = true;
		}
		if (elements.tightnessValue) {
			elements.tightnessValue.textContent = 'Loose';
		}

		// Show controls and process
		elements.controls.style.display = 'block';

		// Show original boundary and process
		updateOriginalBoundaryLayer();
		processAndPreviewGeojson();
	}

	// Confirmation dialog for replacing existing polygon
	function confirmPolygonReplacement() {
		return new Promise((resolve) => {
			const result = confirm(
				'Replace existing polygon with the selected OSM boundary?',
			);
			resolve(result);
		});
	}

	// Show/hide original boundary reference layer
	function updateOriginalBoundaryLayer() {
		const map = mapEditor.map;

		// Remove existing layer
		if (originalBoundaryLayer) {
			map.removeLayer(originalBoundaryLayer);
			originalBoundaryLayer = null;
		}

		if (!originalOsmGeojson || !elements.showOriginalBoundary.checked) {
			return;
		}

		// Wrap as Feature if needed
		let feature = originalOsmGeojson;
		if (
			originalOsmGeojson.type !== 'Feature' &&
			originalOsmGeojson.type !== 'FeatureCollection'
		) {
			feature = {
				type: 'Feature',
				geometry: originalOsmGeojson,
				properties: {},
			};
		}

		// Create dashed line style for reference
		originalBoundaryLayer = L.geoJSON(feature, {
			style: {
				color: '#ff6600',
				weight: 2,
				dashArray: '5, 5',
				fillOpacity: 0,
				interactive: false,
			},
		}).addTo(map);
	}

	// Process GeoJSON with Turf.js and preview
	function processAndPreviewGeojson() {
		if (!originalOsmGeojson) return;

		const map = mapEditor.map;

		try {
			// Wrap as Feature if needed
			let feature = originalOsmGeojson;
			if (
				originalOsmGeojson.type !== 'Feature' &&
				originalOsmGeojson.type !== 'FeatureCollection'
			) {
				feature = {
					type: 'Feature',
					geometry: originalOsmGeojson,
					properties: {},
				};
			}

			const tolerance = sliderToTolerance(
				parseFloat(elements.simplifySlider.value),
			);
			const buffer = parseFloat(elements.bufferSlider.value);

			let processed = feature;

			// Apply buffer if > 0
			if (buffer > 0) {
				processed = turf.buffer(processed, buffer, {
					units: 'kilometers',
				});
			}

			// Apply simplification if > 0
			if (tolerance > 0) {
				processed = turf.simplify(processed, {
					tolerance: tolerance,
					highQuality: true,
				});
			}

			// Apply mega simplify if checked
			if (
				elements.megaSimplifyCheckbox &&
				elements.megaSimplifyCheckbox.checked
			) {
				const concavity = sliderToConcavity(
					parseFloat(elements.tightnessSlider.value),
				);

				try {
					// Use turf.convex with concavity parameter
					// concavity: 1 = tight, Infinity = pure convex hull
					processed = turf.convex(processed, {
						concavity: concavity,
					});

					if (!processed) {
						console.warn(
							'[OsmGeojsonGenerator] Convex hull returned null',
						);
						// Fallback: try pure convex
						processed = turf.convex(feature);
					}
				} catch (e) {
					console.warn(
						'[OsmGeojsonGenerator] Convex hull failed:',
						e.message,
					);
					// Keep original processed value
				}
			}

			processedGeojson = processed;

			// Remove existing preview layer
			if (previewLayer) {
				map.removeLayer(previewLayer);
			}

			// Add preview layer
			previewLayer = L.geoJSON(processed, {
				style: {
					color: '#3388ff',
					weight: 3,
					fillColor: '#3388ff',
					fillOpacity: 0.2,
				},
			}).addTo(map);

			// Fit bounds
			map.fitBounds(previewLayer.getBounds());

			// Update point count
			const count = countGeojsonPoints(processed);
			elements.pointsCount.textContent = `Points: ${count}`;
		} catch (error) {
			console.error(
				'[OsmGeojsonGenerator] Error processing GeoJSON:',
				error,
			);
			showError(`Error processing: ${error.message}`);
		}
	}

	// Apply the processed GeoJSON to the map for editing
	function applyProcessedGeojson() {
		if (!processedGeojson) {
			if (typeof showToast === 'function') {
				showToast(
					'Warning',
					'No processed GeoJSON to apply',
					'warning',
				);
			}
			return;
		}

		const map = mapEditor.map;

		// Extract geometry
		const geometry = processedGeojson.geometry || processedGeojson;

		// Remove preview layer
		if (previewLayer) {
			map.removeLayer(previewLayer);
			previewLayer = null;
		}

		// Remove original boundary layer
		if (originalBoundaryLayer) {
			map.removeLayer(originalBoundaryLayer);
			originalBoundaryLayer = null;
		}

		// Call the onApply callback
		if (onApply) {
			onApply(geometry);
		}

		// Hide controls and reset state
		elements.controls.style.display = 'none';
		elements.resultsContainer.style.display = 'none';
		elements.searchInput.value = '';
		elements.resultsSelect.innerHTML =
			'<option value="">Select a place...</option>';
		originalOsmGeojson = null;
		processedGeojson = null;
		osmSearchResults = [];

		if (typeof showToast === 'function') {
			showToast(
				'Success',
				'GeoJSON applied. You can now edit the polygon on the map.',
				'success',
			);
		}
	}

	// Set up event listeners
	if (elements.searchBtn) {
		elements.searchBtn.addEventListener('click', searchOSM);
	}

	if (elements.searchInput) {
		elements.searchInput.addEventListener('keypress', (e) => {
			if (e.key === 'Enter') {
				e.preventDefault();
				searchOSM();
			}
		});
	}

	if (elements.resultsSelect) {
		elements.resultsSelect.addEventListener('change', onSearchResultSelect);
	}

	if (elements.simplifySlider) {
		elements.simplifySlider.addEventListener('input', function () {
			const tolerance = sliderToTolerance(parseFloat(this.value));
			elements.simplifyValue.textContent = formatTolerance(tolerance);
			processAndPreviewGeojson();
		});
	}

	if (elements.bufferSlider) {
		elements.bufferSlider.addEventListener('input', function () {
			elements.bufferValue.textContent = this.value;
			processAndPreviewGeojson();
		});
	}

	if (elements.showOriginalBoundary) {
		elements.showOriginalBoundary.addEventListener(
			'change',
			updateOriginalBoundaryLayer,
		);
	}

	// Mega simplify checkbox
	if (elements.megaSimplifyCheckbox) {
		elements.megaSimplifyCheckbox.addEventListener('change', function () {
			// Enable/disable tightness slider based on checkbox
			if (elements.tightnessSlider) {
				elements.tightnessSlider.disabled = !this.checked;
			}
			processAndPreviewGeojson();
		});
	}

	// Tightness slider
	if (elements.tightnessSlider) {
		elements.tightnessSlider.addEventListener('input', function () {
			const val = parseInt(this.value);
			if (elements.tightnessValue) {
				elements.tightnessValue.textContent = formatTightness(val);
			}
			processAndPreviewGeojson();
		});
	}

	if (elements.applyBtn) {
		elements.applyBtn.addEventListener('click', applyProcessedGeojson);
	}

	// Return public API (minimal, mostly self-contained)
	return {
		searchOSM,
		reset: () => {
			const map = mapEditor.map;
			if (previewLayer) {
				map.removeLayer(previewLayer);
				previewLayer = null;
			}
			if (originalBoundaryLayer) {
				map.removeLayer(originalBoundaryLayer);
				originalBoundaryLayer = null;
			}
			elements.controls.style.display = 'none';
			elements.resultsContainer.style.display = 'none';
			elements.searchInput.value = '';
			originalOsmGeojson = null;
			processedGeojson = null;
			osmSearchResults = [];
		},
	};
}

// Export for module systems if available
if (typeof module !== 'undefined' && module.exports) {
	module.exports = { initOsmGeojsonGenerator };
}
