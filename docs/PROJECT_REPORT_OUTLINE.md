# Project Report Outline

Chapter-wise outline for a standard BCA/MCA project report, mapped to EstateIQ. Each chapter
lists the exact files and artifacts in this repository that supply its content, so writing the
report is a matter of transcribing and explaining what already exists rather than inventing
new material.

## 1. Introduction

- Project title, objective, and scope: `README.md` (top section).
- Problem statement: manual/ad-hoc real estate pricing lacks a data-driven, explainable
  estimate; EstateIQ addresses this with a trained regression model plus a transparent UI.
- Academic project title: **Real Estate Price Intelligence and Prediction System Using Machine
  Learning and Django**.

## 2. Literature Review

- Reference the general approach of price-prediction studies on Indian housing datasets
  (feature engineering from listing text, per-locality outlier handling, tree-ensemble
  regressors outperforming linear baselines).
- The specific outlier-removal and feature-engineering choices made here, with their
  domain rationale, are documented in code and surfaced live in the app:
  - `ml_pipeline/steps/01_clean.py` (docstrings on every cleaning rule)
  - `predictor/methodology.py` (rationale text also rendered on `/predictor/model-report/`)

## 3. System Analysis

- **Requirements:** the phase-by-phase build spec this project was built from covers scope
  precisely (data pipeline, Django data layer, prediction UI, analytics, map, transparency,
  accounts, hardening).
- **Feasibility:** SQLite3 + a CDN-only frontend keeps the system deployable on a single small
  VPS with no external services -- see `deploy/DEPLOY.md`.
- **Data source:** `ml_pipeline/data/raw/SOURCE.md` explains the dataset's provenance
  (synthetic stand-in structurally matching common Bengaluru/Mumbai Kaggle datasets) and how to
  substitute a real scraped dataset.

## 4. System Design

- **Architecture diagram:** `README.md` (ASCII diagram) and the hand-coded SVG pipeline diagram
  rendered on `/predictor/model-report/` (`templates/components/pipeline_diagram.html`).
- **Data model / ER diagram:** `docs/DATA_MODEL.md` -- Location, Property, Amenity,
  PredictionLog, ModelMetric, RetrainJob, with design notes explaining denormalisation choices.
- **Design system:** Blueprint Slate tokens in `static/css/blueprint-slate.css` and the Tailwind
  config in `templates/base.html`.
- **ML pipeline design:** the five-stage `ml_pipeline/steps/` sequence
  (`01_clean.py` -> `02_eda.py` -> `03_features.py` -> `04_train.py`), orchestrated by
  `ml_pipeline/run_pipeline.py`.
- **Feature contract:** `ml_pipeline/artifacts/feature_columns.json` is the exact, versioned
  interface between the offline training pipeline and the live Django predictor
  (`predictor/services/engine.py::build_feature_vector`), preventing training/serving skew.

## 5. Implementation

- **Data cleaning:** `ml_pipeline/steps/01_clean.py` -- unit conversion, range midpoints,
  per-location outlier filtering, with before/after row counts logged to
  `ml_pipeline/artifacts/cleaning_report.json`.
- **EDA:** `ml_pipeline/steps/02_eda.py` -- all charts in `ml_pipeline/artifacts/eda/`, numeric
  findings in `ml_pipeline/artifacts/eda_summary.json`.
- **Feature engineering:** `ml_pipeline/steps/03_features.py` -- derived features, one-hot
  encoding, StandardScaler, and the explicit exclusion of `price_per_sqft` as a model input to
  avoid target leakage (documented in the module docstring).
- **Model training and selection:** `ml_pipeline/steps/04_train.py` -- five models, GridSearchCV
  tuning, 5-fold CV, ranked by test RMSE; results in `ml_pipeline/artifacts/model_report.json`.
- **Django data layer:** `properties/models.py`, `predictor/models.py`, and the management
  commands in `properties/management/commands/` and `predictor/management/commands/`.
- **Prediction serving:** `predictor/services/engine.py` (`PredictionEngine`), `predictor/forms.py`,
  `templates/predictor/predict.html` / `result.html`.
- **Analytics dashboard:** `analytics/services/aggregates.py` (cached query functions),
  `analytics/views.py` (JSON endpoints), `templates/analytics/dashboard.html`,
  `static/js/dashboard.js` / `charts.js`.
- **Map intelligence:** `analytics/views.py::geojson_locations`, `templates/analytics/map.html`,
  `static/js/map.js`.
- **Model transparency and retraining:** `templates/predictor/model_report.html`,
  `predictor/views.py::retrain` (background-thread subprocess + `RetrainJob` status polling).
- **Accounts and exports:** `core/auth_urls.py`, `predictor/views.py` (`history`, `compare`,
  `export_prediction_pdf`, `export_history_csv`).
- **Hardening:** `estateiq/settings/{base,dev,prod}.py`, `core/middleware.py` (CSP),
  `core/decorators.py` (rate limiting).

## 6. Testing

- **Automated tests:** `tests/` (pytest-django) --
  - `test_feature_contract.py`: feature vector column order matches `feature_columns.json`.
  - `test_prediction_bounds.py`: prediction interval always brackets the point estimate.
  - `test_prediction_form.py`: form validation rejects every out-of-range input the spec lists.
  - `test_aggregates.py`: analytics aggregate functions return the expected shape on a fixture.
  - `test_urls.py`: every named URL in the project resolves.
- Run with `pytest` from the project root (`pytest.ini` configures `DJANGO_SETTINGS_MODULE`).
- **Manual verification performed during development:** end-to-end prediction flow (form submit
  -> result page -> PredictionLog row), admin CRUD for every model, full retrain job lifecycle
  (queued -> running -> success, with live log streaming), signup -> predict -> history ->
  compare -> PDF/CSV export, and a 31-request burst confirming the rate limiter's 30/hour cutoff.

## 7. Results and Discussion

- Model comparison table and discussion of why the winning model (ranked by test RMSE) performs
  best: `ml_pipeline/artifacts/model_report.json`, rendered with captions on
  `/predictor/model-report/`, and the summary table in `README.md`.
- Evaluation plots and what each demonstrates: `ml_pipeline/artifacts/eda/model_comparison.png`,
  `feature_importance.png`, `actual_vs_predicted.png`, `residuals.png` (captions in
  `templates/predictor/model_report.html` explain each one).
- Dashboard insights computed server-side (e.g. tier price comparisons, amenity price impact):
  `analytics/views.py::_build_insights`.

## 8. Conclusion and Future Scope

- Summary: a working, explainable, end-to-end price intelligence system from raw data to a
  deployed Django application, with retraining and full transparency built in.
- Future scope: see the **Limitations and Future Scope** section of `README.md` -- real dataset
  ingestion, multi-city support, moving rate limiting/job-locking to a shared cache for
  multi-worker deployments, and a nonce-based CSP.
