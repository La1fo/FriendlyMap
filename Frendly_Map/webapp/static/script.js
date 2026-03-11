

function initTelegramWebApp() {
  const tg = window.Telegram?.WebApp;
  if (!tg) return;

  try {
    tg.ready();
    tg.expand();

    const bg = tg.themeParams?.bg_color;
    const text = tg.themeParams?.text_color;
    if (bg) document.body.style.background = bg;
    if (text) document.body.style.color = text;

    if (typeof tg.viewportHeight === "number" && tg.viewportHeight > 0) {
      document.documentElement.style.setProperty("--tg-vh", `${tg.viewportHeight}px`);
    }
  } catch (e) {
    console.warn("Telegram WebApp init failed", e);
  }
}
let map;
let routeLine;
let userMarker;
let pickerMarker;
let selectedLocation = null;
let userCoords = null;
let pickerCoords = null;

const markersById = new Map();
let allLocations = [];
let filteredLocations = [];
let selectedTags = new Set();
let searchTerm = "";

const els = {};

function showStatus(message, persistent = false) {
  els.statusBar.textContent = message;
  els.statusBar.classList.remove("hidden");
  if (!persistent) {
    setTimeout(() => els.statusBar.classList.add("hidden"), 2800);
  }
}

function hideStatus() {
  els.statusBar.classList.add("hidden");
}

function formatDistance(meters) {
  return meters >= 1000 ? `${(meters / 1000).toFixed(1)} км` : `${Math.round(meters)} м`;
}

function formatDuration(seconds) {
  const m = Math.round(seconds / 60);
  if (m < 60) return `${m} мин`;
  const h = Math.floor(m / 60);
  return `${h} ч ${m % 60} мин`;
}

function initDom() {
  els.searchInput = document.getElementById("searchInput");
  els.refreshBtn = document.getElementById("refreshBtn");
  els.findMeBtn = document.getElementById("findMeBtn");
  els.clearFiltersBtn = document.getElementById("clearFiltersBtn");
  els.tagsToggleBtn = document.getElementById("tagsToggleBtn");
  els.tagFiltersPanel = document.getElementById("tagFiltersPanel");
  els.tagFilters = document.getElementById("tagFilters");
  els.selectedTags = document.getElementById("selectedTags");
  els.locationList = document.getElementById("locationList");
  els.emptyState = document.getElementById("emptyState");
  els.detailPanel = document.getElementById("detailPanel");
  els.detailTitle = document.getElementById("detailTitle");
  els.detailAddress = document.getElementById("detailAddress");
  els.detailDescription = document.getElementById("detailDescription");
  els.detailTags = document.getElementById("detailTags");
  els.detailPhotos = document.getElementById("detailPhotos");
  els.routeSummary = document.getElementById("routeSummary");
  els.buildRouteBtn = document.getElementById("buildRouteBtn");
  els.clearRouteBtn = document.getElementById("clearRouteBtn");
  els.closeDetailBtn = document.getElementById("closeDetailBtn");
  els.statusBar = document.getElementById("statusBar");
  els.confirmPointBtn = document.getElementById("confirmPointBtn");

  if (window.MAP_PICKER_MODE) {
    els.searchInput.classList.add("hidden");
    els.tagsToggleBtn.classList.add("hidden");
    els.clearFiltersBtn.classList.add("hidden");
    els.refreshBtn.classList.add("hidden");
    els.tagFiltersPanel.classList.add("hidden");
    els.selectedTags.classList.add("hidden");
    document.querySelector(".side-panel")?.classList.add("hidden");
  }
}

function initMap() {
  if (!window.L) {
    showStatus("Карта не загрузилась. Обновите страницу или попробуйте позже.", true);
    return;
  }
  map = L.map("map").setView([window.MAP_DEFAULTS.lat, window.MAP_DEFAULTS.lng], window.MAP_DEFAULTS.zoom);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors",
    maxZoom: 19,
  }).addTo(map);

  map.whenReady(() => {
    setTimeout(() => map.invalidateSize(), 100);
  });
  window.addEventListener("resize", () => map.invalidateSize());

  if (window.MAP_PICKER_MODE) {
    map.on("click", (e) => {
      pickerCoords = { lat: e.latlng.lat, lng: e.latlng.lng };
      if (pickerMarker) map.removeLayer(pickerMarker);
      pickerMarker = L.marker([pickerCoords.lat, pickerCoords.lng]).addTo(map).bindPopup("Выбранная точка");
      pickerMarker.openPopup();
      showStatus("Точка выбрана. Нажмите «Подтвердить точку»", true);
    });
  }

  if (window.MAP_FOCUS_POINT) {
    const p = window.MAP_FOCUS_POINT;
    L.marker([p.lat, p.lng]).addTo(map).bindPopup(p.name || "Точка").openPopup();
    map.setView([p.lat, p.lng], 15);
  }
}

function confirmPickerPoint() {
  if (!pickerCoords && map) {
    const center = map.getCenter();
    pickerCoords = { lat: center.lat, lng: center.lng };
    if (pickerMarker) map.removeLayer(pickerMarker);
    pickerMarker = L.marker([pickerCoords.lat, pickerCoords.lng]).addTo(map);
  }

  const payload = JSON.stringify({
    type: "add_location_point",
    latitude: pickerCoords.lat,
    longitude: pickerCoords.lng,
  });

  const tg = window.Telegram?.WebApp;
  if (tg?.sendData) {
    tg.sendData(payload);
    showStatus("Точка отправлена в бот", true);
    tg.close();
    return;
  }

  showStatus("Точка выбрана, но это не Telegram WebApp", true);
}

async function apiJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    const errText = await response.text();
    throw new Error(`${response.status}: ${errText}`);
  }
  return response.json();
}

async function loadTags() {
  try {
    const tags = await apiJson("/api/tag/tags");
    renderTags(tags || []);
  } catch {
    showStatus("Не удалось загрузить теги");
  }
}


function renderSelectedTags() {
  els.selectedTags.innerHTML = "";
  if (selectedTags.size === 0) {
    els.selectedTags.classList.add("hidden");
    return;
  }
  els.selectedTags.classList.remove("hidden");
  [...selectedTags].forEach((tagName) => {
    const chip = document.createElement("span");
    chip.className = "tag-chip active";
    chip.textContent = `#${tagName}`;
    els.selectedTags.appendChild(chip);
  });
}

function renderTags(tags) {
  els.tagFilters.innerHTML = "";
  tags.forEach((tag) => {
    const chip = document.createElement("button");
    chip.className = "tag-chip";
    chip.textContent = tag.name;
    chip.dataset.tag = tag.name.toLowerCase();
    chip.addEventListener("click", () => {
      const key = chip.dataset.tag;
      if (selectedTags.has(key)) selectedTags.delete(key);
      else selectedTags.add(key);
      chip.classList.toggle("active", selectedTags.has(key));
      applyFilters();
      renderSelectedTags();
    });
    els.tagFilters.appendChild(chip);
  });
  renderSelectedTags();
}

function renderMarkers(locations) {
  markersById.forEach((marker) => map.removeLayer(marker));
  markersById.clear();

  locations.forEach((loc) => {
    const marker = L.marker([loc.latitude, loc.longitude]).addTo(map);
    marker.on("click", () => selectLocation(loc.id, true));
    markersById.set(loc.id, marker);
  });

  if (locations.length && !selectedLocation) {
    const bounds = L.latLngBounds(locations.map((l) => [l.latitude, l.longitude]));
    map.fitBounds(bounds.pad(0.2));
  }
}

function renderList(locations) {
  els.locationList.innerHTML = "";
  els.emptyState.classList.toggle("hidden", locations.length > 0);

  locations.forEach((loc) => {
    const item = document.createElement("li");
    item.className = "location-item";
    item.innerHTML = `<h4>${loc.name}</h4><p>${loc.address || "Адрес не указан"}</p>`;
    item.addEventListener("click", () => selectLocation(loc.id, true));
    els.locationList.appendChild(item);
  });
}

function locationMatches(location) {
  const tags = (location.tags || []).map((t) => (t.name || "").toLowerCase());
  const tagsOk = selectedTags.size === 0 || [...selectedTags].every((t) => tags.includes(t));

  const haystack = [location.name, location.address, location.description].join(" ").toLowerCase();
  const searchOk = !searchTerm || haystack.includes(searchTerm);
  return tagsOk && searchOk;
}

function applyFilters() {
  filteredLocations = allLocations.filter(locationMatches);
  renderMarkers(filteredLocations);
  renderList(filteredLocations);

  if (selectedLocation && !filteredLocations.find((l) => l.id === selectedLocation.id)) {
    closeDetail();
  }
}

function selectLocation(locationId, pan = false) {
  const loc = allLocations.find((l) => l.id === locationId);
  if (!loc) return;
  selectedLocation = loc;

  const marker = markersById.get(loc.id);
  if (marker) marker.openPopup();
  if (pan) map.setView([loc.latitude, loc.longitude], 15);

  els.detailTitle.textContent = loc.name;
  els.detailAddress.textContent = loc.address || "Адрес не указан";
  els.detailDescription.textContent = loc.description || "Описание отсутствует";

  els.detailTags.innerHTML = "";
  (loc.tags || []).forEach((tag) => {
    const span = document.createElement("span");
    span.className = "tag";
    span.textContent = tag.name;
    els.detailTags.appendChild(span);
  });

  els.detailPhotos.innerHTML = "";
  if (!loc.photos || !loc.photos.length) {
    const fallback = document.createElement("span");
    fallback.className = "empty";
    fallback.textContent = "Фото отсутствуют";
    els.detailPhotos.appendChild(fallback);
  } else {
    loc.photos.forEach((photo) => {
      const img = document.createElement("img");
      img.src = photo.url;
      img.loading = "lazy";
      img.alt = `Фото ${loc.name}`;
      img.onerror = () => {
        img.replaceWith(document.createTextNode("Фото недоступно"));
      };
      els.detailPhotos.appendChild(img);
    });
  }

  els.routeSummary.classList.add("hidden");
  els.detailPanel.classList.remove("hidden");
}

function closeDetail() {
  selectedLocation = null;
  els.detailPanel.classList.add("hidden");
}

function ensureUserLocation() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error("Геолокация не поддерживается"));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => {
        userCoords = {
          lat: position.coords.latitude,
          lng: position.coords.longitude,
        };
        if (userMarker) map.removeLayer(userMarker);
        userMarker = L.marker([userCoords.lat, userCoords.lng]).addTo(map).bindPopup("Вы здесь");
        resolve(userCoords);
      },
      () => reject(new Error("Не удалось получить геопозицию")),
      { enableHighAccuracy: true, timeout: 10000 }
    );
  });
}

async function findMe() {
  try {
    const coords = await ensureUserLocation();
    map.setView([coords.lat, coords.lng], 15);
    showStatus("Местоположение определено");
  } catch (err) {
    showStatus(err.message, true);
  }
}

async function buildRoute() {
  if (!selectedLocation) {
    showStatus("Сначала выберите локацию", true);
    return;
  }

  try {
    const coords = userCoords || (await ensureUserLocation());
    const params = new URLSearchParams({
      start_lat: coords.lat,
      start_lng: coords.lng,
      end_lat: selectedLocation.latitude,
      end_lng: selectedLocation.longitude,
    });
    const route = await apiJson(`/api/map/route?${params.toString()}`);

    if (routeLine) map.removeLayer(routeLine);
    routeLine = L.polyline(route.points.map((p) => [p.lat, p.lng]), { color: "#16a34a", weight: 5 }).addTo(map);
    map.fitBounds(routeLine.getBounds().pad(0.1));

    els.routeSummary.textContent = `Маршрут: ${formatDistance(route.distance_m)} · ${formatDuration(route.duration_s)}`;
    els.routeSummary.classList.remove("hidden");
  } catch {
    showStatus("Не удалось построить маршрут", true);
  }
}

function clearRoute() {
  if (routeLine) {
    map.removeLayer(routeLine);
    routeLine = null;
  }
  els.routeSummary.classList.add("hidden");
}

async function loadLocations() {
  hideStatus();
  try {
    const payload = await apiJson("/api/map/locations/approved");
    allLocations = payload.items || [];
    applyFilters();
    if (!allLocations.length) showStatus("Пока нет одобренных локаций", true);
  } catch {
    showStatus("Ошибка загрузки локаций", true);
  }
}

function bindEvents() {
  els.searchInput.addEventListener("input", (e) => {
    searchTerm = e.target.value.trim().toLowerCase();
    applyFilters();
  });
  els.clearFiltersBtn.addEventListener("click", () => {
    selectedTags.clear();
    searchTerm = "";
    els.searchInput.value = "";
    document.querySelectorAll("#tagFilters .tag-chip").forEach((chip) => chip.classList.remove("active"));
    applyFilters();
    renderSelectedTags();
    clearRoute();
  });
  els.tagsToggleBtn.addEventListener("click", () => {
    els.tagFiltersPanel.classList.toggle("hidden");
  });
  els.refreshBtn.addEventListener("click", loadLocations);
  els.findMeBtn.addEventListener("click", findMe);
  els.buildRouteBtn.addEventListener("click", buildRoute);
  els.clearRouteBtn.addEventListener("click", clearRoute);
  els.closeDetailBtn.addEventListener("click", closeDetail);
  if (window.MAP_PICKER_MODE && els.confirmPointBtn) {
    els.confirmPointBtn.classList.remove("hidden");
    els.confirmPointBtn.addEventListener("click", confirmPickerPoint);
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  initTelegramWebApp();
  initDom();
  initMap();
  if (!map) return;
  bindEvents();
  if (window.MAP_PICKER_MODE) {
    return;
  }
  await Promise.all([loadTags(), loadLocations()]);
});
