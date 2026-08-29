// Charcoal + Gold global Chart.js configuration + Indian lakh/crore number formatting.
// Loaded once; every chart on the analytics dashboard reuses these defaults.

const BP_COLORS = {
  accent: "#D4AF37",
  accentSoft: "#B8860B",
  highlight: "#FACC15",
  up: "#34D399",
  down: "#F87171",
  line: "#333333",
  text: "#F5F5F5",
  muted: "#A3A3A3",
  surface: "#1C1C1C",
};

const BP_PALETTE = ["#D4AF37", "#34D399", "#FACC15", "#B8860B", "#F87171", "#A3A3A3"];

function inrShort(value) {
  const n = Number(value);
  if (Number.isNaN(n)) return String(value);
  const sign = n < 0 ? "-" : "";
  const abs = Math.abs(n);
  if (abs >= 1_00_00_000) return `${sign}${(abs / 1_00_00_000).toFixed(2)} Cr`;
  if (abs >= 1_00_000) return `${sign}${(abs / 1_00_000).toFixed(2)} L`;
  if (abs >= 1000) return `${sign}${(abs / 1000).toFixed(1)}k`;
  return `${sign}${abs.toFixed(0)}`;
}

if (window.Chart) {
  Chart.defaults.color = BP_COLORS.muted;
  Chart.defaults.borderColor = BP_COLORS.line;
  Chart.defaults.font.family = "'JetBrains Mono', monospace";
  Chart.defaults.font.size = 11;
  Chart.defaults.plugins.legend.labels.color = BP_COLORS.text;
  Chart.defaults.plugins.tooltip.backgroundColor = BP_COLORS.surface;
  Chart.defaults.plugins.tooltip.borderColor = BP_COLORS.line;
  Chart.defaults.plugins.tooltip.borderWidth = 1;
  Chart.defaults.plugins.tooltip.titleColor = BP_COLORS.text;
  Chart.defaults.plugins.tooltip.bodyColor = BP_COLORS.text;
  Chart.defaults.plugins.tooltip.padding = 10;
}

const BP_CURRENCY_TOOLTIP = {
  callbacks: {
    label(ctx) {
      const raw = ctx.parsed.y ?? ctx.parsed.x ?? ctx.parsed;
      const label = ctx.dataset.label ? `${ctx.dataset.label}: ` : "";
      return `${label}${inrShort(raw)}`;
    },
  },
};
