"""
Phase 2, Part A -- Exploratory data analysis.

Reads the Phase 1 cleaned dataset and produces:
  - Blueprint Slate-styled PNG charts in ml_pipeline/artifacts/eda/
  - a companion eda_summary.json with the numeric findings, so the Django UI can render
    headline insights later without re-reading the CSV.

Pure pandas/numpy/matplotlib. No Django imports.
"""

import json
import logging
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s  %(message)s")
logger = logging.getLogger("eda")

BASE_DIR = Path(__file__).resolve().parent.parent
CLEAN_CSV = BASE_DIR / "data" / "processed" / "properties_clean.csv"
EDA_DIR = BASE_DIR / "artifacts" / "eda"
SUMMARY_JSON = BASE_DIR / "artifacts" / "eda_summary.json"

DPI = 150

# Blueprint Slate palette
BP_BASE = "#0B1420"
BP_SURFACE = "#121F30"
BP_LINE = "#24384F"
BP_ACCENT = "#4FA3E3"
BP_UP = "#3FD8A4"
BP_DOWN = "#E5646E"
BP_TEXT = "#E6EEF7"
BP_MUTED = "#8CA3BB"

CATEGORICAL_ACCENTS = [BP_ACCENT, BP_UP, "#7FBFEF", "#2A5F8C", BP_DOWN]


def _apply_blueprint_style():
    plt.rcParams.update({
        "figure.facecolor": BP_BASE,
        "savefig.facecolor": BP_BASE,
        "axes.facecolor": BP_BASE,
        "axes.edgecolor": BP_LINE,
        "axes.labelcolor": BP_TEXT,
        "axes.titlecolor": BP_TEXT,
        "text.color": BP_TEXT,
        "xtick.color": BP_MUTED,
        "ytick.color": BP_MUTED,
        "grid.color": BP_LINE,
        "grid.alpha": 0.6,
        "axes.grid": True,
        "axes.axisbelow": True,
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "DejaVu Sans"],
        "font.size": 10,
        "axes.titlesize": 13,
        "axes.titleweight": "600",
        "figure.titlesize": 14,
    })


def _save(fig, name: str):
    path = EDA_DIR / name
    fig.tight_layout()
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    logger.info("Saved %s", path)


def plot_price_distribution(df, summary):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    axes[0].hist(df["price_inr"] / 1e5, bins=40, color=BP_ACCENT, edgecolor=BP_BASE)
    axes[0].set_title("Price Distribution (Lakhs)")
    axes[0].set_xlabel("Price (Lakhs INR)")
    axes[0].set_ylabel("Listings")

    log_price = np.log1p(df["price_inr"])
    axes[1].hist(log_price, bins=40, color=BP_UP, edgecolor=BP_BASE)
    axes[1].set_title("Log-Scaled Price Distribution")
    axes[1].set_xlabel("log(1 + price_inr)")
    axes[1].set_ylabel("Listings")

    fig.suptitle("Price Distribution -- Raw vs Log-Scaled")
    _save(fig, "price_distribution.png")

    summary["price_lakhs"] = {
        "median": round(float((df["price_inr"] / 1e5).median()), 2),
        "mean": round(float((df["price_inr"] / 1e5).mean()), 2),
        "std": round(float((df["price_inr"] / 1e5).std()), 2),
    }


def plot_price_per_sqft_distribution(df, summary):
    ppsf = df["price_per_sqft"]
    mean, std = ppsf.mean(), ppsf.std()
    lower, upper = mean - std, mean + std

    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.hist(ppsf, bins=50, color=BP_ACCENT, edgecolor=BP_BASE)
    ax.axvline(lower, color=BP_DOWN, linestyle="--", linewidth=1.2, label=f"mean - 1 std ({lower:,.0f})")
    ax.axvline(upper, color=BP_DOWN, linestyle="--", linewidth=1.2, label=f"mean + 1 std ({upper:,.0f})")
    ax.axvline(mean, color=BP_UP, linestyle="-", linewidth=1.2, label=f"mean ({mean:,.0f})")
    ax.set_title("Price per Sqft Distribution (post per-location outlier removal)")
    ax.set_xlabel("Price per sqft (INR)")
    ax.set_ylabel("Listings")
    ax.legend(facecolor=BP_SURFACE, edgecolor=BP_LINE, labelcolor=BP_TEXT, fontsize=8)
    _save(fig, "price_per_sqft_distribution.png")

    summary["price_per_sqft"] = {
        "median": round(float(ppsf.median()), 2),
        "mean": round(float(mean), 2),
        "std": round(float(std), 2),
        "cut_lower": round(float(lower), 2),
        "cut_upper": round(float(upper), 2),
    }


def plot_top_locations_by_count(df, summary):
    top = df["location"].value_counts().head(15).sort_values()
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.barh(top.index, top.values, color=BP_ACCENT)
    ax.set_title("Top 15 Locations by Listing Count")
    ax.set_xlabel("Listings")
    _save(fig, "top_locations_by_count.png")

    summary["top_locations_by_count"] = [
        {"location": k, "count": int(v)} for k, v in top.sort_values(ascending=False).items()
    ]


def plot_location_price_extremes(df, summary):
    medians = df.groupby("location")["price_per_sqft"].median()
    counts = df["location"].value_counts()
    eligible = medians[counts >= 10]  # ignore very small samples for a "typical price" ranking

    top15 = eligible.sort_values(ascending=False).head(15)
    bottom15 = eligible.sort_values(ascending=True).head(15)

    fig, axes = plt.subplots(1, 2, figsize=(13, 6))
    axes[0].barh(top15.sort_values().index, top15.sort_values().values, color=BP_UP)
    axes[0].set_title("Top 15 Locations by Median Price/Sqft")
    axes[0].set_xlabel("Median price per sqft (INR)")

    axes[1].barh(bottom15.sort_values(ascending=False).index, bottom15.sort_values(ascending=False).values, color=BP_DOWN)
    axes[1].set_title("Bottom 15 Locations by Median Price/Sqft")
    axes[1].set_xlabel("Median price per sqft (INR)")

    _save(fig, "location_price_extremes.png")

    summary["top_locations_by_median_ppsf"] = [
        {"location": k, "median_price_per_sqft": round(float(v), 2)} for k, v in top15.items()
    ]
    summary["bottom_locations_by_median_ppsf"] = [
        {"location": k, "median_price_per_sqft": round(float(v), 2)} for k, v in bottom15.items()
    ]


def plot_bhk_vs_price(df, summary):
    fig, ax = plt.subplots(figsize=(9, 5))
    order = sorted(df["bhk"].unique())
    data = [df.loc[df["bhk"] == b, "price_inr"] / 1e5 for b in order]
    bp = ax.boxplot(data, tick_labels=[str(b) for b in order], patch_artist=True)
    for patch in bp["boxes"]:
        patch.set_facecolor(BP_ACCENT)
        patch.set_edgecolor(BP_TEXT)
        patch.set_alpha(0.75)
    for element in ["whiskers", "caps", "medians"]:
        for line in bp[element]:
            line.set_color(BP_TEXT)
    ax.set_title("BHK vs Price")
    ax.set_xlabel("BHK")
    ax.set_ylabel("Price (Lakhs INR)")
    _save(fig, "bhk_vs_price.png")

    summary["bhk_price_median_lakhs"] = {
        str(b): round(float((df.loc[df["bhk"] == b, "price_inr"] / 1e5).median()), 2) for b in order
    }


def plot_sqft_vs_price(df, summary):
    fig, ax = plt.subplots(figsize=(9, 6))
    sample = df.sample(n=min(3000, len(df)), random_state=42)
    scatter = ax.scatter(
        sample["total_sqft"], sample["price_inr"] / 1e5,
        c=sample["bhk"], cmap="cool", s=14, alpha=0.7, edgecolors="none",
    )
    cbar = fig.colorbar(scatter, ax=ax)
    cbar.set_label("BHK", color=BP_TEXT)
    cbar.ax.yaxis.set_tick_params(color=BP_MUTED)
    plt.setp(plt.getp(cbar.ax.axes, "yticklabels"), color=BP_MUTED)
    ax.set_title("Total Sqft vs Price, coloured by BHK")
    ax.set_xlabel("Total sqft")
    ax.set_ylabel("Price (Lakhs INR)")
    _save(fig, "sqft_vs_price.png")


def plot_correlation_heatmap(df, summary):
    numeric_cols = ["total_sqft", "bath", "balcony", "bhk", "price_per_sqft", "price_inr"]
    numeric_cols = [c for c in numeric_cols if c in df.columns]
    corr = df[numeric_cols].corr()

    fig, ax = plt.subplots(figsize=(7, 6))
    sns.heatmap(
        corr, annot=True, fmt=".2f", cmap="coolwarm", center=0,
        cbar_kws={"label": "Correlation"}, ax=ax,
        annot_kws={"color": BP_BASE, "fontsize": 9, "weight": "bold"},
    )
    ax.set_title("Correlation Heatmap -- Numeric Features")
    _save(fig, "correlation_heatmap.png")

    summary["correlation_matrix"] = {
        row: {col: round(float(val), 3) for col, val in corr.loc[row].items()} for row in corr.index
    }


def run():
    logger.info("Loading cleaned dataset from %s", CLEAN_CSV)
    df = pd.read_csv(CLEAN_CSV)
    EDA_DIR.mkdir(parents=True, exist_ok=True)
    _apply_blueprint_style()

    summary = {
        "counts": {
            "total_rows": int(len(df)),
            "unique_locations": int(df["location"].nunique()),
        }
    }

    plot_price_distribution(df, summary)
    plot_price_per_sqft_distribution(df, summary)
    plot_top_locations_by_count(df, summary)
    plot_location_price_extremes(df, summary)
    plot_bhk_vs_price(df, summary)
    plot_sqft_vs_price(df, summary)
    plot_correlation_heatmap(df, summary)

    with open(SUMMARY_JSON, "w") as f:
        json.dump(summary, f, indent=2)
    logger.info("Wrote EDA summary: %s", SUMMARY_JSON)

    return summary


if __name__ == "__main__":
    run()
