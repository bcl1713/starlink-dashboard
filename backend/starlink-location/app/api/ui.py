"""UI endpoints for POI management interface."""

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
                    'other': 'star'
                };
                document.getElementById('poiIcon').value = iconMap[e.target.value] || 'star';
            });

            // Load POIs
            async function loadPOIs() {
                try {
                    const response = await fetch('/api/pois');
                    if (!response.ok) throw new Error('Failed to load POIs');

                    const data = await response.json();
                    poiData = data.pois || [];

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
                    const poiData = {
                        name: document.getElementById('poiName').value,
                        latitude: parseFloat(document.getElementById('poiLatitude').value),
                        longitude: parseFloat(document.getElementById('poiLongitude').value),
                        category: document.getElementById('poiCategory').value,
                        icon: document.getElementById('poiIcon').value,
                        description: document.getElementById('poiDescription').value || null
                    };

                    if (!poiData.name || !poiData.latitude || !poiData.longitude || !poiData.category) {
                        throw new Error('Please fill in all required fields');
                    }

                    const url = currentEditId ? `/api/pois/${currentEditId}` : '/api/pois';
                    const method = currentEditId ? 'PUT' : 'POST';

                    const response = await fetch(url, {
                        method,
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(poiData)
                    });

                    if (!response.ok) {
                        const error = await response.json();
                        throw new Error(error.detail || 'Operation failed');
                    }

                    const action = currentEditId ? 'updated' : 'created';
                    showAlert(`POI "${poiData.name}" ${action} successfully`, 'success');

                    // Reset form
                    document.getElementById('poiForm').reset();
                    currentEditId = null;
                    document.getElementById('submitBtn').textContent = 'Create POI';
                    document.getElementById('deleteBtn').style.display = 'none';
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
                initMap();
                loadPOIs();

                // Refresh POI list every 5 seconds
                setInterval(loadPOIs, 5000);
            });
        </script>
    </body>
    </html>
    """
