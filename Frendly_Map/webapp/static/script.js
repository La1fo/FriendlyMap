let map;
let userLocationMarker = null;
const API_BASE_URL = window.location.origin;

document.addEventListener('DOMContentLoaded', () => {
    map = L.map('map').setView([55.76, 37.64], 12);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors'
    }).addTo(map);

    loadApprovedLocations();

    document.getElementById('myLocationBtn').addEventListener('click', findMyLocation);
    document.getElementById('refreshBtn').addEventListener('click', loadApprovedLocations);
    document.getElementById('closeInfo').addEventListener('click', closeLocationInfo);
});

async function loadApprovedLocations() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/map/locations/approved`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const locations = await response.json();

        map.eachLayer(layer => {
            if (layer instanceof L.Marker) map.removeLayer(layer);
        });

        locations.forEach(location => addLocationToMap(location));
    } catch (error) {
        console.error('Ошибка загрузки локаций:', error);
        alert('Не удалось загрузить локации.');
    }
}

function addLocationToMap(location) {
    const marker = L.marker([location.latitude, location.longitude], {
        icon: L.divIcon({
            className: 'map-marker',
            html: `<div class="marker-pin"><span>${location.name.substring(0, 20)}</span></div>`,
            iconSize: [30, 40],
            iconAnchor: [15, 40]
        })
    }).addTo(map);

    let balloonContent = `<strong>${location.name}</strong>`;
    if (location.description) balloonContent += `<p>${location.description}</p>`;
    if (location.address) balloonContent += `<p><strong>📍 Адрес:</strong> ${location.address}</p>`;
    if (location.tags && location.tags.length > 0) {
        const tagsHTML = location.tags.map(tag => `<span class="tag">${tag.name}</span>`).join('');
        balloonContent += `<p><strong>🏷️ Теги:</strong> ${tagsHTML}</p>`;
    }
    balloonContent += `<p><em>Одобрено модератором</em></p>`;
    marker.bindPopup(balloonContent);

    marker.on('click', () => showLocationInfo(location));
}

function showLocationInfo(location) {
    const infoPanel = document.getElementById('locationInfo');
    const title = document.getElementById('locationTitle');
    const content = document.getElementById('locationContent');

    title.textContent = location.name;

    let html = '';
    if (location.description) html += `<p>${location.description}</p>`;
    if (location.address) html += `<p><strong>📍 Адрес:</strong> ${location.address}</p>`;
    html += `<p><strong>📅 Добавлено:</strong> ${new Date(location.created_at).toLocaleDateString('ru-RU')}</p>`;
    html += `<p><strong>✅ Статус:</strong> Одобрено</p>`;

    if (location.tags && location.tags.length > 0) {
        const tagsHTML = location.tags.map(tag => `<span class="tag">${tag.name}</span>`).join('');
        html += `<div class="tags"><strong>🏷️ Теги:</strong> ${tagsHTML}</div>`;
    }

    if (location.photos && location.photos.length > 0) {
        const photosHTML = location.photos.map((photo, i) =>
            `<img src="https://via.placeholder.com/80x80/4CAF50/FFFFFF?text=Photo${i+1}" 
                  alt="Фото ${i+1}" class="photo-thumb">`
        ).join('');
        html += `<div class="photo-gallery"><strong>📷 Фотографии:</strong> ${photosHTML}</div>`;
    }

    content.innerHTML = html;
    infoPanel.classList.remove('hidden');
    map.setView([location.latitude, location.longitude], 14);
}

function closeLocationInfo() {
    document.getElementById('locationInfo').classList.add('hidden');
}

function findMyLocation() {
    if (!navigator.geolocation) {
        alert('Геолокация не поддерживается');
        return;
    }

    navigator.geolocation.getCurrentPosition(
        pos => {
            const coords = [pos.coords.latitude, pos.coords.longitude];
            if (userLocationMarker) map.removeLayer(userLocationMarker);

            userLocationMarker = L.marker(coords, {
                icon: L.divIcon({
                    className: 'user-marker',
                    html: '<div class="user-pin">📍</div>',
                    iconSize: [30, 30],
                    iconAnchor: [15, 30]
                })
            }).addTo(map);

            map.setView(coords, 15);
        },
        err => {
            console.error('Ошибка геолокации:', err);
            alert('Не удалось определить местоположение');
        }
    );
}
