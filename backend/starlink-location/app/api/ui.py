"""UI endpoints for POI and Route management interfaces."""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/ui", tags=["UI"])


@router.get("/pois", response_class=HTMLResponse)
async def poi_management_ui():
    """Serve POI management user interface."""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>POI Management</title>
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }

            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }

            .container {
                max-width: 1400px;
                margin: 0 auto;
                background: white;
                border-radius: 12px;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                overflow: hidden;
            }

            .header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                text-align: center;
            }

            .header h1 {
                font-size: 2.5em;
                margin-bottom: 10px;
                text-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
            }

            .header p {
                opacity: 0.9;
                font-size: 1.1em;
            }

            .content {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 30px;
                padding: 30px;
                max-height: 70vh;
                overflow-y: auto;
            }

            @media (max-width: 1024px) {
                .content {
                    grid-template-columns: 1fr;
                    max-height: none;
                }
            }

            .section {
                background: #f8f9fa;
                border-radius: 8px;
                padding: 25px;
                border: 1px solid #e0e0e0;
            }

            .section h2 {
                color: #333;
                margin-bottom: 20px;
                font-size: 1.5em;
                border-bottom: 2px solid #667eea;
                padding-bottom: 10px;
            }

            .form-group {
                margin-bottom: 20px;
                display: flex;
                flex-direction: column;
            }

            .help-text {
                font-size: 0.85em;
                color: #666;
                margin-top: 6px;
            }

            .inline-checkbox {
                display: flex;
                align-items: flex-start;
                gap: 12px;
            }

            .inline-checkbox input[type="checkbox"] {
                width: auto;
                margin-top: 2px;
            }

            .inline-checkbox label {
                margin-bottom: 0;
                font-weight: 600;
                color: #333;
                display: flex;
                align-items: center;
                gap: 10px;
            }

            .help-text {
                font-size: 0.85em;
                color: #666;
                margin-top: 6px;
            }

            .inline-checkbox {
                display: flex;
                align-items: flex-start;
                gap: 12px;
            }

            .inline-checkbox input[type="checkbox"] {
                width: auto;
                margin-top: 2px;
            }

            .inline-checkbox label {
                margin-bottom: 0;
                font-weight: 600;
                color: #333;
                display: flex;
                align-items: center;
                gap: 10px;
            }

            label {
                font-weight: 600;
                color: #333;
                margin-bottom: 8px;
                font-size: 0.95em;
            }

            input[type="text"],
            input[type="number"],
            textarea,
            select {
                padding: 12px;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                font-family: inherit;
                font-size: 1em;
                transition: all 0.3s ease;
            }

            input[type="text"]:focus,
            input[type="number"]:focus,
            textarea:focus,
            select:focus {
                outline: none;
                border-color: #667eea;
                box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
            }

            textarea {
                min-height: 80px;
                resize: vertical;
            }

            .form-row {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 15px;
            }

            .button-group {
                display: flex;
                gap: 12px;
                margin-top: 25px;
                flex-wrap: wrap;
            }

            button {
                padding: 12px 24px;
                border: none;
                border-radius: 6px;
                font-size: 1em;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.3s ease;
                flex: 1;
                min-width: 120px;
            }

            .btn-primary {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }

            .btn-primary:hover {
                transform: translateY(-2px);
                box-shadow: 0 8px 20px rgba(102, 126, 234, 0.3);
            }

            .btn-secondary {
                background: #e0e0e0;
                color: #333;
            }

            .btn-secondary:hover {
                background: #d0d0d0;
            }

            .btn-danger {
                background: #dc3545;
                color: white;
                flex: 0;
            }

            .btn-danger:hover {
                background: #c82333;
                transform: translateY(-2px);
            }

            .map-container {
                height: 400px;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                margin-top: 10px;
                position: relative;
            }

            #map {
                width: 100%;
                height: 100%;
                border-radius: 6px;
            }

            .map-hint {
                color: #666;
                font-size: 0.85em;
                margin-top: 8px;
                font-style: italic;
            }

            .poi-list {
                max-height: 500px;
                overflow-y: auto;
            }

            .poi-item {
                background: white;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                padding: 15px;
                margin-bottom: 12px;
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                transition: all 0.3s ease;
                cursor: pointer;
            }

            .poi-item:hover {
                border-color: #667eea;
                box-shadow: 0 4px 12px rgba(102, 126, 234, 0.1);
            }

            .poi-info h3 {
                color: #333;
                margin-bottom: 5px;
                font-size: 1.1em;
            }

            .poi-details {
                color: #666;
                font-size: 0.85em;
                line-height: 1.4;
            }

            .poi-coords {
                background: #f0f0f0;
                padding: 8px 12px;
                border-radius: 4px;
                font-family: monospace;
                font-size: 0.8em;
                margin-top: 5px;
            }

            .poi-actions {
                display: flex;
                gap: 8px;
                flex-shrink: 0;
            }

            .poi-actions button {
                padding: 8px 12px;
                font-size: 0.85em;
                min-width: auto;
                flex: 0;
            }

            .filter-row {
                display: flex;
                align-items: center;
                gap: 12px;
                margin-bottom: 15px;
            }

            .filter-row select {
                padding: 6px 12px;
                border: 1px solid #d9dde5;
                border-radius: 6px;
                background: white;
                font-size: 0.95em;
            }

            .badge {
                display: inline-block;
                background: #667eea;
                color: white;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 0.75em;
                font-weight: 600;
                margin-top: 5px;
            }

            .route-badge {
                background: #2dce89;
            }

            .empty-state {
                text-align: center;
                padding: 40px 20px;
                color: #999;
            }

            .empty-state p {
                font-size: 1.1em;
                margin-bottom: 10px;
            }

            .alert {
                padding: 15px;
                border-radius: 6px;
                margin-bottom: 20px;
                font-weight: 500;
            }

            .alert-success {
                background: #d4edda;
                color: #155724;
                border: 1px solid #c3e6cb;
            }

            .alert-error {
                background: #f8d7da;
                color: #721c24;
                border: 1px solid #f5c6cb;
            }

            .alert-info {
                background: #d1ecf1;
                color: #0c5460;
                border: 1px solid #bee5eb;
            }

            .loading {
                display: inline-block;
                width: 20px;
                height: 20px;
                border: 3px solid #f3f3f3;
                border-top: 3px solid #667eea;
                border-radius: 50%;
                animation: spin 1s linear infinite;
            }

            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }

            .status-text {
                font-size: 0.9em;
                color: #666;
                margin-top: 10px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🗺️ POI Management</h1>
                <p>Create, edit, and delete Points of Interest for your Starlink terminal tracking</p>
            </div>

            <div class="content">
                <!-- Form Section -->
                <div class="section">
                    <h2>Add/Edit POI</h2>
                    <div id="alerts"></div>
                    <form id="poiForm">
                        <div class="form-group">
                            <label for="poiName">Name *</label>
                            <input type="text" id="poiName" required placeholder="e.g., JFK Airport">
                        </div>

                        <div class="form-row">
                            <div class="form-group">
                                <label for="poiLatitude">Latitude *</label>
                                <input type="number" id="poiLatitude" step="0.00001" required placeholder="40.6413">
                            </div>
                            <div class="form-group">
                                <label for="poiLongitude">Longitude *</label>
                                <input type="number" id="poiLongitude" step="0.00001" required placeholder="-73.7781">
                            </div>
                        </div>

                        <div class="form-row">
                            <div class="form-group">
                                <label for="poiCategory">Category *</label>
                                <select id="poiCategory" required>
                                    <option value="">Select a category</option>
                                    <option value="airport">Airport</option>
                                    <option value="city">City</option>
                                    <option value="landmark">Landmark</option>
                                    <option value="waypoint">Waypoint</option>
                                    <option value="departure">Departure</option>
                                    <option value="arrival">Arrival</option>
                                    <option value="alternate">Alternate</option>
                                    <option value="satellite">Satellite</option>
                                    <option value="other">Other</option>
                                </select>
                            </div>
                            <div class="form-group">
                                <label for="poiIcon">Icon</label>
                                <input type="text" id="poiIcon" placeholder="auto-assigned" disabled>
                            </div>
                        </div>

                        <div class="form-group">
                            <label for="poiDescription">Description</label>
                            <textarea id="poiDescription" placeholder="Optional description..."></textarea>
                        </div>

                        <div class="form-group">
                            <label for="poiRoute">Route Association</label>
                            <select id="poiRoute">
                                <option value="">Global (no route)</option>
                            </select>
                            <p class="help-text">Imported route POIs only display when their route is active.</p>
                        </div>

                        <div class="form-group">
                            <label>Click on map to set coordinates</label>
                            <div class="map-container">
                                <div id="map"></div>
                            </div>
                            <p class="map-hint">📍 Click anywhere on the map to set latitude and longitude</p>
                        </div>

                        <div class="button-group">
                            <button type="submit" class="btn-primary" id="submitBtn">Create POI</button>
                            <button type="reset" class="btn-secondary">Clear</button>
                            <button type="button" class="btn-danger" id="deleteBtn" style="display: none;">Delete</button>
                        </div>
                        <p class="status-text" id="statusText"></p>
                    </form>
                </div>

                <!-- POI List Section -->
                <div class="section">
                    <h2>POIs (<span id="poiCount">0</span>)</h2>
                    <div class="filter-row">
                        <label for="poiRouteFilter">Filter</label>
                        <select id="poiRouteFilter">
                            <option value="all">All routes</option>
                            <option value="global">Global only</option>
                        </select>
                    </div>
                    <div class="poi-list" id="poiList">
                        <div class="empty-state">
                            <p>No POIs yet</p>
                            <p style="font-size: 0.9em;">Create your first POI using the form</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <script>
            // Global state
            let map = null;
            let mapMarker = null;
            let currentEditId = null;
            let poiData = [];
            let routeOptions = [];
            const routeLookup = new Map();
            let currentPOIRouteFilter = 'all';

            // Map initialization
            function initMap() {
                map = L.map('map').setView([40.7128, -74.0060], 4);
                L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                    attribution: '© OpenStreetMap contributors',
                    maxZoom: 19
                }).addTo(map);

                // Handle map clicks for coordinate selection
                map.on('click', (e) => {
                    const lat = e.latlng.lat.toFixed(5);
                    const lng = e.latlng.lng.toFixed(5);

                    document.getElementById('poiLatitude').value = lat;
                    document.getElementById('poiLongitude').value = lng;

                    updateMapMarker(parseFloat(lat), parseFloat(lng));
                });
            }

            function updateMapMarker(lat, lng) {
                if (mapMarker) {
                    mapMarker.setLatLng([lat, lng]);
                } else {
                    mapMarker = L.marker([lat, lng], {
                        draggable: true
                    }).addTo(map);

                    mapMarker.on('drag', (e) => {
                        const latlng = e.target.getLatLng();
                        document.getElementById('poiLatitude').value = latlng.lat.toFixed(5);
                        document.getElementById('poiLongitude').value = latlng.lng.toFixed(5);
                    });
                }
                map.flyTo([lat, lng], 10);
            }

            // Auto-assign icon based on category
            document.getElementById('poiCategory').addEventListener('change', (e) => {
                const iconMap = {
                    'airport': 'airport',
                    'city': 'city',
                    'landmark': 'landmark',
                    'waypoint': 'waypoint',
                    'other': 'star',
                    'departure': 'airport',
                    'arrival': 'flag',
                    'alternate': 'star',
                    'satellite': 'channel'
                };
                document.getElementById('poiIcon').value = iconMap[e.target.value] || 'star';
            });

            async function loadRoutesForPoiForm(preserveSelection = true) {
                try {
                    const response = await fetch('/api/routes');
                    if (!response.ok) throw new Error('Failed to load routes');

                    const data = await response.json();
                    routeOptions = data.routes || [];
                    const routeSelect = document.getElementById('poiRoute');
                    const filterSelect = document.getElementById('poiRouteFilter');
                    const previousRouteValue = preserveSelection && routeSelect ? routeSelect.value : '';
                    const previousRouteLabel = preserveSelection && routeSelect && previousRouteValue
                        ? (Array.from(routeSelect.options).find(option => option.value === previousRouteValue)?.textContent || previousRouteValue)
                        : '';
                    const previousFilterValue = preserveSelection && filterSelect ? filterSelect.value : currentPOIRouteFilter;

                    routeLookup.clear();
                    for (const route of routeOptions) {
                        routeLookup.set(route.id, route.name || route.id);
                    }

                    if (routeSelect) {
                        const routeOptionsHtml = [
                            '<option value="">Global (no route)</option>',
                            ...routeOptions.map(route => `<option value="${route.id}">${route.name || route.id}</option>`)
                        ];
                        routeSelect.innerHTML = routeOptionsHtml.join('');
                        if (previousRouteValue) {
                            if (!routeLookup.has(previousRouteValue) && previousRouteLabel) {
                                const fallbackOption = document.createElement('option');
                                fallbackOption.value = previousRouteValue;
                                fallbackOption.textContent = previousRouteLabel;
                                routeSelect.appendChild(fallbackOption);
                                routeLookup.set(previousRouteValue, previousRouteLabel);
                            }
                            if (routeLookup.has(previousRouteValue)) {
                                routeSelect.value = previousRouteValue;
                            } else {
                                routeSelect.value = '';
                            }
                        } else {
                            routeSelect.value = '';
                        }
                    }

                    if (filterSelect) {
                        const filterOptionsHtml = [
                            '<option value="all">All routes</option>',
                            '<option value="global">Global only</option>',
                            ...routeOptions.map(route => `<option value="${route.id}">${route.name || route.id}</option>`)
                        ];
                        filterSelect.innerHTML = filterOptionsHtml.join('');
                        if (
                            previousFilterValue === 'all' ||
                            previousFilterValue === 'global' ||
                            routeLookup.has(previousFilterValue)
                        ) {
                            filterSelect.value = previousFilterValue;
                        } else {
                            filterSelect.value = 'all';
                            currentPOIRouteFilter = 'all';
                        }
                    }
                } catch (error) {
                    console.error('Failed to load routes for POI form:', error);
                }
            }

            // Load POIs
            async function loadPOIs() {
                await loadRoutesForPoiForm(true);
                try {
                    let requestUrl = '/api/pois';
                    let filterGlobals = false;

                    if (currentPOIRouteFilter === 'global') {
                        filterGlobals = true;
                    } else if (currentPOIRouteFilter !== 'all') {
                        requestUrl = `/api/pois?route_id=${encodeURIComponent(currentPOIRouteFilter)}`;
                    }

                    const response = await fetch(requestUrl);
                    if (!response.ok) throw new Error('Failed to load POIs');

                    const data = await response.json();
                    let pois = data.pois || [];

                    if (filterGlobals) {
                        pois = pois.filter(poi => !poi.route_id);
                    }

                    poiData = pois.map(poi => {
                        const routeLabel = poi.route_id ? (routeLookup.get(poi.route_id) || poi.route_id) : 'Global';
                        return { ...poi, routeLabel };
                    });

                    document.getElementById('poiCount').textContent = poiData.length;

                    const poiList = document.getElementById('poiList');
                    if (poiData.length === 0) {
                        poiList.innerHTML = `
                            <div class="empty-state">
                                <p>No POIs yet</p>
                                <p style="font-size: 0.9em;">Create your first POI using the form</p>
                            </div>
                        `;
                    } else {
                        poiList.innerHTML = poiData.map(poi => `
                            <div class="poi-item" onclick="editPOI('${poi.id}')">
                                <div class="poi-info">
                                    <h3>${poi.name}</h3>
                                    <div class="poi-details">
                                        <span class="badge">${poi.category}</span>
                                        <span class="badge route-badge">${poi.routeLabel}</span>
                                        <div class="poi-coords">
                                            ${poi.latitude.toFixed(4)}, ${poi.longitude.toFixed(4)}
                                        </div>
                                    </div>
                                </div>
                                <div class="poi-actions">
                                    <button class="btn-secondary" onclick="event.stopPropagation(); editPOI('${poi.id}')">Edit</button>
                                    <button class="btn-danger" onclick="event.stopPropagation(); deletePOI('${poi.id}')">Delete</button>
                                </div>
                            </div>
                        `).join('');
                    }
                } catch (error) {
                    showAlert('Failed to load POIs: ' + error.message, 'error');
                }
            }

            // Edit POI
            function editPOI(id) {
                const poi = poiData.find(p => p.id === id);
                if (!poi) return;

                currentEditId = id;
                document.getElementById('poiName').value = poi.name;
                document.getElementById('poiLatitude').value = poi.latitude;
                document.getElementById('poiLongitude').value = poi.longitude;
                document.getElementById('poiCategory').value = poi.category;
                document.getElementById('poiIcon').value = poi.icon;
                document.getElementById('poiDescription').value = poi.description || '';
                const routeSelect = document.getElementById('poiRoute');
                if (poi.route_id) {
                    if (!routeLookup.has(poi.route_id)) {
                        const option = document.createElement('option');
                        option.value = poi.route_id;
                        option.textContent = poi.routeLabel || poi.route_id;
                        routeSelect.appendChild(option);
                        routeLookup.set(poi.route_id, option.textContent);
                    }
                    routeSelect.value = poi.route_id;
                } else {
                    routeSelect.value = '';
                }

                updateMapMarker(poi.latitude, poi.longitude);

                // Update button states
                document.getElementById('submitBtn').textContent = 'Update POI';
                document.getElementById('deleteBtn').style.display = 'flex';

                // Scroll to form
                document.querySelector('.section').scrollIntoView({ behavior: 'smooth', block: 'start' });
            }

            // Delete POI
            async function deletePOI(id) {
                const poi = poiData.find(p => p.id === id);
                if (!poi || !confirm(`Delete POI "${poi.name}"? This cannot be undone.`)) return;

                try {
                    const response = await fetch(`/api/pois/${id}`, { method: 'DELETE' });
                    if (!response.ok) throw new Error('Delete failed');

                    showAlert(`POI "${poi.name}" deleted successfully`, 'success');
                    loadPOIs();
                } catch (error) {
                    showAlert('Failed to delete POI: ' + error.message, 'error');
                }
            }

            // Form submission
            document.getElementById('poiForm').addEventListener('submit', async (e) => {
                e.preventDefault();

                const submitBtn = document.getElementById('submitBtn');
                const originalText = submitBtn.textContent;
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<span class="loading"></span>';

                try {
                    const nameValue = document.getElementById('poiName').value.trim();
                    const latitudeValue = parseFloat(document.getElementById('poiLatitude').value);
                    const longitudeValue = parseFloat(document.getElementById('poiLongitude').value);
                    const categoryValue = document.getElementById('poiCategory').value;
                    const routeValue = document.getElementById('poiRoute').value;

                    const poiPayload = {
                        name: nameValue,
                        latitude: latitudeValue,
                        longitude: longitudeValue,
                        category: categoryValue,
                        icon: document.getElementById('poiIcon').value,
                        description: document.getElementById('poiDescription').value || null,
                        route_id: routeValue ? routeValue : null
                    };

                    if (
                        !poiPayload.name ||
                        !Number.isFinite(poiPayload.latitude) ||
                        !Number.isFinite(poiPayload.longitude) ||
                        !poiPayload.category
                    ) {
                        throw new Error('Please fill in all required fields');
                    }

                    const url = currentEditId ? `/api/pois/${currentEditId}` : '/api/pois';
                    const method = currentEditId ? 'PUT' : 'POST';

                    const response = await fetch(url, {
                        method,
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(poiPayload)
                    });

                    if (!response.ok) {
                        const error = await response.json();
                        throw new Error(error.detail || 'Operation failed');
                    }

                    const action = currentEditId ? 'updated' : 'created';
                    showAlert(`POI "${poiPayload.name}" ${action} successfully`, 'success');

                    // Reset form
                    document.getElementById('poiForm').reset();
                    currentEditId = null;
                    document.getElementById('submitBtn').textContent = 'Create POI';
                    document.getElementById('deleteBtn').style.display = 'none';
                    document.getElementById('poiRoute').value = '';
                    if (mapMarker) {
                        map.removeLayer(mapMarker);
                        mapMarker = null;
                    }

                    // Reload POI list
                    await loadPOIs();
                } catch (error) {
                    showAlert('Error: ' + error.message, 'error');
                } finally {
                    submitBtn.disabled = false;
                    submitBtn.textContent = originalText;
                }
            });

            // Delete button handler
            document.getElementById('deleteBtn').addEventListener('click', () => {
                if (currentEditId) {
                    deletePOI(currentEditId);
                }
            });

            document.getElementById('poiRouteFilter').addEventListener('change', async (e) => {
                currentPOIRouteFilter = e.target.value;
                await loadPOIs();
            });

            // Show alert
            function showAlert(message, type = 'info') {
                const alertsDiv = document.getElementById('alerts');
                const alertDiv = document.createElement('div');
                alertDiv.className = `alert alert-${type}`;
                alertDiv.textContent = message;

                alertsDiv.appendChild(alertDiv);
                setTimeout(() => alertDiv.remove(), 4000);
            }

            // Initialize on load
            document.addEventListener('DOMContentLoaded', async () => {
                initMap();
                await loadRoutesForPoiForm(false);
                await loadPOIs();

                // Refresh POI list every 5 seconds
                setInterval(loadPOIs, 5000);
            });
        </script>
    </body>
    </html>
    """


@router.get("/routes", response_class=HTMLResponse)
async def route_management_ui():
    """Serve Route management user interface."""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Route Management</title>
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }

            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }

            .container {
                max-width: 1400px;
                margin: 0 auto;
                background: white;
                border-radius: 12px;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                overflow: hidden;
            }

            .header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                text-align: center;
            }

            .header h1 {
                font-size: 2.5em;
                margin-bottom: 10px;
                text-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
            }

            .header p {
                opacity: 0.9;
                font-size: 1.1em;
            }

            .content {
                display: grid;
                grid-template-columns: 1fr 2fr;
                gap: 30px;
                padding: 30px;
                max-height: 70vh;
                overflow-y: auto;
            }

            @media (max-width: 1024px) {
                .content {
                    grid-template-columns: 1fr;
                    max-height: none;
                }
            }

            .section {
                background: #f8f9fa;
                border-radius: 8px;
                padding: 25px;
                border: 1px solid #e0e0e0;
            }

            .section h2 {
                color: #333;
                margin-bottom: 20px;
                font-size: 1.5em;
                border-bottom: 2px solid #667eea;
                padding-bottom: 10px;
            }

            .form-group {
                margin-bottom: 20px;
                display: flex;
                flex-direction: column;
            }

            label {
                font-weight: 600;
                color: #333;
                margin-bottom: 8px;
                font-size: 0.95em;
            }

            input[type="text"],
            input[type="file"],
            textarea,
            select {
                padding: 12px;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                font-family: inherit;
                font-size: 1em;
                transition: all 0.3s ease;
            }

            input[type="text"]:focus,
            input[type="file"]:focus,
            textarea:focus,
            select:focus {
                outline: none;
                border-color: #667eea;
                box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
            }

            textarea {
                min-height: 80px;
                resize: vertical;
            }

            .file-input-wrapper {
                position: relative;
                overflow: hidden;
                display: inline-block;
            }

            input[type="file"] {
                position: absolute;
                left: -9999px;
            }

            .file-input-label {
                display: inline-block;
                padding: 12px 24px;
                background: #667eea;
                color: white;
                border-radius: 6px;
                cursor: pointer;
                transition: all 0.3s ease;
                font-weight: 600;
            }

            .file-input-label:hover {
                background: #5568d3;
                transform: translateY(-2px);
            }

            .file-name {
                margin-top: 8px;
                color: #666;
                font-size: 0.9em;
            }

            .button-group {
                display: flex;
                gap: 12px;
                margin-top: 25px;
                flex-wrap: wrap;
            }

            button {
                padding: 12px 24px;
                border: none;
                border-radius: 6px;
                font-size: 1em;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.3s ease;
                flex: 1;
                min-width: 120px;
            }

            .btn-primary {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }

            .btn-primary:hover {
                transform: translateY(-2px);
                box-shadow: 0 8px 20px rgba(102, 126, 234, 0.3);
            }

            .btn-primary:disabled {
                opacity: 0.6;
                cursor: not-allowed;
                transform: none;
            }

            .btn-secondary {
                background: #e0e0e0;
                color: #333;
            }

            .btn-secondary:hover {
                background: #d0d0d0;
            }

            .btn-danger {
                background: #dc3545;
                color: white;
                flex: 0;
                padding: 8px 16px;
                font-size: 0.9em;
            }

            .btn-danger:hover {
                background: #c82333;
                transform: translateY(-2px);
            }

            .btn-small {
                padding: 8px 12px;
                font-size: 0.85em;
                min-width: auto;
                flex: 0;
            }

            .route-table {
                width: 100%;
                border-collapse: collapse;
                background: white;
                border-radius: 6px;
                overflow: hidden;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            }

            .route-table thead {
                background: #f0f0f0;
            }

            .route-table th {
                padding: 15px;
                text-align: left;
                font-weight: 600;
                color: #333;
                border-bottom: 2px solid #e0e0e0;
            }

            .route-table td {
                padding: 15px;
                border-bottom: 1px solid #e0e0e0;
            }

            .route-table tbody tr:hover {
                background: #f9f9f9;
            }

            .route-table tbody tr.active-route {
                background: #f0f8ff;
                border-left: 4px solid #667eea;
            }

            .route-name {
                font-weight: 500;
                color: #333;
            }

            .route-distance {
                color: #666;
                font-size: 0.9em;
            }

            .route-actions {
                display: flex;
                gap: 8px;
            }

            .badge {
                display: inline-block;
                background: #28a745;
                color: white;
                padding: 4px 12px;
                border-radius: 4px;
                font-size: 0.75em;
                font-weight: 600;
            }

            .empty-state {
                text-align: center;
                padding: 40px 20px;
                color: #999;
            }

            .empty-state p {
                font-size: 1.1em;
                margin-bottom: 10px;
            }

            .alert {
                padding: 15px;
                border-radius: 6px;
                margin-bottom: 20px;
                font-weight: 500;
            }

            .alert-success {
                background: #d4edda;
                color: #155724;
                border: 1px solid #c3e6cb;
            }

            .alert-error {
                background: #f8d7da;
                color: #721c24;
                border: 1px solid #f5c6cb;
            }

            .alert-info {
                background: #d1ecf1;
                color: #0c5460;
                border: 1px solid #bee5eb;
            }

            .loading {
                display: inline-block;
                width: 20px;
                height: 20px;
                border: 3px solid #f3f3f3;
                border-top: 3px solid #667eea;
                border-radius: 50%;
                animation: spin 1s linear infinite;
            }

            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }

            .status-text {
                font-size: 0.9em;
                color: #666;
                margin-top: 10px;
            }

            .route-list {
                max-height: 600px;
                overflow-y: auto;
            }

            .modal {
                display: none;
                position: fixed;
                z-index: 1000;
                left: 0;
                top: 0;
                width: 100%;
                height: 100%;
                background-color: rgba(0, 0, 0, 0.4);
                animation: fadeIn 0.3s ease;
            }

            .modal.show {
                display: block;
            }

            @keyframes fadeIn {
                from { opacity: 0; }
                to { opacity: 1; }
            }

            .modal-content {
                background-color: white;
                margin: 10% auto;
                padding: 30px;
                border-radius: 12px;
                width: 90%;
                max-width: 600px;
                box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
                animation: slideIn 0.3s ease;
            }

            @keyframes slideIn {
                from {
                    transform: translateY(-50px);
                    opacity: 0;
                }
                to {
                    transform: translateY(0);
                    opacity: 1;
                }
            }

            .modal-header {
                margin-bottom: 20px;
                border-bottom: 2px solid #667eea;
                padding-bottom: 15px;
            }

            .modal-header h2 {
                color: #333;
                margin: 0;
            }

            .modal-close {
                float: right;
                font-size: 28px;
                font-weight: bold;
                color: #999;
                cursor: pointer;
                border: none;
                background: none;
                padding: 0;
                width: 30px;
                height: 30px;
            }

            .modal-close:hover {
                color: #333;
            }

            .modal-body {
                margin-bottom: 20px;
            }

            .detail-item {
                margin-bottom: 15px;
            }

            .detail-label {
                font-weight: 600;
                color: #667eea;
                font-size: 0.9em;
                text-transform: uppercase;
            }

            .detail-value {
                color: #333;
                margin-top: 5px;
                font-size: 1.05em;
            }

            .modal-footer {
                text-align: right;
                display: flex;
                gap: 12px;
                justify-content: flex-end;
            }

            .modal-footer button {
                flex: 0;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🛣️ Route Management</h1>
                <p>Upload, manage, and activate KML route files for your Starlink terminal tracking</p>
            </div>

            <div class="content">
                <!-- Upload Section -->
                <div class="section">
                    <h2>Upload Route</h2>
                    <div id="alerts"></div>
                    <form id="uploadForm">
                        <div class="form-group">
                            <label for="routeFile">KML File *</label>
                            <div class="file-input-wrapper">
                                <input type="file" id="routeFile" accept=".kml" required>
                                <label for="routeFile" class="file-input-label">Choose KML File</label>
                                <div class="file-name" id="fileName"></div>
                            </div>
                        </div>

                        <div class="form-group">
                            <div class="inline-checkbox">
                                <input type="checkbox" id="importPoisCheckbox" checked>
                                <label for="importPoisCheckbox">Import POIs from KML placemarks</label>
                            </div>
                            <p class="help-text">Automatically create route-specific POIs from Point placemarks during upload.</p>
                        </div>

                        <div class="button-group">
                            <button type="submit" class="btn-primary" id="uploadBtn">Upload Route</button>
                            <button type="reset" class="btn-secondary">Clear</button>
                        </div>
                        <p class="status-text" id="statusText"></p>
                    </form>
                </div>

                <!-- Route List Section -->
                <div class="section">
                    <h2>Routes (<span id="routeCount">0</span>)</h2>
                    <div class="route-list">
                        <table class="route-table" id="routeTable">
                            <thead>
                                <tr>
                                    <th>Name</th>
                                    <th>Points</th>
                                    <th>Distance</th>
                                    <th>Status</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody id="routeTableBody">
                                <tr>
                                    <td colspan="5" class="empty-state">
                                        <p>No routes yet</p>
                                        <p style="font-size: 0.9em;">Upload your first KML file to get started</p>
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>

        <!-- Route Details Modal -->
        <div id="detailsModal" class="modal">
            <div class="modal-content">
                <div class="modal-header">
                    <button class="modal-close" onclick="closeDetailsModal()">&times;</button>
                    <h2 id="detailsTitle">Route Details</h2>
                </div>
                <div class="modal-body" id="detailsBody"></div>
                <div class="modal-footer">
                    <button class="btn-secondary" onclick="closeDetailsModal()">Close</button>
                </div>
            </div>
        </div>

        <!-- Delete Confirmation Modal -->
        <div id="confirmModal" class="modal">
            <div class="modal-content">
                <div class="modal-header">
                    <h2>Confirm Deletion</h2>
                </div>
                <div class="modal-body" id="confirmMessage"></div>
                <div class="modal-footer">
                    <button class="btn-secondary" onclick="closeConfirmModal()">Cancel</button>
                    <button class="btn-danger" onclick="confirmDelete()">Delete</button>
                </div>
            </div>
        </div>

        <script>
            // Global state
            let routeData = [];
            let pendingDeleteId = null;

            // File input change handler
            document.getElementById('routeFile').addEventListener('change', (e) => {
                const fileName = e.target.files[0]?.name || '';
                document.getElementById('fileName').textContent = fileName ? `Selected: ${fileName}` : '';
            });

            // Load routes
            async function loadRoutes() {
                try {
                    const response = await fetch('/api/routes');
                    if (!response.ok) throw new Error('Failed to load routes');

                    const data = await response.json();
                    routeData = data.routes || [];

                    document.getElementById('routeCount').textContent = routeData.length;

                    const tbody = document.getElementById('routeTableBody');
                    if (routeData.length === 0) {
                        tbody.innerHTML = `
                            <tr>
                                <td colspan="5" class="empty-state">
                                    <p>No routes yet</p>
                                    <p style="font-size: 0.9em;">Upload your first KML file to get started</p>
                                </td>
                            </tr>
                        `;
                    } else {
                        tbody.innerHTML = routeData.map(route => `
                            <tr class="${route.is_active ? 'active-route' : ''}">
                                <td class="route-name">${route.name || route.id}</td>
                                <td>${route.point_count}</td>
                                <td class="route-distance" id="distance-${route.id}">Loading...</td>
                                <td>
                                    ${route.is_active ?
                                        '<button class="btn-secondary btn-small" onclick="deactivateRoute()">Deactivate</button>' :
                                        `<button class="btn-secondary btn-small" onclick="activateRoute('${route.id}')">Activate</button>`
                                    }
                                </td>
                                <td class="route-actions">
                                    <button class="btn-secondary btn-small" onclick="showDetails('${route.id}')">Details</button>
                                    <button class="btn-secondary btn-small" onclick="downloadRoute('${route.id}')">Download</button>
                                    <button class="btn-danger btn-small" onclick="confirmDeleteRoute('${route.id}')">Delete</button>
                                </td>
                            </tr>
                        `).join('');

                        // Load distance stats for each route
                        for (const route of routeData) {
                            loadRouteStats(route.id);
                        }
                    }
                } catch (error) {
                    showAlert('Failed to load routes: ' + error.message, 'error');
                }
            }

            // Load route statistics
            async function loadRouteStats(routeId) {
                try {
                    const response = await fetch(`/api/routes/${routeId}/stats`);
                    if (response.ok) {
                        const stats = await response.json();
                        const distanceEl = document.getElementById(`distance-${routeId}`);
                        if (distanceEl) {
                            distanceEl.textContent = stats.distance_km.toFixed(1) + ' km';
                        }
                    }
                } catch (error) {
                    console.error('Failed to load stats for route:', routeId, error);
                }
            }

            // Upload route
            document.getElementById('uploadForm').addEventListener('submit', async (e) => {
                e.preventDefault();

                const fileInput = document.getElementById('routeFile');
                const file = fileInput.files[0];

                if (!file) {
                    showAlert('Please select a KML file', 'error');
                    return;
                }

                if (!file.name.endsWith('.kml')) {
                    showAlert('Please select a .kml file', 'error');
                    return;
                }

                const importPois = document.getElementById('importPoisCheckbox').checked;
                const uploadBtn = document.getElementById('uploadBtn');
                const originalText = uploadBtn.textContent;
                uploadBtn.disabled = true;
                uploadBtn.innerHTML = '<span class="loading"></span>';

                try {
                    const formData = new FormData();
                    formData.append('file', file);

                    const uploadUrl = importPois ? '/api/routes/upload?import_pois=true' : '/api/routes/upload';

                    const response = await fetch(uploadUrl, {
                        method: 'POST',
                        body: formData
                    });

                    if (!response.ok) {
                        const error = await response.json();
                        throw new Error(error.detail || 'Upload failed');
                    }

                    const result = await response.json();
                    let successMessage = `Route "${result.name || result.id}" uploaded successfully.`;
                    if (importPois && typeof result.imported_poi_count === 'number') {
                        successMessage += ` Imported ${result.imported_poi_count} POI${result.imported_poi_count === 1 ? '' : 's'}.`;
                        if (typeof result.skipped_poi_count === 'number' && result.skipped_poi_count > 0) {
                            successMessage += ` Skipped ${result.skipped_poi_count} placemark${result.skipped_poi_count === 1 ? '' : 's'} without coordinates.`;
                        }
                    }
                    showAlert(successMessage, 'success');

                    // Reset form
                    document.getElementById('uploadForm').reset();
                    document.getElementById('fileName').textContent = '';

                    // Wait a bit for watchdog to detect the file
                    await new Promise(resolve => setTimeout(resolve, 200));

                    // Reload routes
                    await loadRoutes();
                } catch (error) {
                    showAlert('Error: ' + error.message, 'error');
                } finally {
                    uploadBtn.disabled = false;
                    uploadBtn.textContent = originalText;
                }
            });

            // Activate route
            async function activateRoute(routeId) {
                try {
                    const response = await fetch(`/api/routes/${routeId}/activate`, {
                        method: 'POST'
                    });

                    if (!response.ok) {
                        const error = await response.json();
                        throw new Error(error.detail || 'Activation failed');
                    }

                    showAlert('Route activated successfully', 'success');
                    await loadRoutes();
                } catch (error) {
                    showAlert('Error: ' + error.message, 'error');
                }
            }

            // Deactivate active route
            async function deactivateRoute() {
                try {
                    const response = await fetch('/api/routes/deactivate', {
                        method: 'POST'
                    });

                    if (!response.ok) {
                        const error = await response.json();
                        throw new Error(error.detail || 'Deactivation failed');
                    }

                    showAlert('Route deactivated successfully', 'success');
                    await loadRoutes();
                } catch (error) {
                    showAlert('Error: ' + error.message, 'error');
                }
            }

            // Download route
            function downloadRoute(routeId) {
                const route = routeData.find(r => r.id === routeId);
                const fileName = route ? `${route.id}.kml` : routeId + '.kml';
                window.location.href = `/api/routes/${routeId}/download`;
            }

            // Show route details
            async function showDetails(routeId) {
                try {
                    const response = await fetch(`/api/routes/${routeId}`);
                    if (!response.ok) throw new Error('Failed to load route details');

                    const route = await response.json();
                    const statsResponse = await fetch(`/api/routes/${routeId}/stats`);
                    const stats = statsResponse.ok ? await statsResponse.json() : null;

                    const detailsTitle = document.getElementById('detailsTitle');
                    const detailsBody = document.getElementById('detailsBody');

                    detailsTitle.textContent = route.name || route.id;

                    let boundsHtml = '';
                    if (stats && stats.bounds) {
                        boundsHtml = `
                            <div class="detail-item">
                                <div class="detail-label">Bounds</div>
                                <div class="detail-value">
                                    Lat: ${stats.bounds.min_lat.toFixed(4)}° to ${stats.bounds.max_lat.toFixed(4)}°<br>
                                    Lon: ${stats.bounds.min_lon.toFixed(4)}° to ${stats.bounds.max_lon.toFixed(4)}°
                                </div>
                            </div>
                        `;
                    }

                    const poiCount = route.poi_count || 0;
                    const poiHtml = `
                        <div class="detail-item">
                            <div class="detail-label">Associated POIs</div>
                            <div class="detail-value">${poiCount} ${poiCount === 1 ? 'POI' : 'POIs'}</div>
                        </div>
                    `;

                    let waypointHtml = '';
                    if (route.waypoints && route.waypoints.length) {
                        const waypointPreview = route.waypoints
                            .slice(0, 5)
                            .map(wp => wp.name || `Waypoint ${wp.order + 1}`)
                            .join(', ');
                        waypointHtml = `
                            <div class="detail-item">
                                <div class="detail-label">Waypoints (${route.waypoints.length})</div>
                                <div class="detail-value">${waypointPreview}${route.waypoints.length > 5 ? ' …' : ''}</div>
                            </div>
                        `;
                    }

                    detailsBody.innerHTML = `
                        <div class="detail-item">
                            <div class="detail-label">Route ID</div>
                            <div class="detail-value">${route.id}</div>
                        </div>
                        <div class="detail-item">
                            <div class="detail-label">Waypoints</div>
                            <div class="detail-value">${route.point_count}</div>
                        </div>
                        ${stats ? `
                            <div class="detail-item">
                                <div class="detail-label">Distance</div>
                                <div class="detail-value">${stats.distance_km.toFixed(1)} km (${stats.distance_meters.toLocaleString()} m)</div>
                            </div>
                        ` : ''}
                        ${boundsHtml}
                        ${poiHtml}
                        ${waypointHtml}
                        <div class="detail-item">
                            <div class="detail-label">Status</div>
                            <div class="detail-value">${route.is_active ? '🟢 Active' : '⚪ Inactive'}</div>
                        </div>
                    `;

                    document.getElementById('detailsModal').classList.add('show');
                } catch (error) {
                    showAlert('Failed to load route details: ' + error.message, 'error');
                }
            }

            // Close details modal
            function closeDetailsModal() {
                document.getElementById('detailsModal').classList.remove('show');
            }

            // Confirm delete route
            async function confirmDeleteRoute(routeId) {
                const summary = routeData.find(r => r.id === routeId);
                pendingDeleteId = routeId;

                let routeName = summary ? (summary.name || summary.id) : routeId;
                let poiCount = 0;

                try {
                    const response = await fetch(`/api/routes/${routeId}`);
                    if (response.ok) {
                        const detail = await response.json();
                        routeName = detail.name || detail.id || routeName;
                        poiCount = detail.poi_count || 0;
                    }
                } catch (error) {
                    console.error('Failed to fetch route details for deletion prompt:', error);
                }

                const poiWarning = poiCount > 0
                    ? `<p style="margin-top: 15px; color: #d9534f;"><strong>⚠️ Warning:</strong> This will also delete ${poiCount} associated POI${poiCount === 1 ? '' : 's'}.</p>`
                    : '<p style="margin-top: 15px;">No associated POIs detected for this route.</p>';

                const confirmMessage = document.getElementById('confirmMessage');
                confirmMessage.innerHTML = `
                    <p>Are you sure you want to delete the route <strong>"${routeName}"</strong>?</p>
                    ${poiWarning}
                `;

                document.getElementById('confirmModal').classList.add('show');
            }

            // Close confirm modal
            function closeConfirmModal() {
                document.getElementById('confirmModal').classList.remove('show');
                pendingDeleteId = null;
            }

            // Confirm delete
            async function confirmDelete() {
                if (!pendingDeleteId) return;

                const routeId = pendingDeleteId;
                closeConfirmModal();

                try {
                    const response = await fetch(`/api/routes/${routeId}`, {
                        method: 'DELETE'
                    });

                    if (!response.ok) {
                        const error = await response.json();
                        throw new Error(error.detail || 'Delete failed');
                    }

                    showAlert('Route deleted successfully', 'success');
                    await loadRoutes();
                } catch (error) {
                    showAlert('Error: ' + error.message, 'error');
                }
            }

            // Close modals on outside click
            window.addEventListener('click', (e) => {
                const detailsModal = document.getElementById('detailsModal');
                const confirmModal = document.getElementById('confirmModal');

                if (e.target === detailsModal) {
                    closeDetailsModal();
                }
                if (e.target === confirmModal) {
                    closeConfirmModal();
                }
            });

            // Show alert
            function showAlert(message, type = 'info') {
                const alertsDiv = document.getElementById('alerts');
                const alertDiv = document.createElement('div');
                alertDiv.className = `alert alert-${type}`;
                alertDiv.textContent = message;

                alertsDiv.appendChild(alertDiv);
                setTimeout(() => alertDiv.remove(), 4000);
            }

            // Initialize on load
            document.addEventListener('DOMContentLoaded', () => {
                loadRoutes();

                // Refresh routes every 5 seconds
                setInterval(loadRoutes, 5000);
            });
        </script>
    </body>
    </html>
    """


@router.get("/mission-planner", response_class=HTMLResponse)
async def mission_planner_ui():
    """Serve Mission Planner user interface for communication planning."""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Mission Planner</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }

            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }

            .container {
                max-width: 1400px;
                margin: 0 auto;
                background: white;
                border-radius: 12px;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                overflow: hidden;
            }

            .header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                text-align: center;
            }

            .header h1 {
                font-size: 2.5em;
                margin-bottom: 10px;
                text-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
            }

            .header p {
                opacity: 0.9;
                font-size: 1.1em;
            }

            .content {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 30px;
                padding: 30px;
                max-height: 70vh;
                overflow-y: auto;
            }

            @media (max-width: 1024px) {
                .content {
                    grid-template-columns: 1fr;
                    max-height: none;
                }
            }

            .section {
                background: #f8f9fa;
                border-radius: 8px;
                padding: 25px;
                border: 1px solid #e0e0e0;
            }

            .section h2 {
                color: #333;
                margin-bottom: 20px;
                font-size: 1.5em;
                border-bottom: 2px solid #667eea;
                padding-bottom: 10px;
            }

            .section h3 {
                color: #333;
                margin-top: 20px;
                margin-bottom: 15px;
                font-size: 1.1em;
                padding-bottom: 5px;
                border-bottom: 1px solid #ddd;
            }

            .form-group {
                margin-bottom: 20px;
                display: flex;
                flex-direction: column;
            }

            label {
                font-weight: 600;
                color: #333;
                margin-bottom: 8px;
                font-size: 0.95em;
            }

            input[type="text"],
            input[type="number"],
            input[type="datetime-local"],
            textarea,
            select {
                padding: 12px;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                font-family: inherit;
                font-size: 1em;
                transition: all 0.3s ease;
            }

            input[type="text"]:focus,
            input[type="number"]:focus,
            input[type="datetime-local"]:focus,
            textarea:focus,
            select:focus {
                outline: none;
                border-color: #667eea;
                box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
            }

            textarea {
                min-height: 80px;
                resize: vertical;
            }

            .form-row {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 15px;
            }

            .form-row-3 {
                display: grid;
                grid-template-columns: 1fr 1fr 1fr;
                gap: 15px;
            }

            .button-group {
                display: flex;
                gap: 12px;
                margin-top: 25px;
                flex-wrap: wrap;
            }

            button {
                padding: 12px 24px;
                border: none;
                border-radius: 6px;
                font-size: 1em;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.3s ease;
                flex: 1;
                min-width: 120px;
            }

            .btn-primary {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }

            .btn-primary:hover {
                transform: translateY(-2px);
                box-shadow: 0 8px 20px rgba(102, 126, 234, 0.3);
            }

            .btn-primary:disabled {
                opacity: 0.6;
                cursor: not-allowed;
                transform: none;
            }

            .btn-secondary {
                background: #e0e0e0;
                color: #333;
            }

            .btn-secondary:hover {
                background: #d0d0d0;
            }

            .btn-small {
                padding: 8px 12px;
                font-size: 0.85em;
                min-width: auto;
                flex: 0;
            }

            .btn-danger {
                background: #dc3545;
                color: white;
                flex: 0;
                padding: 8px 16px;
                font-size: 0.9em;
            }

            .btn-danger:hover {
                background: #c82333;
                transform: translateY(-2px);
            }

            .alert {
                padding: 15px;
                border-radius: 6px;
                margin-bottom: 20px;
                font-weight: 500;
            }

            .alert-success {
                background: #d4edda;
                color: #155724;
                border: 1px solid #c3e6cb;
            }

            .alert-error {
                background: #f8d7da;
                color: #721c24;
                border: 1px solid #f5c6cb;
            }

            .alert-info {
                background: #d1ecf1;
                color: #0c5460;
                border: 1px solid #bee5eb;
            }

            .card {
                background: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 20px;
                margin-bottom: 15px;
            }

            .card-title {
                font-weight: 600;
                color: #333;
                margin-bottom: 12px;
                font-size: 1.05em;
            }

            .card-content {
                color: #666;
                font-size: 0.95em;
                line-height: 1.6;
            }

            .badge {
                display: inline-block;
                background: #667eea;
                color: white;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 0.75em;
                font-weight: 600;
                margin-right: 5px;
            }

            .badge-ka {
                background: #2dce89;
            }

            .badge-x {
                background: #fb6340;
            }

            .badge-ku {
                background: #11cdef;
            }

            .list-item {
                background: white;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                padding: 15px;
                margin-bottom: 12px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }

            .list-item-content {
                flex: 1;
            }

            .list-item-title {
                font-weight: 600;
                color: #333;
                margin-bottom: 5px;
            }

            .list-item-details {
                color: #666;
                font-size: 0.9em;
            }

            .list-item-actions {
                display: flex;
                gap: 8px;
                flex-shrink: 0;
            }

            .empty-state {
                text-align: center;
                padding: 40px 20px;
                color: #999;
            }

            .empty-state p {
                font-size: 1.1em;
                margin-bottom: 10px;
            }

            .loading {
                display: inline-block;
                width: 20px;
                height: 20px;
                border: 3px solid #f3f3f3;
                border-top: 3px solid #667eea;
                border-radius: 50%;
                animation: spin 1s linear infinite;
            }

            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }

            .status-text {
                font-size: 0.9em;
                color: #666;
                margin-top: 10px;
            }

            .tab-buttons {
                display: flex;
                gap: 10px;
                margin-bottom: 20px;
                border-bottom: 2px solid #e0e0e0;
            }

            .tab-button {
                padding: 12px 20px;
                border: none;
                background: none;
                color: #666;
                font-weight: 600;
                cursor: pointer;
                border-bottom: 3px solid transparent;
                transition: all 0.3s ease;
                font-size: 0.95em;
            }

            .tab-button.active {
                color: #667eea;
                border-bottom-color: #667eea;
            }

            .tab-button:hover {
                color: #667eea;
            }

            .tab-content {
                display: none;
            }

            .tab-content.active {
                display: block;
            }

            .info-box {
                background: #e8f0fe;
                border-left: 4px solid #667eea;
                padding: 15px;
                border-radius: 4px;
                margin-bottom: 15px;
                font-size: 0.95em;
                color: #333;
            }

            .help-text {
                font-size: 0.85em;
                color: #666;
                margin-top: 6px;
                font-style: italic;
            }
            .inline-upload-row {
                display: flex;
                gap: 10px;
                align-items: center;
                flex-wrap: wrap;
                margin-top: 10px;
            }
            .file-chip {
                font-size: 0.85em;
                color: #555;
            }
            .checkbox-inline {
                display: flex;
                align-items: center;
                gap: 6px;
                font-size: 0.9em;
                color: #444;
            }
            .select-with-action {
                display: flex;
                gap: 10px;
                align-items: center;
            }
            .select-with-action select {
                flex: 1;
            }
            .modal-content.small {
                max-width: 480px;
            }
            .status-badge {
                display: inline-flex;
                align-items: center;
                padding: 4px 10px;
                border-radius: 999px;
                font-size: 0.85em;
                font-weight: 600;
            }
            .status-active {
                background: #2dce89;
                color: #fff;
            }
            .status-inactive {
                background: #e0e0e0;
                color: #555;
            }
            .modal {
                display: none;
                position: fixed;
                z-index: 2000;
                left: 0;
                top: 0;
                width: 100%;
                height: 100%;
                background: rgba(0, 0, 0, 0.6);
                align-items: center;
                justify-content: center;
                padding: 20px;
            }
            .modal.show {
                display: flex;
            }
            .modal-content {
                background: white;
                border-radius: 10px;
                width: 100%;
                max-width: 560px;
                box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
                animation: fadeIn 0.2s ease-out;
            }
            .modal-header {
                padding: 16px 20px;
                border-bottom: 1px solid #eee;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .modal-header h2 {
                font-size: 1.3em;
                color: #333;
            }
            .modal-close {
                background: none;
                border: none;
                font-size: 1.5em;
                cursor: pointer;
                color: #888;
            }
            .modal-body {
                padding: 20px;
            }
            .modal-footer {
                padding: 16px 20px;
                border-top: 1px solid #eee;
                display: flex;
                justify-content: flex-end;
                gap: 10px;
            }
            .modal-footer button {
                margin: 0;
            }
            @keyframes fadeIn {
                from { opacity: 0; transform: translateY(10px); }
                to { opacity: 1; transform: translateY(0); }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>✈️ Mission Planner</h1>
                <p>Plan satellite communication for your mission with precise X transitions, Ka coverage, AAR windows, and Ku overrides</p>
            </div>

            <div class="content">
                <!-- Mission Creation/Selection -->
                <div class="section">
                    <h2>Mission Setup</h2>
                    <div id="alerts"></div>

                    <div class="form-group">
                        <label for="missionSelect">Select Mission</label>
                        <div class="select-with-action">
                            <select id="missionSelect">
                                <option value="new">+ Create New Mission</option>
                            </select>
                            <button type="button" class="btn-secondary btn-small" id="newMissionBtn">New Mission</button>
                        </div>
                        <div style="margin-top: 8px;">
                            <span id="missionStatusBadge" class="status-badge status-inactive">Draft</span>
                        </div>
                    </div>

                    <form id="missionForm">
                        <div class="form-group">
                            <label for="missionName">Mission Name *</label>
                            <input type="text" id="missionName" required placeholder="e.g., Leg 6 Rev 6 - KSA to Europe">
                            <p class="help-text">Human-readable mission identifier</p>
                        </div>

                        <div class="form-group">
                            <label for="routeId">Flight Route *</label>
                            <select id="routeId" required>
                                <option value="">Select a route...</option>
                            </select>
                            <p class="help-text">Choose an active KML route for timing and waypoint references</p>
                            <div class="inline-upload-row">
                                <button type="button" class="btn-secondary btn-small" id="selectMissionRouteFileBtn">Select KML</button>
                                <span class="file-chip" id="missionRouteFileName">No file selected</span>
                                <label class="checkbox-inline">
                                    <input type="checkbox" id="missionImportPois" checked>
                                    Import POIs from waypoints
                                </label>
                                <button type="button" class="btn-secondary btn-small" id="missionRouteUploadBtn">Upload Route</button>
                            </div>
                            <input type="file" id="missionRouteFile" accept=".kml" style="display: none;">
                            <p class="help-text" id="missionRouteUploadStatus">Upload a new KML if your route is missing.</p>
                        </div>

                        <div class="form-group">
                            <label for="missionDescription">Description</label>
                            <textarea id="missionDescription" placeholder="Optional detailed description..."></textarea>
                        </div>

                        <div class="form-group">
                            <label for="initialXSatellite">Initial X Satellite *</label>
                            <div class="select-with-action">
                                <select id="initialXSatellite" required>
                                    <option value="">Select satellite...</option>
                                </select>
                                <button type="button" class="btn-secondary btn-small add-satellite-btn" data-target-field="initial">+ New Satellite</button>
                            </div>
                            <p class="help-text">Pick from satellite POIs. Add a new one if it is missing.</p>
                        </div>

                        <div class="form-group">
                            <label for="missionNotes">Planning Notes</label>
                            <textarea id="missionNotes" placeholder="Customer briefs, constraints, or special considerations..."></textarea>
                        </div>

                        <div class="button-group">
                            <button type="submit" class="btn-primary" id="saveMissionBtn">Save Mission</button>
                            <button type="button" class="btn-secondary" id="resetMissionBtn">Clear</button>
                            <button type="button" class="btn-secondary" id="toggleMissionBtn" disabled>Activate Mission</button>
                            <button type="button" class="btn-danger" id="deleteMissionBtn" style="display: none;">Delete Mission</button>
                        </div>
                        <div class="button-group">
                            <button type="button" class="btn-secondary" id="recomputeTimelineBtn" disabled>Recompute Timeline</button>
                            <div class="select-with-action" style="flex: 1;">
                                <select id="exportFormatSelect">
                                    <option value="pptx" selected>PPTX (PowerPoint)</option>
                                    <option value="pdf">PDF Brief</option>
                                    <option value="xlsx">XLSX (Multi-sheet)</option>
                                    <option value="csv">CSV (Excel compatible)</option>
                                </select>
                                <button type="button" class="btn-secondary" id="exportTimelineBtn" disabled>Download Timeline</button>
                            </div>
                        </div>
                        <p class="status-text" id="timelineStatusText">Save a mission to enable timeline tools.</p>
                    </form>
                </div>

                <!-- Transport Configuration Tabs -->
                <div class="section">
                    <h2>Transport Configuration</h2>

                    <div class="tab-buttons">
                        <button class="tab-button active" onclick="switchTab('x-transport')">X (Geo)</button>
                        <button class="tab-button" onclick="switchTab('ka-transport')">Ka (Geo)</button>
                        <button class="tab-button" onclick="switchTab('ku-transport')">Ku (LEO)</button>
                        <button class="tab-button" onclick="switchTab('aar-windows')">AAR</button>
                    </div>

                    <!-- X Transport Tab -->
                    <div id="x-transport" class="tab-content active">
                        <h3>X Transport - Satellite Transitions</h3>
                        <div class="info-box">
                            Fixed geostationary satellite. Add transition points with target satellites and optional beam changes.
                        </div>

                        <div class="form-row">
                            <div class="form-group">
                                <label for="xTransitionLat">Transition Latitude *</label>
                                <input type="number" id="xTransitionLat" step="0.00001" placeholder="35.5">
                            </div>
                            <div class="form-group">
                                <label for="xTransitionLon">Transition Longitude *</label>
                                <input type="number" id="xTransitionLon" step="0.00001" placeholder="-120.3">
                            </div>
                        </div>

                        <div class="form-group">
                            <label for="targetXSatellite">Target Satellite *</label>
                            <div class="select-with-action">
                                <select id="targetXSatellite">
                                    <option value="">Select satellite...</option>
                                </select>
                                <button type="button" class="btn-secondary btn-small add-satellite-btn" data-target-field="target">+ New Satellite</button>
                            </div>
                        </div>

                        <button type="button" class="btn-primary" onclick="addXTransition()">Add X Transition</button>

                        <div id="xTransitionsList" style="margin-top: 20px;"></div>
                    </div>

                    <!-- Ka Transport Tab -->
                    <div id="ka-transport" class="tab-content">
                        <h3>Ka Transport - Coverage & Outages</h3>
                        <div class="info-box">
                            Three geostationary satellites (AOR, POR, IOR) with auto-calculated coverage. Optionally define manual outage windows.
                        </div>

                        <div class="form-group">
                            <label for="kaInitialSatellites">Initial Ka Satellites</label>
                            <input type="text" id="kaInitialSatellites" value="AOR, POR, IOR" disabled placeholder="AOR, POR, IOR">
                            <p class="help-text">Read-only. Auto-calculated from coverage.</p>
                        </div>

                        <h3>Manual Outage Windows</h3>
                        <div class="form-group">
                            <label for="kaOutageStart">Outage Start Time</label>
                            <input type="datetime-local" id="kaOutageStart">
                        </div>

                        <div class="form-row">
                            <div class="form-group">
                                <label for="kaOutageDuration">Duration (seconds)</label>
                                <input type="number" id="kaOutageDuration" step="1" min="1" placeholder="600">
                            </div>
                        </div>

                        <button type="button" class="btn-primary" onclick="addKaOutage()">Add Ka Outage</button>

                        <div id="kaOutagesList" style="margin-top: 20px;"></div>
                    </div>

                    <!-- Ku Transport Tab -->
                    <div id="ku-transport" class="tab-content">
                        <h3>Ku Transport - LEO Overrides</h3>
                        <div class="info-box">
                            Ku LEO constellation is always-on by default. Only define outage windows for expected or actual downtime.
                        </div>

                        <div class="form-group">
                            <label for="kuOutageStart">Outage Start Time</label>
                            <input type="datetime-local" id="kuOutageStart">
                        </div>

                        <div class="form-row">
                            <div class="form-group">
                                <label for="kuOutageDuration">Duration (seconds)</label>
                                <input type="number" id="kuOutageDuration" step="1" min="1" placeholder="300">
                            </div>
                            <div class="form-group">
                                <label for="kuOutageReason">Reason (optional)</label>
                                <input type="text" id="kuOutageReason" placeholder="e.g., Planned maintenance">
                            </div>
                        </div>

                        <button type="button" class="btn-primary" onclick="addKuOverride()">Add Ku Outage</button>

                        <div id="kuOverridesList" style="margin-top: 20px;"></div>
                    </div>

                    <!-- AAR Windows Tab -->
                    <div id="aar-windows" class="tab-content">
                        <h3>Air-Refueling (AAR) Windows</h3>
                        <div class="info-box">
                            Define route segments where the X azimuth exclusion zone inverts to 315°–45°. Use waypoint names from your route.
                        </div>

                        <div class="form-row">
                            <div class="form-group">
                                <label for="aarStartWaypoint">Start Waypoint *</label>
                                <select id="aarStartWaypoint">
                                    <option value="">Select waypoint...</option>
                                </select>
                            </div>
                            <div class="form-group">
                                <label for="aarEndWaypoint">End Waypoint *</label>
                                <select id="aarEndWaypoint">
                                    <option value="">Select waypoint...</option>
                                </select>
                            </div>
                        </div>

                        <button type="button" class="btn-primary" onclick="addAARWindow()">Add AAR Window</button>

                        <div id="aarWindowsList" style="margin-top: 20px;"></div>
                    </div>
                </div>
            </div>

            <!-- Export/Import Section -->
            <div style="padding: 30px; border-top: 1px solid #e0e0e0; display: flex; gap: 20px; justify-content: center; flex-wrap: wrap;">
                <button class="btn-secondary" onclick="exportMission()">📥 Export to JSON</button>
                <button class="btn-secondary" onclick="document.getElementById('importFile').click()">📤 Import from JSON</button>
                <input type="file" id="importFile" accept=".json" style="display: none;" onchange="importMission()">
            </div>
        </div>

        <div id="satelliteModal" class="modal">
            <div class="modal-content small">
                <div class="modal-header">
                    <h2 id="satelliteModalTitle">Add Satellite POI</h2>
                    <button class="modal-close" type="button" onclick="closeSatelliteModal()">&times;</button>
                </div>
                <div class="modal-body">
                    <form id="satelliteForm">
                        <div class="form-group">
                            <label for="satelliteName">Satellite Name *</label>
                            <input type="text" id="satelliteName" required placeholder="e.g., X-1">
                        </div>
                        <div class="form-group">
                            <label for="satelliteLongitude">Longitude *</label>
                            <input type="number" step="0.00001" id="satelliteLongitude" required placeholder="0.0">
                        </div>
                        <p class="help-text">Latitude is fixed at 0° for geostationary satellites. New satellites are stored globally as POIs.</p>
                    </form>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn-secondary" id="satelliteModalCancel">Cancel</button>
                    <button type="submit" class="btn-primary" form="satelliteForm" id="saveSatelliteBtn">Save Satellite</button>
                </div>
            </div>
        </div>

        <script>
            // Global state
            let currentMission = null;
            let missions = [];
            let routes = [];
            let currentRouteWaypoints = [];
            let satellitePois = [];
            let missionRouteFile = null;
            let satelliteModalContext = 'initial';
            let selectedInitialSatellite = '';
            let selectedTargetSatellite = '';
            let missionDirty = false;
            let timelineAvailable = false;
            let suppressDirtyEvents = false;
            const DEFAULT_KA_SATELLITES = ["AOR", "POR", "IOR"];

            // Initialize on page load
            document.addEventListener('DOMContentLoaded', async () => {
                await Promise.all([loadMissions(), loadRoutes(), loadSatellitePOIs()]);
                setupEventListeners();
            });

            function generateMissionId() {
                return `mission-${Date.now()}`;
            }

            function createEmptyMission() {
                const initialSatelliteInput = document.getElementById('initialXSatellite');
                const initialSatellite = initialSatelliteInput?.value || '';
                const timestamp = new Date().toISOString();
                return {
                    id: generateMissionId(),
                    name: '',
                    description: null,
                    route_id: '',
                    transports: {
                        initial_x_satellite_id: initialSatellite,
                        initial_ka_satellite_ids: [...DEFAULT_KA_SATELLITES],
                        x_transitions: [],
                        ka_outages: [],
                        aar_windows: [],
                        ku_overrides: []
                    },
                    notes: null,
                    is_active: false,
                    created_at: timestamp,
                    updated_at: timestamp
                };
            }

    function setTimelineAvailability(flag) {
        timelineAvailable = flag;
        updateMissionStatus();
    }

    async function refreshTimelineAvailability() {
        if (!currentMission || !currentMission.id) {
            setTimelineAvailability(false);
            return;
        }
        try {
            const response = await fetch(`/api/missions/${currentMission.id}/timeline`);
            setTimelineAvailability(response.ok);
        } catch (_) {
            setTimelineAvailability(false);
        }
    }

    function updateTimelineStatusMessage() {
        const statusEl = document.getElementById('timelineStatusText');
        if (!statusEl) return;

        if (!currentMission) {
            statusEl.textContent = 'Save a mission to enable timeline tools.';
            return;
        }
        if (missionDirty) {
            statusEl.textContent = 'Save changes before recomputing the timeline.';
            return;
        }
        statusEl.textContent = timelineAvailable
            ? 'Timeline ready for export.'
            : 'Timeline not computed yet. Recompute to refresh segments.';
    }

    function markMissionDirtyFromForm(event) {
        if (suppressDirtyEvents) return;
        const ignoreIds = new Set(['exportFormatSelect']);
        if (!event.target || ignoreIds.has(event.target.id)) {
            return;
        }
        missionDirty = true;
        setTimelineAvailability(false);
        updateMissionStatus();
    }

    function markMissionDirty() {
        missionDirty = true;
        setTimelineAvailability(false);
        updateMissionStatus();
    }

    function resetMissionDirty() {
        missionDirty = false;
        updateMissionStatus();
    }

            // Tab switching
            function switchTab(tabName) {
                document.querySelectorAll('.tab-content').forEach(tab => {
                    tab.classList.remove('active');
                });
                document.querySelectorAll('.tab-button').forEach(btn => {
                    btn.classList.remove('active');
                });

                document.getElementById(tabName).classList.add('active');
                event.target.classList.add('active');
            }

            // Setup event listeners
            function setupEventListeners() {
                document.getElementById('missionForm').addEventListener('submit', saveMission);
                document.getElementById('resetMissionBtn').addEventListener('click', resetForm);
                document.getElementById('deleteMissionBtn').addEventListener('click', deleteMission);
                document.getElementById('missionSelect').addEventListener('change', selectMission);
                document.getElementById('newMissionBtn').addEventListener('click', startNewMissionDraft);
                const toggleBtn = document.getElementById('toggleMissionBtn');
                if (toggleBtn) {
                    toggleBtn.addEventListener('click', toggleMissionState);
                }
                document.getElementById('routeId').addEventListener('change', () => {
                    loadRouteWaypoints();
                    if (!suppressDirtyEvents) {
                        markMissionDirty();
                    }
                });
                document.getElementById('aarStartWaypoint').addEventListener('change', handleAARStartChange);
                document.getElementById('initialXSatellite').addEventListener('change', () => {
                    if (!suppressDirtyEvents) {
                        markMissionDirty();
                    }
                });
                document.getElementById('selectMissionRouteFileBtn').addEventListener('click', () => document.getElementById('missionRouteFile').click());
                document.getElementById('missionRouteFile').addEventListener('change', handleMissionRouteFileChange);
                document.getElementById('missionRouteUploadBtn').addEventListener('click', uploadMissionRoute);
                document.getElementById('initialXSatellite').addEventListener('change', (event) => {
                    selectedInitialSatellite = event.target.value;
                });
                document.getElementById('targetXSatellite').addEventListener('change', (event) => {
                    selectedTargetSatellite = event.target.value;
                });
                document.getElementById('recomputeTimelineBtn').addEventListener('click', recomputeTimeline);
                document.getElementById('exportTimelineBtn').addEventListener('click', exportTimeline);
                document.querySelectorAll('.add-satellite-btn').forEach(button => {
                    button.addEventListener('click', () => openSatelliteModal(button.dataset.targetField));
                });
                document.getElementById('satelliteForm').addEventListener('submit', submitSatelliteForm);
                document.getElementById('satelliteModalCancel').addEventListener('click', closeSatelliteModal);
                document.getElementById('missionForm').addEventListener('input', markMissionDirtyFromForm);

                // Reload missions every 5 seconds
                setInterval(loadMissions, 5000);
                updateMissionStatus();
            }

            function buildMissionDraftFromForm() {
                const name = document.getElementById('missionName').value.trim();
                const routeId = document.getElementById('routeId').value;
                const description = document.getElementById('missionDescription').value || null;
                const notes = document.getElementById('missionNotes').value || null;
                const initialSatellite = document.getElementById('initialXSatellite').value;

                if (!name || !routeId || !initialSatellite) {
                    return null;
                }

                const timestamp = new Date().toISOString();
                return {
                    id: generateMissionId(),
                    name,
                    description,
                    route_id: routeId,
                    transports: {
                        initial_x_satellite_id: initialSatellite,
                        initial_ka_satellite_ids: [...DEFAULT_KA_SATELLITES],
                        x_transitions: [],
                        ka_outages: [],
                        aar_windows: [],
                        ku_overrides: []
                    },
                    notes,
                    is_active: false,
                    created_at: timestamp,
                    updated_at: timestamp
                };
            }

            function ensureMissionDraft() {
                if (currentMission) {
                    return true;
                }
                const draft = buildMissionDraftFromForm();
                if (!draft) {
                    showAlert('Enter mission name, route, and initial X satellite before adding transitions.', 'error');
                    return false;
                }
                currentMission = draft;
                markMissionDirty();
                return true;
            }

    function confirmDiscardIfDirty() {
        if (!missionDirty) return true;
        return confirm('You have unsaved mission changes. Continue and discard them?');
    }

    function updateMissionStatus() {
        const badge = document.getElementById('missionStatusBadge');
        const toggleBtn = document.getElementById('toggleMissionBtn');
        const recomputeBtn = document.getElementById('recomputeTimelineBtn');
        const exportBtn = document.getElementById('exportTimelineBtn');
        if (!badge) return;

        badge.classList.remove('status-active', 'status-inactive');

        if (!currentMission) {
            badge.textContent = 'Draft';
            badge.classList.add('status-inactive');
            if (toggleBtn) {
                toggleBtn.disabled = true;
                toggleBtn.textContent = 'Activate Mission';
            }
            if (recomputeBtn) {
                recomputeBtn.disabled = true;
            }
            if (exportBtn) {
                exportBtn.disabled = true;
            }
            updateTimelineStatusMessage();
            return;
        }

        if (missionDirty) {
            badge.textContent = 'Unsaved Changes';
            badge.classList.add('status-inactive');
        } else if (currentMission.is_active) {
            badge.textContent = 'Active';
            badge.classList.add('status-active');
        } else {
            badge.textContent = 'Saved Draft';
            badge.classList.add('status-inactive');
        }

        if (toggleBtn) {
            toggleBtn.disabled = missionDirty || !currentMission.id;
            toggleBtn.textContent = currentMission.is_active ? 'Deactivate Mission' : 'Activate Mission';
        }
        if (recomputeBtn) {
            recomputeBtn.disabled = missionDirty || !currentMission.id;
        }
        if (exportBtn) {
            exportBtn.disabled = missionDirty || !currentMission.id || !timelineAvailable;
        }
        updateTimelineStatusMessage();
    }

            function findWaypointByName(name) {
                if (!name) return null;
                return currentRouteWaypoints.find(wp => (wp.name || String(wp.order)) === name) || null;
            }

            async function createPoi(payload) {
                const response = await fetch('/api/pois', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                if (!response.ok) {
                    let detail = 'Failed to create POI';
                    try {
                        const errorBody = await response.json();
                        if (errorBody.detail) detail = errorBody.detail;
                    } catch (_) {
                        // ignore parse errors
                    }
                    throw new Error(detail);
                }
                return response.json();
            }

            async function syncMissionPois(mission) {
                if (!mission || !mission.route_id || !mission.id) {
                    return;
                }

                await deleteMissionScopedPois(mission.id);

                const poiPayloads = [];
                const descriptionBase = mission.name ? `Mission ${mission.name}` : mission.id;

                const xTransitions = mission.transports.x_transitions || [];
                let activeXSatellite = mission.transports.initial_x_satellite_id || null;
                xTransitions.forEach((transition, idx) => {
                    if (!Number.isFinite(transition.latitude) || !Number.isFinite(transition.longitude)) {
                        return;
                    }
                    const satelliteName = transition.target_satellite_id || 'Satellite';
                    let poiName;
                    if (transition.is_same_satellite_transition) {
                        poiName = 'X-Band\\nBeam Swap';
                    } else if (activeXSatellite) {
                        poiName = `X-Band\\n${activeXSatellite}→${satelliteName}`;
                    } else {
                        poiName = `X-Band\\n→${satelliteName}`;
                    }
                    poiPayloads.push({
                        name: poiName,
                        latitude: transition.latitude,
                        longitude: transition.longitude,
                        icon: 'satellite',
                        category: 'mission-event',
                        description: `${descriptionBase} | Target: ${satelliteName}`,
                        route_id: mission.route_id,
                        mission_id: mission.id
                    });
                    if (!transition.is_same_satellite_transition && transition.target_satellite_id) {
                        activeXSatellite = transition.target_satellite_id;
                    }
                });

                (mission.transports.aar_windows || []).forEach((window, idx) => {
                    const startWaypoint = findWaypointByName(window.start_waypoint_name);
                    if (startWaypoint && Number.isFinite(startWaypoint.latitude) && Number.isFinite(startWaypoint.longitude)) {
                        poiPayloads.push({
                            name: 'AAR\\nStart',
                            latitude: startWaypoint.latitude,
                            longitude: startWaypoint.longitude,
                            icon: 'aar',
                            category: 'mission-event',
                            description: `${descriptionBase} | AAR window start`,
                            route_id: mission.route_id,
                            mission_id: mission.id
                        });
                    }
                    const endWaypoint = findWaypointByName(window.end_waypoint_name);
                    if (endWaypoint && Number.isFinite(endWaypoint.latitude) && Number.isFinite(endWaypoint.longitude)) {
                        poiPayloads.push({
                            name: 'AAR\\nEnd',
                            latitude: endWaypoint.latitude,
                            longitude: endWaypoint.longitude,
                            icon: 'aar',
                            category: 'mission-event',
                            description: `${descriptionBase} | AAR window end`,
                            route_id: mission.route_id,
                            mission_id: mission.id
                        });
                    }
                });

                if (poiPayloads.length === 0) {
                    return;
                }

                try {
                    const results = await Promise.allSettled(poiPayloads.map(payload => createPoi(payload)));
                    const createdCount = results.filter(r => r.status === 'fulfilled').length;
                    const failedCount = results.length - createdCount;
                    if (createdCount > 0) {
                        showAlert(`Created ${createdCount} mission POI${createdCount === 1 ? '' : 's'}`, 'success');
                    }
                    if (failedCount > 0) {
                        showAlert(`Failed to create ${failedCount} mission POI${failedCount === 1 ? '' : 's'}`, 'error');
                    }
                } catch (error) {
                    showAlert(`Error creating mission POIs: ${error.message}`, 'error');
                }
            }
            async function deleteMissionScopedPois(missionId) {
                if (!missionId) return;
                try {
                    const response = await fetch(`/api/pois?mission_id=${encodeURIComponent(missionId)}`);
                    if (!response.ok) return;
                    const data = await response.json();
                    const pois = data.pois || [];
                    if (pois.length === 0) return;
                    await Promise.allSettled(pois.map(poi => fetch(`/api/pois/${poi.id}`, { method: 'DELETE' })));
                } catch (error) {
                    console.error('Failed to delete mission POIs:', error);
                }
            }

            // Load missions from API
            async function loadMissions() {
                try {
                    const response = await fetch('/api/missions');
                    if (!response.ok) throw new Error('Failed to load missions');

                    const data = await response.json();
                    missions = data.missions || [];

                    const select = document.getElementById('missionSelect');
                    const currentValue = select.value;

                    select.innerHTML = '<option value="new">+ Create New Mission</option>';
                    missions.forEach(mission => {
                        const option = document.createElement('option');
                        option.value = mission.id;
                        option.textContent = mission.name || mission.id;
                        if (mission.is_active) {
                            option.textContent += ' (Active)';
                        }
                        select.appendChild(option);
                    });

                    if (currentValue !== 'new' && missions.some(m => m.id === currentValue)) {
                        select.value = currentValue;
                    } else if (currentMission && missions.some(m => m.id === currentMission.id)) {
                        select.value = currentMission.id;
                    }
                    updateMissionStatus();
                } catch (error) {
                    console.error('Failed to load missions:', error);
                }
            }

            // Load routes from API
            async function loadRoutes() {
                try {
                    const response = await fetch('/api/routes');
                    if (!response.ok) throw new Error('Failed to load routes');

                    const data = await response.json();
                    routes = data.routes || [];

                    const select = document.getElementById('routeId');
                    const previousValue = select.value;
                    const preferredValue = currentMission?.route_id || previousValue || '';

                    select.innerHTML = '<option value="">Select a route...</option>';
                    routes.forEach(route => {
                        const option = document.createElement('option');
                        option.value = route.id;
                        option.textContent = route.name || route.id;
                        select.appendChild(option);
                    });

                    if (preferredValue) {
                        const hasMatch = routes.some(route => route.id === preferredValue);
                        select.value = hasMatch ? preferredValue : '';
                    } else {
                        select.value = '';
                    }

                    if (select.value) {
                        await loadRouteWaypoints();
                    } else {
                        currentRouteWaypoints = [];
                        updateWaypointSelects();
                    }
                } catch (error) {
                    console.error('Failed to load routes:', error);
                    showAlert('Failed to load routes: ' + error.message, 'error');
                }
            }

            // Load waypoints for selected route
            async function loadRouteWaypoints() {
                const routeId = document.getElementById('routeId').value;
                if (!routeId) {
                    currentRouteWaypoints = [];
                    updateWaypointSelects();
                    return;
                }

                try {
                    const response = await fetch(`/api/routes/${routeId}`);
                    if (!response.ok) throw new Error('Failed to load route details');

                    const route = await response.json();
                    currentRouteWaypoints = route.waypoints || [];
                    updateWaypointSelects();
                } catch (error) {
                    console.error('Failed to load waypoints:', error);
                    showAlert('Failed to load route waypoints: ' + error.message, 'error');
                }
            }

            function handleMissionRouteFileChange(event) {
                missionRouteFile = event.target.files[0] || null;
                const label = document.getElementById('missionRouteFileName');
                if (label) {
                    label.textContent = missionRouteFile ? missionRouteFile.name : 'No file selected';
                }
            }

            async function uploadMissionRoute() {
                if (!missionRouteFile) {
                    showAlert('Select a KML file before uploading', 'error');
                    return;
                }

                const uploadBtn = document.getElementById('missionRouteUploadBtn');
                const originalText = uploadBtn.textContent;
                uploadBtn.disabled = true;
                uploadBtn.innerHTML = '<span class="loading"></span>';

                try {
                    const formData = new FormData();
                    formData.append('file', missionRouteFile);

                    const importPois = document.getElementById('missionImportPois').checked;
                    const uploadUrl = importPois ? '/api/routes/upload?import_pois=true' : '/api/routes/upload';

                    const response = await fetch(uploadUrl, {
                        method: 'POST',
                        body: formData
                    });

                    if (!response.ok) {
                        let errorDetail = 'Upload failed';
                        try {
                            const errorBody = await response.json();
                            if (errorBody.detail) errorDetail = errorBody.detail;
                        } catch (parseError) {
                            // ignore JSON parse failure
                        }
                        throw new Error(errorDetail);
                    }

                    const result = await response.json();
                    showAlert(`Route "${result.name || result.id}" uploaded successfully`, 'success');
                    const status = document.getElementById('missionRouteUploadStatus');
                    if (status) {
                        status.textContent = `Last uploaded: ${result.name || result.id}`;
                    }

                    missionRouteFile = null;
                    document.getElementById('missionRouteFile').value = '';
                    document.getElementById('missionRouteFileName').textContent = 'No file selected';

                    await loadRoutes();
                    document.getElementById('routeId').value = result.id;
                    await loadRouteWaypoints();
                } catch (error) {
                    const status = document.getElementById('missionRouteUploadStatus');
                    if (status) {
                        status.textContent = `Upload failed: ${error.message}`;
                    }
                    showAlert(error.message, 'error');
                } finally {
                    uploadBtn.disabled = false;
                    uploadBtn.textContent = originalText;
                }
            }

            async function loadSatellitePOIs() {
                try {
                    const response = await fetch('/api/pois');
                    if (!response.ok) throw new Error('Failed to load POIs');

                    const data = await response.json();
                    const pois = data.pois || [];
                    satellitePois = pois
                        .filter(poi => {
                            const category = (poi.category || '').toLowerCase();
                            const icon = (poi.icon || '').toLowerCase();
                            return category.includes('satellite') || icon.includes('satellite');
                        })
                        .sort((a, b) => a.name.localeCompare(b.name));

                    populateSatelliteSelects();
                } catch (error) {
                    console.error('Failed to load satellite POIs:', error);
                    satellitePois = [];
                    populateSatelliteSelects();
                }
            }

            function populateSatelliteSelects() {
                const selects = [
                    { element: document.getElementById('initialXSatellite'), selected: selectedInitialSatellite },
                    { element: document.getElementById('targetXSatellite'), selected: selectedTargetSatellite }
                ];

                selects.forEach(({ element, selected }) => {
                    if (!element) return;
                    const previousValue = selected || element.value;
                    element.innerHTML = '';

                    const placeholder = document.createElement('option');
                    placeholder.value = '';
                    placeholder.textContent = satellitePois.length
                        ? 'Select satellite...'
                        : 'No satellites available - add one';
                    element.appendChild(placeholder);

                    satellitePois.forEach(poi => {
                        const option = document.createElement('option');
                        option.value = poi.name;
                        option.textContent = poi.name;
                        option.dataset.poiId = poi.id;
                        option.dataset.latitude = poi.latitude;
                        option.dataset.longitude = poi.longitude;
                        element.appendChild(option);
                    });

                    if (previousValue) {
                        ensureSatelliteOption(element, previousValue);
                        element.value = previousValue;
                    } else {
                        element.value = '';
                    }
                });
            }

            function ensureSatelliteOption(selectElement, value) {
                if (!selectElement || !value) return;
                const exists = Array.from(selectElement.options).some(option => option.value === value);
                if (!exists) {
                    const fallback = document.createElement('option');
                    fallback.value = value;
                    fallback.textContent = `${value} (custom)`;
                    selectElement.appendChild(fallback);
                }
            }

            function setSatelliteValue(selectId, value) {
                const selectElement = document.getElementById(selectId);
                if (!selectElement) return;
                ensureSatelliteOption(selectElement, value);
                selectElement.value = value || '';

                if (selectId === 'initialXSatellite') {
                    selectedInitialSatellite = value || '';
                } else if (selectId === 'targetXSatellite') {
                    selectedTargetSatellite = value || '';
                }
            }

            function openSatelliteModal(targetField = 'initial') {
                satelliteModalContext = targetField || 'initial';
                const modal = document.getElementById('satelliteModal');
                document.getElementById('satelliteForm').reset();
                const title = document.getElementById('satelliteModalTitle');
                title.textContent = satelliteModalContext === 'target'
                    ? 'Add Target Satellite'
                    : 'Add Satellite POI';
                modal.classList.add('show');
            }

            function closeSatelliteModal() {
                document.getElementById('satelliteModal').classList.remove('show');
                satelliteModalContext = 'initial';
            }

            async function submitSatelliteForm(event) {
                event.preventDefault();

                const name = document.getElementById('satelliteName').value.trim();
                const longitude = parseFloat(document.getElementById('satelliteLongitude').value);
                const latitude = 0;

                if (!name || !Number.isFinite(longitude)) {
                    showAlert('Provide a satellite name and longitude', 'error');
                    return;
                }

                const saveBtn = document.getElementById('saveSatelliteBtn');
                const originalText = saveBtn.textContent;
                saveBtn.disabled = true;
                saveBtn.innerHTML = '<span class="loading"></span>';

                try {
                    const response = await fetch('/api/pois', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            name,
                            latitude,
                            longitude,
                            icon: 'satellite',
                            category: 'satellite',
                            description: 'Created via Mission Planner'
                        })
                    });

                    if (!response.ok) {
                        let errorDetail = 'Failed to create satellite';
                        try {
                            const errorBody = await response.json();
                            if (errorBody.detail) errorDetail = errorBody.detail;
                        } catch (parseError) {
                            // ignore
                        }
                        throw new Error(errorDetail);
                    }

                    const result = await response.json();
                    showAlert(`Satellite "${result.name}" created`, 'success');
                    closeSatelliteModal();
                    await loadSatellitePOIs();

                    if (satelliteModalContext === 'target') {
                        setSatelliteValue('targetXSatellite', result.name);
                    } else {
                        setSatelliteValue('initialXSatellite', result.name);
                    }
                } catch (error) {
                    showAlert(error.message, 'error');
                } finally {
                    saveBtn.disabled = false;
                    saveBtn.textContent = originalText;
                }
            }

            // Update waypoint select dropdowns
            function updateWaypointSelects() {
                const startSelect = document.getElementById('aarStartWaypoint');
                const endSelect = document.getElementById('aarEndWaypoint');

                const currentStart = startSelect.value;
                const currentEnd = endSelect.value;

                startSelect.innerHTML = '<option value="">Select waypoint...</option>';
                endSelect.innerHTML = '<option value="">Select waypoint...</option>';

                currentRouteWaypoints.forEach((wp, idx) => {
                    const orderValue = typeof wp.order === 'number' ? wp.order : idx;

                    const startOption = document.createElement('option');
                    startOption.value = wp.name || wp.order;
                    startOption.textContent = wp.name || `Waypoint ${wp.order + 1}`;
                    startOption.dataset.order = orderValue;
                    startSelect.appendChild(startOption);

                    const endOption = document.createElement('option');
                    endOption.value = wp.name || wp.order;
                    endOption.textContent = wp.name || `Waypoint ${wp.order + 1}`;
                    endOption.dataset.order = orderValue;
                    endSelect.appendChild(endOption);
                });

                if (currentStart) startSelect.value = currentStart;
                if (currentEnd) endSelect.value = currentEnd;

                applyAAREndpointConstraints();
            }

            function getOptionOrder(selectElement, value) {
                if (!value) return null;
                const option = Array.from(selectElement.options).find(opt => opt.value === value);
                if (!option || option.dataset.order === undefined) return null;
                const parsed = Number(option.dataset.order);
                return Number.isFinite(parsed) ? parsed : null;
            }

            function handleAARStartChange() {
                applyAAREndpointConstraints();
            }

            function applyAAREndpointConstraints() {
                const startSelect = document.getElementById('aarStartWaypoint');
                const endSelect = document.getElementById('aarEndWaypoint');
                const startOrder = getOptionOrder(startSelect, startSelect.value);

                Array.from(endSelect.options).forEach(option => {
                    if (!option.dataset.order) {
                        option.disabled = false;
                        option.hidden = false;
                        return;
                    }

                    const optionOrder = Number(option.dataset.order);
                    const shouldDisable = startOrder !== null && optionOrder <= startOrder;
                    option.disabled = shouldDisable;
                    option.hidden = shouldDisable;
                });

                const endOrder = getOptionOrder(endSelect, endSelect.value);
                if (startOrder !== null && endOrder !== null && endOrder <= startOrder) {
                    endSelect.value = '';
                }
            }

            // Select mission
            async function selectMission() {
                const select = document.getElementById('missionSelect');
                const missionId = select.value;

                if (missionId === 'new') {
                    startNewMissionDraft();
                    return;
                }

                try {
                    if (!confirmDiscardIfDirty()) {
                        select.value = currentMission?.id || 'new';
                        return;
                    }
                    const response = await fetch(`/api/missions/${missionId}`);
                    if (!response.ok) throw new Error('Failed to load mission');

                    currentMission = await response.json();
                    populateFormFromMission(currentMission);
                    await refreshTimelineAvailability();
                } catch (error) {
                    showAlert('Failed to load mission: ' + error.message, 'error');
                }
            }

            // Populate form from mission
            function populateFormFromMission(mission) {
                suppressDirtyEvents = true;
                document.getElementById('missionName').value = mission.name;
                document.getElementById('routeId').value = mission.route_id;
                document.getElementById('missionDescription').value = mission.description || '';
                setSatelliteValue('initialXSatellite', mission.transports.initial_x_satellite_id);
                document.getElementById('missionNotes').value = mission.notes || '';

                currentMission = JSON.parse(JSON.stringify(mission));

                // Update transport displays
                renderXTransitions(currentMission.transports.x_transitions);
                renderKaOutages(currentMission.transports.ka_outages);
                renderKuOverrides(currentMission.transports.ku_overrides);
                renderAARWindows(currentMission.transports.aar_windows);

                // Load route waypoints
                loadRouteWaypoints();

                // Show delete button
                document.getElementById('deleteMissionBtn').style.display = 'flex';
                suppressDirtyEvents = false;
                resetMissionDirty();
                const toggleBtn = document.getElementById('toggleMissionBtn');
                if (toggleBtn) {
                    toggleBtn.disabled = missionDirty || !currentMission.id;
                }
                setTimelineAvailability(false);
            }

            // Add X transition
            function addXTransition() {
                const lat = parseFloat(document.getElementById('xTransitionLat').value);
                const lon = parseFloat(document.getElementById('xTransitionLon').value);
                const satellite = document.getElementById('targetXSatellite').value;

                if (!Number.isFinite(lat) || !Number.isFinite(lon) || !satellite) {
                    showAlert('Please fill in required X transition fields', 'error');
                    return;
                }

                if (!ensureMissionDraft()) {
                    return;
                }

                const transitions = currentMission.transports.x_transitions;
                const previousSatellite = transitions.length > 0
                    ? transitions[transitions.length - 1].target_satellite_id
                    : currentMission.transports.initial_x_satellite_id;

                const transition = {
                    id: `x-transition-${Date.now()}`,
                    latitude: lat,
                    longitude: lon,
                    target_satellite_id: satellite,
                    target_beam_id: null,
                    is_same_satellite_transition: previousSatellite === satellite
                };

                transitions.push(transition);
                renderXTransitions(transitions);
                clearXTransitionForm();
                markMissionDirty();
            }

            // Render X transitions
            function renderXTransitions(transitions) {
                const list = document.getElementById('xTransitionsList');
                if (transitions.length === 0) {
                    list.innerHTML = '<p class="empty-state">No X transitions yet</p>';
                    return;
                }

                list.innerHTML = transitions.map(t => `
                    <div class="list-item">
                            <div class="list-item-content">
                                <div class="list-item-title">
                                    <span class="badge badge-x">X</span>
                                ${t.target_satellite_id} ${t.is_same_satellite_transition ? '(beam shift)' : ''}
                            </div>
                            <div class="list-item-details">
                                ${t.latitude.toFixed(4)}°, ${t.longitude.toFixed(4)}° → ${t.target_satellite_id}
                            </div>
                        </div>
                        <div class="list-item-actions">
                            <button class="btn-danger btn-small" onclick="removeXTransition('${t.id}')">Remove</button>
                        </div>
                    </div>
                `).join('');
            }

            // Remove X transition
            function removeXTransition(id) {
                if (currentMission) {
                    currentMission.transports.x_transitions = currentMission.transports.x_transitions.filter(t => t.id !== id);
                    renderXTransitions(currentMission.transports.x_transitions);
                    markMissionDirty();
                }
            }

            // Clear X transition form
            function clearXTransitionForm() {
                document.getElementById('xTransitionLat').value = '';
                document.getElementById('xTransitionLon').value = '';
                setSatelliteValue('targetXSatellite', '');
            }

            // Add Ka outage
            function addKaOutage() {
                const start = document.getElementById('kaOutageStart').value;
                const duration = parseFloat(document.getElementById('kaOutageDuration').value);

                if (!start || !Number.isFinite(duration)) {
                    showAlert('Please fill in Ka outage fields', 'error');
                    return;
                }

                if (currentMission) {
                    const outage = {
                        id: `ka-outage-${Date.now()}`,
                        start_time: new Date(start).toISOString(),
                        duration_seconds: duration
                    };
                    currentMission.transports.ka_outages.push(outage);
                    renderKaOutages(currentMission.transports.ka_outages);
                    clearKaOutageForm();
                    markMissionDirty();
                }
            }

            // Render Ka outages
            function renderKaOutages(outages) {
                const list = document.getElementById('kaOutagesList');
                if (outages.length === 0) {
                    list.innerHTML = '<p class="empty-state">No Ka outages defined</p>';
                    return;
                }

                list.innerHTML = outages.map(o => `
                    <div class="list-item">
                        <div class="list-item-content">
                            <div class="list-item-title"><span class="badge badge-ka">Ka</span>Outage Window</div>
                            <div class="list-item-details">
                                ${new Date(o.start_time).toLocaleString()} for ${(o.duration_seconds / 60).toFixed(1)} minutes
                            </div>
                        </div>
                        <div class="list-item-actions">
                            <button class="btn-danger btn-small" onclick="removeKaOutage('${o.id}')">Remove</button>
                        </div>
                    </div>
                `).join('');
            }

            // Remove Ka outage
            function removeKaOutage(id) {
                if (currentMission) {
                    currentMission.transports.ka_outages = currentMission.transports.ka_outages.filter(o => o.id !== id);
                    renderKaOutages(currentMission.transports.ka_outages);
                    markMissionDirty();
                }
            }

            // Clear Ka outage form
            function clearKaOutageForm() {
                document.getElementById('kaOutageStart').value = '';
                document.getElementById('kaOutageDuration').value = '';
            }

            // Add Ku override
            function addKuOverride() {
                const start = document.getElementById('kuOutageStart').value;
                const duration = parseFloat(document.getElementById('kuOutageDuration').value);
                const reason = document.getElementById('kuOutageReason').value || null;

                if (!start || !Number.isFinite(duration)) {
                    showAlert('Please fill in Ku outage fields', 'error');
                    return;
                }

                if (currentMission) {
                    const override = {
                        id: `ku-outage-${Date.now()}`,
                        start_time: new Date(start).toISOString(),
                        duration_seconds: duration,
                        reason: reason
                    };
                    currentMission.transports.ku_overrides.push(override);
                    renderKuOverrides(currentMission.transports.ku_overrides);
                    clearKuOverrideForm();
                    markMissionDirty();
                }
            }

            // Render Ku overrides
            function renderKuOverrides(overrides) {
                const list = document.getElementById('kuOverridesList');
                if (overrides.length === 0) {
                    list.innerHTML = '<p class="empty-state">No Ku overrides defined</p>';
                    return;
                }

                list.innerHTML = overrides.map(o => `
                    <div class="list-item">
                        <div class="list-item-content">
                            <div class="list-item-title"><span class="badge badge-ku">Ku</span>Outage Override</div>
                            <div class="list-item-details">
                                ${new Date(o.start_time).toLocaleString()} for ${(o.duration_seconds / 60).toFixed(1)} minutes
                                ${o.reason ? ` - ${o.reason}` : ''}
                            </div>
                        </div>
                        <div class="list-item-actions">
                            <button class="btn-danger btn-small" onclick="removeKuOverride('${o.id}')">Remove</button>
                        </div>
                    </div>
                `).join('');
            }

            // Remove Ku override
            function removeKuOverride(id) {
                if (currentMission) {
                    currentMission.transports.ku_overrides = currentMission.transports.ku_overrides.filter(o => o.id !== id);
                    renderKuOverrides(currentMission.transports.ku_overrides);
                    markMissionDirty();
                }
            }

            // Clear Ku override form
            function clearKuOverrideForm() {
                document.getElementById('kuOutageStart').value = '';
                document.getElementById('kuOutageDuration').value = '';
                document.getElementById('kuOutageReason').value = '';
            }

            // Add AAR window
            function addAARWindow() {
                const start = document.getElementById('aarStartWaypoint').value;
                const end = document.getElementById('aarEndWaypoint').value;

                if (!start || !end) {
                    showAlert('Please select start and end waypoints', 'error');
                    return;
                }

                if (!ensureMissionDraft()) {
                    return;
                }

                const aarWindow = {
                    id: `aar-${Date.now()}`,
                    start_waypoint_name: start,
                    end_waypoint_name: end
                };
                currentMission.transports.aar_windows.push(aarWindow);
                renderAARWindows(currentMission.transports.aar_windows);
                clearAARWindowForm();
                markMissionDirty();
            }

            // Render AAR windows
            function renderAARWindows(windows) {
                const list = document.getElementById('aarWindowsList');
                if (windows.length === 0) {
                    list.innerHTML = '<p class="empty-state">No AAR windows defined</p>';
                    return;
                }

                list.innerHTML = windows.map(w => `
                    <div class="list-item">
                        <div class="list-item-content">
                            <div class="list-item-title">AAR Segment</div>
                            <div class="list-item-details">
                                ${w.start_waypoint_name} → ${w.end_waypoint_name}
                            </div>
                        </div>
                        <div class="list-item-actions">
                            <button class="btn-danger btn-small" onclick="removeAARWindow('${w.id}')">Remove</button>
                        </div>
                    </div>
                `).join('');
            }

            // Remove AAR window
            function removeAARWindow(id) {
                if (currentMission) {
                    currentMission.transports.aar_windows = currentMission.transports.aar_windows.filter(w => w.id !== id);
                    renderAARWindows(currentMission.transports.aar_windows);
                    markMissionDirty();
                }
            }

            // Clear AAR window form
            function clearAARWindowForm() {
                document.getElementById('aarStartWaypoint').value = '';
                document.getElementById('aarEndWaypoint').value = '';
                applyAAREndpointConstraints();
            }

            // Save mission
            async function saveMission(e) {
                e.preventDefault();

                const initialSatellite = document.getElementById('initialXSatellite').value;
                if (!initialSatellite) {
                    showAlert('Select an initial X satellite before saving', 'error');
                    return;
                }

                if (!currentMission) {
                    currentMission = createEmptyMission();
                }

                currentMission.name = document.getElementById('missionName').value;
                currentMission.route_id = document.getElementById('routeId').value;
                currentMission.description = document.getElementById('missionDescription').value || null;
                currentMission.transports.initial_x_satellite_id = initialSatellite;
                currentMission.notes = document.getElementById('missionNotes').value || null;
                currentMission.updated_at = new Date().toISOString();

                const saveBtn = document.querySelector('#saveMissionBtn');
                const originalText = saveBtn.textContent;
                saveBtn.disabled = true;
                saveBtn.innerHTML = '<span class="loading"></span>';

                try {
                    const method = missions.some(m => m.id === currentMission.id) ? 'PUT' : 'POST';
                    const url = method === 'PUT'
                        ? `/api/missions/${currentMission.id}`
                        : '/api/missions';

                    const response = await fetch(url, {
                        method: method,
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(currentMission)
                    });

                    if (!response.ok) {
                        const error = await response.json();
                        throw new Error(error.detail || 'Save failed');
                    }

                    const savedMission = await response.json();
                    populateFormFromMission(savedMission);
                    document.getElementById('missionSelect').value = savedMission.id;
                    await refreshTimelineAvailability();

                    showAlert(`Mission "${currentMission.name}" saved successfully`, 'success');
                    await loadMissions();
                    resetMissionDirty();
                    await recomputeTimeline(true);
                    await loadSatellitePOIs();
                } catch (error) {
                    showAlert('Error: ' + error.message, 'error');
                } finally {
                    saveBtn.disabled = false;
                    saveBtn.textContent = originalText;
                }
            }

            async function toggleMissionState() {
                if (!currentMission || !currentMission.id) {
                    showAlert('Save mission before activating', 'error');
                    return;
                }

                if (missionDirty) {
                    showAlert('Save mission before continuing', 'error');
                    return;
                }

                try {
                    if (currentMission.is_active) {
                        // Deactivate the mission
                        if (!confirm(`Deactivate mission "${currentMission.name}"?`)) {
                            return;
                        }

                        const response = await fetch('/api/missions/active/deactivate', {
                            method: 'POST'
                        });

                        if (!response.ok) {
                            const error = await response.json();
                            throw new Error(error.detail || 'Deactivation failed');
                        }

                        currentMission.is_active = false;
                        setTimelineAvailability(false);
                        showAlert(`Mission "${currentMission.name}" deactivated`, 'success');
                    } else {
                        // Activate the mission
                        const response = await fetch(`/api/missions/${currentMission.id}/activate`, {
                            method: 'POST'
                        });

                        if (!response.ok) {
                            const error = await response.json();
                            throw new Error(error.detail || 'Activation failed');
                        }

                        const result = await response.json();
                        currentMission.is_active = true;
                        setTimelineAvailability(true);
                        showAlert(`Mission activated (phase: ${result.flight_phase})`, 'success');
                    }

                    await loadMissions();
                    await refreshTimelineAvailability();
                } catch (error) {
                    showAlert('Error: ' + error.message, 'error');
                }
            }

            async function recomputeTimeline(silent = false) {
                if (!currentMission || !currentMission.id) {
                    if (!silent) {
                        showAlert('Save mission before recomputing timeline', 'error');
                    }
                    return;
                }
                if (missionDirty) {
                    if (!silent) {
                        showAlert('Save changes before recomputing timeline', 'error');
                    }
                    return;
                }

                const btn = document.getElementById('recomputeTimelineBtn');
                const originalText = btn ? btn.textContent : null;
                if (btn) {
                    if (!silent) {
                        btn.disabled = true;
                        btn.innerHTML = '<span class="loading"></span>';
                    } else {
                        btn.disabled = true;
                    }
                }

                try {
                    const response = await fetch(`/api/missions/${currentMission.id}/timeline/recompute`, {
                        method: 'POST'
                    });
                    if (!response.ok) {
                        const error = await response.json().catch(() => ({}));
                        throw new Error(error.detail || 'Timeline recompute failed');
                    }
                    const timeline = await response.json();
                    setTimelineAvailability(true);
                    if (!silent) {
                        showAlert(`Timeline recomputed (${timeline.segments.length} segments)`, 'success');
                    }
                    await refreshTimelineAvailability();
                    return timeline;
                } catch (error) {
                    if (!silent) {
                        showAlert('Error: ' + error.message, 'error');
                    } else {
                        console.error('Timeline recompute failed:', error);
                    }
                } finally {
                    if (btn) {
                        if (!silent && originalText !== null) {
                            btn.textContent = originalText;
                        }
                        btn.disabled = false;
                    }
                    updateMissionStatus();
                }
            }

            async function exportTimeline() {
                if (!currentMission || !currentMission.id) {
                    showAlert('Save mission before exporting timeline', 'error');
                    return;
                }
                if (!timelineAvailable || missionDirty) {
                    showAlert('Recompute the timeline before exporting', 'error');
                    return;
                }

                const formatSelect = document.getElementById('exportFormatSelect');
                const format = formatSelect?.value || 'csv';
                const btn = document.getElementById('exportTimelineBtn');
                const originalText = btn.textContent;
                btn.disabled = true;
                btn.innerHTML = '<span class="loading"></span>';

                try {
                    const response = await fetch(`/api/missions/${currentMission.id}/export?format=${format}`, {
                        method: 'POST'
                    });
                    if (!response.ok) {
                        const error = await response.json().catch(() => ({}));
                        throw new Error(error.detail || 'Timeline export failed');
                    }
                    const blob = await response.blob();
                    const url = window.URL.createObjectURL(blob);
                    const link = document.createElement('a');
                    link.href = url;
                    link.download = `${currentMission.id}-timeline.${format}`;
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                    window.URL.revokeObjectURL(url);
                    showAlert(`Downloaded ${format.toUpperCase()} timeline`, 'success');
                } catch (error) {
                    showAlert('Error: ' + error.message, 'error');
                } finally {
                    btn.textContent = originalText;
                    btn.disabled = false;
                    updateMissionStatus();
                }
            }

            // Delete mission
            async function deleteMission() {
                if (!currentMission || !confirm(`Delete mission "${currentMission.name}"? This cannot be undone.`)) return;

                try {
                    const response = await fetch(`/api/missions/${currentMission.id}`, {
                        method: 'DELETE'
                    });

                    if (!response.ok) throw new Error('Delete failed');

                    showAlert(`Mission "${currentMission.name}" deleted successfully`, 'success');
                    resetForm();
                    setTimelineAvailability(false);
                    await loadMissions();
                } catch (error) {
                    showAlert('Error: ' + error.message, 'error');
                }
            }

            // Reset form
            function resetForm() {
                suppressDirtyEvents = true;
                document.getElementById('missionForm').reset();
                document.getElementById('missionSelect').value = 'new';
                currentMission = null;
                document.getElementById('deleteMissionBtn').style.display = 'none';
                const toggleBtn = document.getElementById('toggleMissionBtn');
                if (toggleBtn) {
                    toggleBtn.disabled = true;
                }
                renderXTransitions([]);
                renderKaOutages([]);
                renderKuOverrides([]);
                renderAARWindows([]);
                clearXTransitionForm();
                clearKaOutageForm();
                clearKuOverrideForm();
                clearAARWindowForm();
                selectedInitialSatellite = '';
                selectedTargetSatellite = '';
                populateSatelliteSelects();
                suppressDirtyEvents = false;
                resetMissionDirty();
                setTimelineAvailability(false);
            }

            function startNewMissionDraft() {
                if (!confirmDiscardIfDirty()) {
                    document.getElementById('missionSelect').value = currentMission?.id || 'new';
                    return;
                }
                resetForm();
                currentMission = createEmptyMission();
                document.getElementById('missionSelect').value = 'new';
                resetMissionDirty();
                const toggleBtn = document.getElementById('toggleMissionBtn');
                if (toggleBtn) {
                    toggleBtn.disabled = true;
                }
                updateMissionStatus();
                showAlert('Started a new mission draft', 'info');
            }

            // Export mission
            function exportMission() {
                if (!currentMission) {
                    showAlert('Please create or select a mission first', 'error');
                    return;
                }

                const json = JSON.stringify(currentMission, null, 2);
                const blob = new Blob([json], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `${currentMission.id}.json`;
                a.click();
                URL.revokeObjectURL(url);

                showAlert('Mission exported successfully', 'success');
            }

            // Import mission
            function importMission() {
                const fileInput = document.getElementById('importFile');
                const file = fileInput.files[0];

                if (!file) return;
                if (!confirmDiscardIfDirty()) {
                    fileInput.value = '';
                    return;
                }

                const reader = new FileReader();
                reader.onload = (e) => {
                    try {
                        const mission = JSON.parse(e.target.result);
                        const timestamp = new Date().toISOString();
                        mission.id = generateMissionId();
                        mission.is_active = false;
                        mission.created_at = timestamp;
                        mission.updated_at = timestamp;
                        document.getElementById('missionSelect').value = 'new';
                        populateFormFromMission(mission);
                        markMissionDirty();
                        showAlert('Mission imported as new draft', 'success');
                    } catch (error) {
                        showAlert('Error importing mission: ' + error.message, 'error');
                    }
                };
                reader.readAsText(file);
                fileInput.value = '';
            }

            window.addEventListener('click', (event) => {
                const satelliteModal = document.getElementById('satelliteModal');
                if (event.target === satelliteModal) {
                    closeSatelliteModal();
                }
            });

            // Show alert
            function showAlert(message, type = 'info') {
                const alertsDiv = document.getElementById('alerts');
                const alertDiv = document.createElement('div');
                alertDiv.className = `alert alert-${type}`;
                alertDiv.textContent = message;

                alertsDiv.appendChild(alertDiv);
                setTimeout(() => alertDiv.remove(), 4000);
            }
        </script>
    </body>
    </html>
    """
