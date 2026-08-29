// Fetches each analytics chart's data from its JSON endpoint and renders it with Chart.js.
// No chart data is ever hardcoded in the template -- every card starts empty + skeleton and
// fills in once its endpoint resolves.

(function () {
  const commonScales = {
    x: { ticks: { color: BP_COLORS.muted }, grid: { color: BP_COLORS.line } },
    y: { ticks: { color: BP_COLORS.muted }, grid: { color: BP_COLORS.line } },
  };

  const RENDERERS = {
    "average-price-by-location": (ctx, data) => new Chart(ctx, {
      type: "bar",
      data: {
        labels: data.map((r) => r.location),
        datasets: [{ label: "Average Price", data: data.map((r) => r.average_price), backgroundColor: BP_COLORS.accent }],
      },
      options: {
        indexAxis: "y",
        scales: commonScales,
        plugins: { legend: { display: false }, tooltip: BP_CURRENCY_TOOLTIP },
      },
    }),

    "price-per-sqft-by-location": (ctx, data) => new Chart(ctx, {
      type: "bar",
      data: {
        labels: data.map((r) => r.location),
        datasets: [{ label: "Price/Sqft", data: data.map((r) => r.price_per_sqft), backgroundColor: BP_COLORS.accentSoft }],
      },
      options: {
        indexAxis: "y",
        scales: commonScales,
        plugins: { legend: { display: false }, tooltip: BP_CURRENCY_TOOLTIP },
      },
    }),

    "bhk-price-distribution": (ctx, data) => new Chart(ctx, {
      type: "bar",
      data: {
        labels: data.map((r) => `${r.bhk} BHK`),
        datasets: [{ label: "Average Price", data: data.map((r) => r.average_price), backgroundColor: BP_COLORS.accent }],
      },
      options: { scales: commonScales, plugins: { legend: { display: false }, tooltip: BP_CURRENCY_TOOLTIP } },
    }),

    "property-type-distribution": (ctx, data) => new Chart(ctx, {
      type: "doughnut",
      data: {
        labels: data.map((r) => r.property_type),
        datasets: [{ data: data.map((r) => r.count), backgroundColor: BP_PALETTE, borderColor: BP_COLORS.surface, borderWidth: 2 }],
      },
      options: { plugins: { legend: { position: "bottom", labels: { color: BP_COLORS.text } } } },
    }),

    "price-trend": (ctx, data) => new Chart(ctx, {
      type: "line",
      data: {
        labels: data.listings.map((r) => r.month),
        datasets: [
          {
            label: "Listings (avg price)",
            data: data.listings.map((r) => r.average_price),
            borderColor: BP_COLORS.accent,
            backgroundColor: "transparent",
            tension: 0.3,
          },
          {
            label: "Predictions (avg price)",
            data: data.predictions.map((r) => r.average_price),
            borderColor: BP_COLORS.up,
            backgroundColor: "transparent",
            tension: 0.3,
          },
        ],
      },
      options: { scales: commonScales, plugins: { tooltip: BP_CURRENCY_TOOLTIP } },
    }),

    "most-expensive-locations": (ctx, data) => new Chart(ctx, {
      type: "bar",
      data: {
        labels: data.map((r) => r.location),
        datasets: [{ label: "Price/Sqft", data: data.map((r) => r.price_per_sqft), backgroundColor: BP_COLORS.up }],
      },
      options: {
        indexAxis: "y",
        scales: commonScales,
        plugins: { legend: { display: false }, tooltip: BP_CURRENCY_TOOLTIP },
      },
    }),

    "most-affordable-locations": (ctx, data) => new Chart(ctx, {
      type: "bar",
      data: {
        labels: data.map((r) => r.location),
        datasets: [{ label: "Price/Sqft", data: data.map((r) => r.price_per_sqft), backgroundColor: BP_COLORS.down }],
      },
      options: {
        indexAxis: "y",
        scales: commonScales,
        plugins: { legend: { display: false }, tooltip: BP_CURRENCY_TOOLTIP },
      },
    }),

    "amenity-price-impact": (ctx, data) => new Chart(ctx, {
      type: "bar",
      data: {
        labels: data.map((r) => r.amenity),
        datasets: [{
          label: "Price delta %",
          data: data.map((r) => r.delta_percent),
          backgroundColor: data.map((r) => (r.delta_percent >= 0 ? BP_COLORS.up : BP_COLORS.down)),
        }],
      },
      options: {
        indexAxis: "y",
        scales: commonScales,
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: (c) => `${c.parsed.x >= 0 ? "+" : ""}${c.parsed.x}%` } },
        },
      },
    }),

    "furnishing-price-impact": (ctx, data) => new Chart(ctx, {
      type: "bar",
      data: {
        labels: data.map((r) => r.furnishing),
        datasets: [{ label: "Average Price", data: data.map((r) => r.average_price), backgroundColor: BP_COLORS.accent }],
      },
      options: { scales: commonScales, plugins: { legend: { display: false }, tooltip: BP_CURRENCY_TOOLTIP } },
    }),

    "tier-price-comparison": (ctx, data) => new Chart(ctx, {
      type: "bar",
      data: {
        labels: data.map((r) => r.tier),
        datasets: [{
          label: "Median Price/Sqft",
          data: data.map((r) => r.median_price_per_sqft),
          backgroundColor: [BP_COLORS.accent, BP_COLORS.accentSoft, BP_COLORS.muted],
        }],
      },
      options: { scales: commonScales, plugins: { legend: { display: false }, tooltip: BP_CURRENCY_TOOLTIP } },
    }),
  };

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-chart-card]").forEach((card) => {
      const slug = card.dataset.slug;
      const skeleton = card.querySelector("[data-skeleton]");
      const canvas = card.querySelector("[data-canvas]");
      const renderer = RENDERERS[slug];

      fetch(`/analytics/api/${slug}/`)
        .then((res) => res.json())
        .then((payload) => {
          if (skeleton) skeleton.remove();
          canvas.classList.remove("hidden");
          if (renderer) renderer(canvas.getContext("2d"), payload.data);
        })
        .catch(() => {
          if (skeleton) {
            skeleton.textContent = "Failed to load";
            skeleton.classList.remove("bp-skeleton");
          }
        });
    });
  });
})();
