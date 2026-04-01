

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
let selectedPickerTagIds = new Set();
let pickerStep = 1;
let loadedPickerTags = false;
let searchTerm = "";

const TAG_CATEGORY_ORDER = ["Еда", "Отдых", "Город", "Культура", "Развлечения", "Атмосфера", "Активности", "Доступность"];

const els = {};

function isModerationMode() {
  return window.MAP_MODERATION_MODE || window.MAP_DELETE_MODE;
}

function isDeleteModeEnabled() {
  return window.MAP_DELETE_MODE && !!window.Telegram?.WebApp?.initData;
}

function isMobileViewport() {
  return window.matchMedia("(max-width: 860px)").matches;
}

function setResultsPanelCollapsed(collapsed) {
  if (!els.sidePanel || !els.resultsToggleBtn || window.MAP_PICKER_MODE || !isMobileViewport()) return;
  els.sidePanel.classList.toggle("collapsed", collapsed);
  els.resultsToggleBtn.classList.remove("hidden");
  els.resultsToggleBtn.textContent = collapsed ? "📋 Показать результаты" : "📋 Скрыть результаты";
}

function getPickerChatId() {
  if (window.MAP_PICKER_CHAT_ID !== null && window.MAP_PICKER_CHAT_ID !== undefined) {
    const n = Number(window.MAP_PICKER_CHAT_ID);
    return Number.isFinite(n) ? n : null;
  }
  const params = new URLSearchParams(window.location.search);
  const raw = params.get("chat_id");
  if (!raw) return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}


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
  els.sidePanel = document.querySelector(".side-panel");
  els.resultsToggleBtn = document.getElementById("resultsToggleBtn");
  els.emptyState = document.getElementById("emptyState");
  els.detailPanel = document.getElementById("detailPanel");
  els.detailTitle = document.getElementById("detailTitle");
  els.detailName = document.getElementById("detailName");
  els.detailDescription = document.getElementById("detailDescription");
  els.detailTags = document.getElementById("detailTags");
  els.detailPhotos = document.getElementById("detailPhotos");
  els.photoLightbox = document.getElementById("photoLightbox");
  els.photoLightboxImage = document.getElementById("photoLightboxImage");
  els.photoLightboxClose = document.getElementById("photoLightboxClose");
  els.routeSummary = document.getElementById("routeSummary");
  els.buildRouteBtn = document.getElementById("buildRouteBtn");
  els.clearRouteBtn = document.getElementById("clearRouteBtn");
  els.closeDetailBtn = document.getElementById("closeDetailBtn");
  els.statusBar = document.getElementById("statusBar");
  els.confirmPointBtn = document.getElementById("confirmPointBtn");
  els.pickerStepHint = document.getElementById("pickerStepHint");
  els.pickerTagHelp = document.getElementById("pickerTagHelp");

  if (window.MAP_PICKER_MODE) {
    els.searchInput.classList.add("hidden");
    els.tagsToggleBtn.classList.add("hidden");
    els.clearFiltersBtn.classList.add("hidden");
    els.refreshBtn.classList.add("hidden");
    els.tagFiltersPanel.classList.add("hidden");
    els.selectedTags.classList.add("hidden");
    els.pickerStepHint.classList.remove("hidden");
    els.pickerTagHelp.classList.remove("hidden");
    document.querySelector(".side-panel")?.classList.add("hidden");
    els.resultsToggleBtn?.classList.add("hidden");
  } else if (isMobileViewport()) {
    setResultsPanelCollapsed(true);
  }
}

function initMap() {
  if (!window.L) {
    showStatus("Карта не загрузилась. Обновите страницу или попробуйте позже.", true);
    return;
  }
  map = L.map("map", { attributionControl: false }).setView([window.MAP_DEFAULTS.lat, window.MAP_DEFAULTS.lng], window.MAP_DEFAULTS.zoom);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "",
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
    L.marker([p.lat, p.lng]).addTo(map);
    map.setView([p.lat, p.lng], 15);
  }
}

async function confirmPickerPoint() {
  if (!pickerCoords && map) {
    const center = map.getCenter();
    pickerCoords = { lat: center.lat, lng: center.lng };
    if (pickerMarker) map.removeLayer(pickerMarker);
    pickerMarker = L.marker([pickerCoords.lat, pickerCoords.lng]).addTo(map);
  }

  const tg = window.Telegram?.WebApp;
  if (!tg?.initData) {
    showStatus("Точка выбрана, но это не Telegram WebApp", true);
    return;
  }

  if (pickerStep === 1) {
    pickerStep = 2;
    els.confirmPointBtn.textContent = "✅ Подтвердить теги";
    els.tagFiltersPanel.classList.remove("hidden");
    showStatus("Шаг 2 из 2: выберите до 5 тегов и нажмите подтверждение", true);
    if (!loadedPickerTags) {
      await loadPickerTags();
    }
    return;
  }

  try {
    const response = await fetch("/api/webapp/picker/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        latitude: pickerCoords.lat,
        longitude: pickerCoords.lng,
        init_data: tg.initData,
        chat_id: getPickerChatId(),
        tag_ids: [...selectedPickerTagIds],
      }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload?.ok !== true) {
      throw new Error(payload?.detail || `HTTP ${response.status}`);
    }

    showStatus("Точка и теги сохранены. Возвращайтесь в бот", true);
    setTimeout(() => tg.close(), 300);
  } catch (err) {
    console.error(err);
    showStatus("Не удалось передать точку и теги. Попробуйте снова", true);
  }
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

async function loadPickerTags() {
  try {
    const tags = await apiJson("/api/tag/tags");
    loadedPickerTags = true;
    renderTags(tags || []);
  } catch {
    showStatus("Не удалось загрузить теги", true);
  }
}


function renderSelectedTags() {
  if (window.MAP_PICKER_MODE) {
    return;
  }
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
  const grouped = new Map();
  tags.forEach((tag) => {
    const category = tag.category || "Другое";
    if (!grouped.has(category)) grouped.set(category, []);
    grouped.get(category).push(tag);
  });

  const orderedCategories = [
    ...TAG_CATEGORY_ORDER.filter((category) => grouped.has(category)),
    ...[...grouped.keys()].filter((category) => !TAG_CATEGORY_ORDER.includes(category)),
  ];

  orderedCategories.forEach((category) => {
    const groupWrap = document.createElement("section");
    groupWrap.className = "tag-group";

    const title = document.createElement("p");
    title.className = "tag-group-title";
    title.textContent = category;
    groupWrap.appendChild(title);

    const chipsWrap = document.createElement("div");
    chipsWrap.className = "tag-group-chips";

    grouped.get(category).forEach((tag) => {
      const chip = document.createElement("button");
      chip.className = "tag-chip";
      chip.textContent = tag.name;
      chip.dataset.tag = tag.name.toLowerCase();
      chip.dataset.tagId = String(tag.id);
      chip.addEventListener("click", () => {
        if (window.MAP_PICKER_MODE) {
          const tagId = Number(chip.dataset.tagId);
          if (selectedPickerTagIds.has(tagId)) {
            selectedPickerTagIds.delete(tagId);
          } else {
            if (selectedPickerTagIds.size >= 5) {
              showStatus("Можно выбрать не более 5 тегов", true);
              return;
            }
            selectedPickerTagIds.add(tagId);
          }
          chip.classList.toggle("active", selectedPickerTagIds.has(tagId));
          return;
        }

        const key = chip.dataset.tag;
        if (selectedTags.has(key)) selectedTags.delete(key);
        else selectedTags.add(key);
        chip.classList.toggle("active", selectedTags.has(key));
        applyFilters();
        renderSelectedTags();
      });
      chipsWrap.appendChild(chip);
    });

    groupWrap.appendChild(chipsWrap);
    els.tagFilters.appendChild(groupWrap);
  });
  renderSelectedTags();
}

function createLocationMarker(loc) {
  const isFocusedPending =
    window.MAP_MODERATION_MODE &&
    loc.status === "pending" &&
    Number(window.MAP_FOCUS_LOCATION_ID) === Number(loc.id);

  if (window.MAP_MODERATION_MODE && loc.status === "pending") {
    const marker = L.circleMarker([loc.latitude, loc.longitude], {
      radius: isFocusedPending ? 10 : 8,
      color: isFocusedPending ? "#991b1b" : "#dc2626",
      weight: isFocusedPending ? 3 : 2,
      fillColor: isFocusedPending ? "#ef4444" : "#f87171",
      fillOpacity: 0.9,
    }).addTo(map);
    marker.bindTooltip(isFocusedPending ? "🛠 Текущая модерируемая точка" : "⏳ Pending", {
      permanent: isFocusedPending,
      direction: "top",
      offset: [0, -8],
    });
    return marker;
  }

  if (window.MAP_MODERATION_MODE && loc.status === "approved") {
    return L.circleMarker([loc.latitude, loc.longitude], {
      radius: 7,
      color: "#1d4ed8",
      weight: 2,
      fillColor: "#3b82f6",
      fillOpacity: 0.85,
    }).addTo(map);
  }

  return L.marker([loc.latitude, loc.longitude]).addTo(map);
}

function renderMarkers(locations) {
  markersById.forEach((marker) => map.removeLayer(marker));
  markersById.clear();

  locations.forEach((loc) => {
    const marker = createLocationMarker(loc);
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
    item.innerHTML = `<h4>${loc.name}</h4>`;
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
  if (pan) map.setView([loc.latitude, loc.longitude], 15);

  els.detailTitle.textContent = loc.name;
  if (els.detailName) {
    els.detailName.textContent = loc.name;
  }
  els.detailDescription.textContent = loc.description || "описания нет";

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
      img.addEventListener("click", () => openPhotoLightbox(photo.url, loc.name));
      img.onerror = () => {
        img.replaceWith(document.createTextNode("Фото недоступно"));
      };
      els.detailPhotos.appendChild(img);
    });
  }

  els.routeSummary.classList.add("hidden");
  els.detailPanel.classList.add("open");
}

function closeDetail() {
  selectedLocation = null;
  els.detailPanel.classList.remove("open");
}

function openPhotoLightbox(url, locationName = "") {
  if (!els.photoLightbox || !els.photoLightboxImage) return;
  els.photoLightboxImage.src = url;
  els.photoLightboxImage.alt = locationName ? `Увеличенное фото: ${locationName}` : "Увеличенное фото";
  els.photoLightbox.classList.remove("hidden");
}

function closePhotoLightbox() {
  if (!els.photoLightbox || !els.photoLightboxImage) return;
  els.photoLightbox.classList.add("hidden");
  els.photoLightboxImage.src = "";
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
    const tg = window.Telegram?.WebApp;
    const isModeration = isModerationMode() && !!tg?.initData;
    const moderationEndpoint = window.MAP_DELETE_MODE
      ? "/api/map/locations/moderation-delete"
      : "/api/map/locations/moderation";
    const endpoint = isModeration
      ? `${moderationEndpoint}?init_data=${encodeURIComponent(tg.initData)}`
      : "/api/map/locations/approved";
    const payload = await apiJson(endpoint);
    allLocations = payload.items || [];
    if (isModeration && window.MAP_FOCUS_LOCATION_ID) {
      try {
        const focusItem = await apiJson(
          `/api/map/location/${window.MAP_FOCUS_LOCATION_ID}?init_data=${encodeURIComponent(tg.initData)}`
        );
        console.info("Pending location context found", { locationId: focusItem.id, status: focusItem.status });
        if (!allLocations.find((loc) => loc.id === focusItem.id)) {
          allLocations.push(focusItem);
        }
      } catch (e) {
        console.warn("Failed to load focused moderation location", e);
        console.warn("Pending location context not found", { locationId: window.MAP_FOCUS_LOCATION_ID });
        showStatus("Модерируемая локация не найдена или недоступна", true);
      }
    }
    applyFilters();
    if (!allLocations.length) {
      if (window.MAP_DELETE_MODE) showStatus("Нет доступных локаций для удаления", true);
      else if (window.MAP_MODERATION_MODE) showStatus("Нет локаций для модерации", true);
      else showStatus("Пока нет одобренных локаций", true);
    }
    if (window.MAP_FOCUS_LOCATION_ID) {
      setTimeout(() => selectLocation(Number(window.MAP_FOCUS_LOCATION_ID), true), 50);
    }
  } catch (e) {
    if (window.MAP_DELETE_MODE) {
      console.warn("Delete mode unavailable", e);
      showStatus("Нет доступа к delete mode", true);
      return;
    }
    if (window.MAP_MODERATION_MODE) {
      console.warn("Moderation map mode unavailable", e);
      showStatus("Нет доступа к moderation map mode", true);
      return;
    }
    showStatus("Ошибка загрузки локаций", true);
  }
}

async function deleteSelectedLocation() {
  if (!isDeleteModeEnabled()) return;
  if (!selectedLocation) {
    showStatus("Сначала выберите локацию", true);
    return;
  }
  const tg = window.Telegram?.WebApp;
  console.info("Delete target location selected", { locationId: selectedLocation.id });
  const ok = window.confirm(`Удалить локацию «${selectedLocation.name}»?`);
  if (!ok) {
    console.info("Delete cancelled", { locationId: selectedLocation.id });
    return;
  }

  try {
    const response = await fetch("/api/webapp/moderation/delete-location", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        location_id: selectedLocation.id,
        init_data: tg.initData,
        confirm: true,
      }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload?.ok !== true) {
      throw new Error(payload?.detail || `HTTP ${response.status}`);
    }
    showStatus("Локация удалена", true);
    closeDetail();
    await loadLocations();
  } catch (e) {
    console.error(e);
    showStatus("Не удалось удалить локацию", true);
  }
}

function bindEvents() {
  if (!window.MAP_PICKER_MODE) {
    els.searchInput.addEventListener("input", (e) => {
      searchTerm = e.target.value.trim().toLowerCase();
      applyFilters();
    });
  }
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
  if (els.resultsToggleBtn) {
    els.resultsToggleBtn.addEventListener("click", () => {
      const collapsed = !els.sidePanel?.classList.contains("collapsed");
      setResultsPanelCollapsed(collapsed);
    });
  }
  els.refreshBtn.addEventListener("click", loadLocations);
  els.findMeBtn.addEventListener("click", findMe);
  els.buildRouteBtn.addEventListener("click", buildRoute);
  els.clearRouteBtn.addEventListener("click", clearRoute);
  if (window.MAP_DELETE_MODE && !isDeleteModeEnabled()) {
    showStatus("Режим удаления доступен только модератору из Telegram", true);
  }
  if (isDeleteModeEnabled()) {
    els.buildRouteBtn.textContent = "🗑 Удалить локацию";
    els.clearRouteBtn.classList.add("hidden");
    els.buildRouteBtn.replaceWith(els.buildRouteBtn.cloneNode(true));
    els.buildRouteBtn = document.getElementById("buildRouteBtn");
    els.buildRouteBtn.addEventListener("click", deleteSelectedLocation);
  }
  els.closeDetailBtn.addEventListener("click", closeDetail);
  if (els.photoLightboxClose) {
    els.photoLightboxClose.addEventListener("click", closePhotoLightbox);
  }
  if (els.photoLightbox) {
    els.photoLightbox.addEventListener("click", (e) => {
      if (e.target === els.photoLightbox) closePhotoLightbox();
    });
  }
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closePhotoLightbox();
    }
  });
  if (window.MAP_PICKER_MODE && els.confirmPointBtn) {
    els.confirmPointBtn.classList.remove("hidden");
    els.confirmPointBtn.addEventListener("click", confirmPickerPoint);
  }
  window.addEventListener("resize", () => {
    if (window.MAP_PICKER_MODE || !els.resultsToggleBtn || !els.sidePanel) return;
    if (isMobileViewport()) {
      if (!els.sidePanel.classList.contains("collapsed")) {
        els.resultsToggleBtn.classList.remove("hidden");
        els.resultsToggleBtn.textContent = "📋 Скрыть результаты";
      } else {
        setResultsPanelCollapsed(true);
      }
      return;
    }
    els.sidePanel.classList.remove("collapsed");
    els.resultsToggleBtn.classList.add("hidden");
  });
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
