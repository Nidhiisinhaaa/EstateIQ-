"""
Phase 3 -- Model training and comparison.

Trains five regression models on the Phase 2 feature matrix, evaluates each on the held-out
test split plus 5-fold cross-validation, tunes the decision tree and the three tree-ensemble
models (Random Forest, Gradient Boosting, XGBoost) with a small GridSearchCV, and persists the
winner (lowest test RMSE) as the artifact the Django predictor loads.

Pure pandas/numpy/scikit-learn/xgboost. No Django imports.
"""

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import (
    mean_absolute_error,
    mean_absolute_percentage_error,
    mean_squared_error,
    r2_score,
)
from sklearn.model_selection import GridSearchCV, cross_val_score
from sklearn.tree import DecisionTreeRegressor
from xgboost import XGBRegressor

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s  %(message)s")
logger = logging.getLogger("train")

SEED = 42
np.random.seed(SEED)

BASE_DIR = Path(__file__).resolve().parent.parent
FEATURES_CSV = BASE_DIR / "data" / "processed" / "features.csv"
ARTIFACTS_DIR = BASE_DIR / "artifacts"
EDA_DIR = ARTIFACTS_DIR / "eda"

FEATURE_COLUMNS_JSON = ARTIFACTS_DIR / "feature_columns.json"
SPLIT_INDICES_JSON = ARTIFACTS_DIR / "split_indices.json"

MODEL_REPORT_JSON = ARTIFACTS_DIR / "model_report.json"
BEST_MODEL_PATH = ARTIFACTS_DIR / "best_model.joblib"
MODEL_META_JSON = ARTIFACTS_DIR / "model_meta.json"

TARGET_COL = "price_inr"
CV_FOLDS = 5

BP_ACCENT = "#4FA3E3"
BP_UP = "#3FD8A4"
BP_DOWN = "#E5646E"
BP_BASE = "#0B1420"
BP_LINE = "#24384F"
BP_TEXT = "#E6EEF7"
BP_MUTED = "#8CA3BB"


def _apply_blueprint_style():
    plt.rcParams.update({
        "figure.facecolor": BP_BASE, "savefig.facecolor": BP_BASE, "axes.facecolor": BP_BASE,
        "axes.edgecolor": BP_LINE, "axes.labelcolor": BP_TEXT, "axes.titlecolor": BP_TEXT,
        "text.color": BP_TEXT, "xtick.color": BP_MUTED, "ytick.color": BP_MUTED,
        "grid.color": BP_LINE, "grid.alpha": 0.6, "axes.grid": True, "axes.axisbelow": True,
        "font.size": 10, "axes.titlesize": 12, "axes.titleweight": "600",
    })


def _load_data():
    df = pd.read_csv(FEATURES_CSV)
    with open(FEATURE_COLUMNS_JSON) as f:
        feature_columns = json.load(f)
    with open(SPLIT_INDICES_JSON) as f:
        split = json.load(f)

    train_idx = [i for i in split["train"] if i in df.index]
    test_idx = [i for i in split["test"] if i in df.index]

    X_train = df.loc[train_idx, feature_columns]
    y_train = df.loc[train_idx, TARGET_COL]
    X_test = df.loc[test_idx, feature_columns]
    y_test = df.loc[test_idx, TARGET_COL]
    return X_train, X_test, y_train, y_test, feature_columns


def _evaluate(name, estimator, X_train, y_train, X_test, y_test, params, train_seconds, cv_r2_mean=None, cv_r2_std=None):
    y_pred = estimator.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
    r2 = r2_score(y_test, y_pred)
    mape = mean_absolute_percentage_error(y_test, y_pred) * 100

    if cv_r2_mean is None:
        scores = cross_val_score(estimator, X_train, y_train, cv=CV_FOLDS, scoring="r2", n_jobs=-1)
        cv_r2_mean, cv_r2_std = float(scores.mean()), float(scores.std())

    result = {
        "name": name,
        "params": params,
        "mae": round(float(mae), 2),
        "rmse": round(rmse, 2),
        "r2": round(float(r2), 4),
        "mape": round(float(mape), 2),
        "cv_r2_mean": round(float(cv_r2_mean), 4),
        "cv_r2_std": round(float(cv_r2_std), 4),
        "train_seconds": round(train_seconds, 3),
        "is_best": False,
    }
    logger.info(
        "%-28s RMSE=%-14.0f MAE=%-14.0f R2=%-7.4f MAPE=%-7.2f%% CV-R2=%.4f+/-%.4f  (%.2fs)",
        name, rmse, mae, r2, mape, cv_r2_mean, cv_r2_std, train_seconds,
    )
    return result, y_pred


def run():
    logger.info("Loading feature matrix from %s", FEATURES_CSV)
    X_train, X_test, y_train, y_test, feature_columns = _load_data()
    logger.info("Train rows=%d  Test rows=%d  Features=%d", len(X_train), len(X_test), len(feature_columns))

    results = []
    fitted_models = {}
    predictions = {}

    # 1. Linear Regression -- no hyperparameters to tune.
    t0 = time.perf_counter()
    lr = LinearRegression()
    lr.fit(X_train, y_train)
    train_seconds = time.perf_counter() - t0
    res, pred = _evaluate("Linear Regression", lr, X_train, y_train, X_test, y_test, {}, train_seconds)
    results.append(res)
    fitted_models["Linear Regression"] = lr
    predictions["Linear Regression"] = pred

    # 2. Decision Tree -- tuned on max_depth / min_samples_leaf.
    t0 = time.perf_counter()
    dt_grid = GridSearchCV(
        DecisionTreeRegressor(random_state=SEED),
        param_grid={"max_depth": [5, 10, 15, None], "min_samples_leaf": [1, 5, 10]},
        cv=CV_FOLDS, scoring="r2", n_jobs=-1,
    )
    dt_grid.fit(X_train, y_train)
    train_seconds = time.perf_counter() - t0
    best_idx = dt_grid.best_index_
    res, pred = _evaluate(
        "Decision Tree", dt_grid.best_estimator_, X_train, y_train, X_test, y_test,
        dt_grid.best_params_, train_seconds,
        dt_grid.cv_results_["mean_test_score"][best_idx], dt_grid.cv_results_["std_test_score"][best_idx],
    )
    results.append(res)
    fitted_models["Decision Tree"] = dt_grid.best_estimator_
    predictions["Decision Tree"] = pred

    # 3. Random Forest (tree ensemble #1) -- small grid, kept modest to respect the ~5 min budget.
    #    min_samples_leaf is fixed rather than gridded: it contributed little variance in an
    #    initial wider sweep but tripled the grid's fit count.
    t0 = time.perf_counter()
    rf_grid = GridSearchCV(
        RandomForestRegressor(random_state=SEED, n_jobs=-1, min_samples_leaf=2),
        param_grid={"n_estimators": [100, 150], "max_depth": [15, None]},
        cv=CV_FOLDS, scoring="r2", n_jobs=-1,
    )
    rf_grid.fit(X_train, y_train)
    train_seconds = time.perf_counter() - t0
    best_idx = rf_grid.best_index_
    res, pred = _evaluate(
        "Random Forest", rf_grid.best_estimator_, X_train, y_train, X_test, y_test,
        rf_grid.best_params_, train_seconds,
        rf_grid.cv_results_["mean_test_score"][best_idx], rf_grid.cv_results_["std_test_score"][best_idx],
    )
    results.append(res)
    fitted_models["Random Forest"] = rf_grid.best_estimator_
    predictions["Random Forest"] = pred

    # 4. Gradient Boosting (tree ensemble #2). max_depth fixed at 3 (the sklearn default and the
    #    typical sweet spot for boosted trees) to keep the grid small.
    t0 = time.perf_counter()
    gb_grid = GridSearchCV(
        GradientBoostingRegressor(random_state=SEED, max_depth=3),
        param_grid={"n_estimators": [100, 150], "learning_rate": [0.05, 0.1]},
        cv=CV_FOLDS, scoring="r2", n_jobs=-1,
    )
    gb_grid.fit(X_train, y_train)
    train_seconds = time.perf_counter() - t0
    best_idx = gb_grid.best_index_
    res, pred = _evaluate(
        "Gradient Boosting", gb_grid.best_estimator_, X_train, y_train, X_test, y_test,
        gb_grid.best_params_, train_seconds,
        gb_grid.cv_results_["mean_test_score"][best_idx], gb_grid.cv_results_["std_test_score"][best_idx],
    )
    results.append(res)
    fitted_models["Gradient Boosting"] = gb_grid.best_estimator_
    predictions["Gradient Boosting"] = pred

    # 5. XGBoost (tree ensemble #3). max_depth fixed at 4 to keep the grid small.
    t0 = time.perf_counter()
    xgb_grid = GridSearchCV(
        XGBRegressor(random_state=SEED, n_jobs=-1, verbosity=0, max_depth=4),
        param_grid={"n_estimators": [100, 150], "learning_rate": [0.05, 0.1]},
        cv=CV_FOLDS, scoring="r2", n_jobs=-1,
    )
    xgb_grid.fit(X_train, y_train)
    train_seconds = time.perf_counter() - t0
    best_idx = xgb_grid.best_index_
    res, pred = _evaluate(
        "XGBoost", xgb_grid.best_estimator_, X_train, y_train, X_test, y_test,
        xgb_grid.best_params_, train_seconds,
        xgb_grid.cv_results_["mean_test_score"][best_idx], xgb_grid.cv_results_["std_test_score"][best_idx],
    )
    results.append(res)
    fitted_models["XGBoost"] = xgb_grid.best_estimator_
    predictions["XGBoost"] = pred

    # Rank by test RMSE ascending; the winner is deployed.
    results.sort(key=lambda r: r["rmse"])
    results[0]["is_best"] = True
    best_name = results[0]["name"]
    best_model = fitted_models[best_name]
    best_pred = predictions[best_name]
    logger.info("Best model by test RMSE: %s", best_name)

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    EDA_DIR.mkdir(parents=True, exist_ok=True)

    with open(MODEL_REPORT_JSON, "w") as f:
        json.dump(results, f, indent=2)
    joblib.dump(best_model, BEST_MODEL_PATH)

    residuals = (y_test.values - best_pred)
    residual_std = float(np.std(residuals))
    meta = {
        "best_model_name": best_name,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "feature_count": len(feature_columns),
        "training_row_count": len(X_train),
        "rmse": results[0]["rmse"],
        "r2": results[0]["r2"],
        "residual_std": round(residual_std, 2),
    }
    with open(MODEL_META_JSON, "w") as f:
        json.dump(meta, f, indent=2)
    logger.info("Wrote model_report.json, best_model.joblib, model_meta.json")

    _apply_blueprint_style()
    _plot_model_comparison(results)
    _plot_feature_importance(best_name, best_model, feature_columns)
    _plot_actual_vs_predicted(y_test.values, best_pred, best_name)
    _plot_residuals(residuals, best_name)

    _print_comparison_table(results)

    return results


def _plot_model_comparison(results):
    names = [r["name"] for r in results]
    mae = [r["mae"] for r in results]
    rmse = [r["rmse"] for r in results]
    r2 = [r["r2"] for r in results]

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    axes[0].bar(names, mae, color=BP_ACCENT)
    axes[0].set_title("MAE (lower is better)")
    axes[0].tick_params(axis="x", rotation=30)

    axes[1].bar(names, rmse, color=BP_DOWN)
    axes[1].set_title("RMSE (lower is better)")
    axes[1].tick_params(axis="x", rotation=30)

    axes[2].bar(names, r2, color=BP_UP)
    axes[2].set_title("R-squared (higher is better)")
    axes[2].set_ylim(0, 1)
    axes[2].tick_params(axis="x", rotation=30)

    fig.suptitle("Model Comparison")
    fig.tight_layout()
    fig.savefig(EDA_DIR / "model_comparison.png", dpi=150)
    plt.close(fig)
    logger.info("Saved model_comparison.png")


def _plot_feature_importance(best_name, best_model, feature_columns):
    if hasattr(best_model, "feature_importances_"):
        importances = best_model.feature_importances_
    elif hasattr(best_model, "coef_"):
        importances = np.abs(best_model.coef_)
    else:
        logger.warning("Best model has no importances/coefficients; skipping feature_importance.png")
        return

    order = np.argsort(importances)[::-1][:20]
    top_features = [feature_columns[i] for i in order][::-1]
    top_values = [importances[i] for i in order][::-1]

    fig, ax = plt.subplots(figsize=(9, 8))
    ax.barh(top_features, top_values, color=BP_ACCENT)
    ax.set_title(f"Top 20 Feature Importances -- {best_name}")
    fig.tight_layout()
    fig.savefig(EDA_DIR / "feature_importance.png", dpi=150)
    plt.close(fig)
    logger.info("Saved feature_importance.png")


def _plot_actual_vs_predicted(y_true, y_pred, best_name):
    fig, ax = plt.subplots(figsize=(7, 7))
    ax.scatter(y_true / 1e5, y_pred / 1e5, alpha=0.4, s=14, color=BP_ACCENT, edgecolors="none")
    lims = [min(y_true.min(), y_pred.min()) / 1e5, max(y_true.max(), y_pred.max()) / 1e5]
    ax.plot(lims, lims, color=BP_UP, linestyle="--", linewidth=1.5, label="Ideal (y = x)")
    ax.set_xlabel("Actual price (Lakhs INR)")
    ax.set_ylabel("Predicted price (Lakhs INR)")
    ax.set_title(f"Actual vs Predicted -- {best_name}")
    ax.legend(facecolor=BP_BASE, edgecolor=BP_LINE, labelcolor=BP_TEXT)
    fig.tight_layout()
    fig.savefig(EDA_DIR / "actual_vs_predicted.png", dpi=150)
    plt.close(fig)
    logger.info("Saved actual_vs_predicted.png")


def _plot_residuals(residuals, best_name):
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.hist(residuals / 1e5, bins=40, color=BP_ACCENT, edgecolor=BP_BASE)
    ax.axvline(0, color=BP_DOWN, linestyle="--", linewidth=1.2)
    ax.set_xlabel("Residual (Lakhs INR, actual - predicted)")
    ax.set_ylabel("Count")
    ax.set_title(f"Residual Distribution -- {best_name}")
    fig.tight_layout()
    fig.savefig(EDA_DIR / "residuals.png", dpi=150)
    plt.close(fig)
    logger.info("Saved residuals.png")


def _print_comparison_table(results):
    headers = ["Model", "MAE", "RMSE", "R2", "MAPE%", "CV-R2", "Train(s)", "Best"]
    rows = []
    for r in results:
        rows.append([
            r["name"], f"{r['mae']:,.0f}", f"{r['rmse']:,.0f}", f"{r['r2']:.4f}",
            f"{r['mape']:.2f}", f"{r['cv_r2_mean']:.4f}+/-{r['cv_r2_std']:.4f}",
            f"{r['train_seconds']:.2f}", "YES" if r["is_best"] else "",
        ])
    widths = [max(len(headers[i]), *(len(row[i]) for row in rows)) for i in range(len(headers))]
    line = "+".join("-" * (w + 2) for w in widths)

    print("\n" + line)
    print("|" + "|".join(f" {headers[i].ljust(widths[i])} " for i in range(len(headers))) + "|")
    print(line)
    for row in rows:
        print("|" + "|".join(f" {row[i].ljust(widths[i])} " for i in range(len(headers))) + "|")
    print(line + "\n")


if __name__ == "__main__":
    run()
