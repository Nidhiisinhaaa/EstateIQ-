// Phase 7 -- Leaflet-based geographic price intelligence.
// Fetches the GeoJSON feed once, then does all tier/price filtering client-side.

(function () {
  const BP = {
    low: "#B8860B",
    high: "#FACC15",
    topDecile: "#34D399",
    approximate: "#A3A3A3",
    surface: "#1C1C1C",
    line: "#333333",
    text: "#F5F5F5",
    muted: "#A3A3A3",
  };

  const CITY_CENTER = [12.9716, 77.5946];
  const CLUSTER_THRESHOLD = 200;

  function hexToRgb(hex) {
    const n = parseInt(hex.slice(1), 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }

  function interpolateColor(hexA, hexB, t) {
    const a = hexToRgb(hexA);
    const b = hexToRgb(hexB);
    const rgb = a.map((v, i) => Math.round(v + (b[i] - v) * t));
    return `rgb(${rgb.join(",")})`;
  }

  function markerRadius(listingCount) {
    return Math.max(5, Math.min(22, 4 + Math.sqrt(listingCount) * 1.4));
  }

  function markerStyle(props) {
    if (props.is_approximate) {
      return { color: BP.approximate, weight: 2, fillOpacity: 0, dashArray: "3,3" };
    }
    const fill = props.is_top_decile ? BP.topDecile : interpolateColor(BP.low, BP.high, props.intensity);
    return { color: fill, weight: 1, fillColor: fill, fillOpacity: 0.8 };
  }

  function inrShort(value) {
    const n = Number(value);
    if (n >= 1_00_00_000) return `${(n / 1_00_00_000).toFixed(2)} Cr`;
    if (n >= 1_00_000) return `${(n / 1_00_000).toFixed(2)} L`;
    return n.toLocaleString("en-IN");
  }

  const map = L.map("estateiq-map", { zoomControl: true }).setView(CITY_CENTER, 11);

  L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
    subdomains: "abcd",
    maxZoom: 19,
  }).addTo(map);

  let allFeatures = [];
  let markerLayer = null;
  let activeTier = "All";
  let ppsfRange = [0, 0];

  function openSidePanel(props) {
    const panel = document.getElementById("side-panel");
    const content = document.getElementById("side-panel-content");

    const bhkRows = props.bhk_breakdown
      .map((r) => `<div class="flex justify-between py-1.5 border-b border-bp-line text-sm">
          <span class="text-bp-muted">${r.bhk} BHK</span>
          <span class="bp-metric">${inrShort(r.average_price)}</span>
        </div>`)
      .join("");

    content.innerHTML = `
      <p class="bp-label mb-2">${props.tier} Tier${props.is_approximate ? " -- Approximate Location" : ""}</p>
      <h2 class="font-heading text-2xl font-semibold text-bp-text mb-4">${props.name}</h2>
      <div class="grid grid-cols-2 gap-3 mb-6">
        <div class="bp-card p-3">
          <p class="bp-label mb-1 text-[10px]">Listings</p>
          <p class="bp-metric text-lg">${props.listing_count}</p>
        </div>
        <div class="bp-card p-3">
          <p class="bp-label mb-1 text-[10px]">Median Price/Sqft</p>
          <p class="bp-metric text-lg">Rs ${Math.round(props.median_price_per_sqft).toLocaleString("en-IN")}</p>
        </div>
        <div class="bp-card p-3 col-span-2">
          <p class="bp-label mb-1 text-[10px]">Median Price</p>
          <p class="bp-metric text-lg">${inrShort(props.median_price)}</p>
        </div>
      </div>
      <p class="bp-label mb-2">BHK Price Breakdown</p>
      <div class="mb-6">${bhkRows || '<p class="text-xs text-bp-muted">No breakdown available.</p>'}</div>
      <a class="bp-btn w-full justify-center" href="${window.ESTATEIQ_PREDICT_URL}?location=${encodeURIComponent(props.name)}">Predict here</a>
    `;
    panel.classList.add("open");
  }

  document.getElementById("side-panel-close").addEventListener("click", () => {
    document.getElementById("side-panel").classList.remove("open");
  });

  function buildMarker(feature) {
    const [lng, lat] = feature.geometry.coordinates;
    const props = feature.properties;
    const marker = L.circleMarker([lat, lng], {
      radius: markerRadius(props.listing_count),
      ...markerStyle(props),
    });
    marker.bindTooltip(
      `<span style="font-family:'JetBrains Mono',monospace">${props.name} -- Rs ${Math.round(props.median_price_per_sqft).toLocaleString("en-IN")}/sqft</span>`,
      { direction: "top", sticky: true }
    );
    marker.on("click", () => openSidePanel(props));
    return marker;
  }

  function render() {
    if (markerLayer) {
      map.removeLayer(markerLayer);
    }

    const filtered = allFeatures.filter((f) => {
      const p = f.properties;
      const tierOk = activeTier === "All" || p.tier === activeTier;
      const priceOk = p.median_price_per_sqft >= ppsfRange[0] && p.median_price_per_sqft <= ppsfRange[1];
      return tierOk && priceOk;
    });

    markerLayer = filtered.length > CLUSTER_THRESHOLD ? L.markerClusterGroup() : L.layerGroup();
    filtered.forEach((f) => markerLayer.addLayer(buildMarker(f)));
    map.addLayer(markerLayer);
  }

  function setupTierFilter() {
    const buttons = document.querySelectorAll(".tier-btn");
    buttons.forEach((btn) => {
      btn.addEventListener("click", () => {
        activeTier = btn.dataset.tier;
        buttons.forEach((b) => b.classList.toggle("!border-bp-accent", b === btn));
        buttons.forEach((b) => b.classList.toggle("!text-bp-accent", b === btn));
        render();
      });
    });
    buttons[0].classList.add("!border-bp-accent", "!text-bp-accent");
  }

  function setupPriceSlider() {
    const values = allFeatures.map((f) => f.properties.median_price_per_sqft).filter((v) => v > 0);
    const min = Math.floor(Math.min(...values) || 0);
    const max = Math.ceil(Math.max(...values) || 1);
    ppsfRange = [min, max];

    const minInput = document.getElementById("ppsf-min");
    const maxInput = document.getElementById("ppsf-max");
    const minLabel = document.getElementById("ppsf-min-label");
    const maxLabel = document.getElementById("ppsf-max-label");

    [minInput, maxInput].forEach((el) => {
      el.min = min;
      el.max = max;
    });
    minInput.value = min;
    maxInput.value = max;
    minLabel.textContent = `Rs ${min.toLocaleString("en-IN")}`;
    maxLabel.textContent = `Rs ${max.toLocaleString("en-IN")}`;

    function onSlide() {
      let lo = Number(minInput.value);
      let hi = Number(maxInput.value);
      if (lo > hi) [lo, hi] = [hi, lo];
      ppsfRange = [lo, hi];
      minLabel.textContent = `Rs ${lo.toLocaleString("en-IN")}`;
      maxLabel.textContent = `Rs ${hi.toLocaleString("en-IN")}`;
      render();
    }

    minInput.addEventListener("input", onSlide);
    maxInput.addEventListener("input", onSlide);
  }

  fetch("/analytics/api/geo/")
    .then((res) => res.json())
    .then((geojson) => {
      allFeatures = geojson.features;
      setupTierFilter();
      setupPriceSlider();
      render();
    });
})();
