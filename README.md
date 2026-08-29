# EstateIQ

**Real Estate Price Intelligence and Prediction System Using Machine Learning and Django**

EstateIQ estimates residential property prices from a cleaned Indian real-estate listings
dataset, using a scikit-learn/XGBoost regression pipeline served through a Django application.
It includes a prediction form with confidence intervals, an analytics dashboard, a Leaflet
price-intelligence map, full model transparency/retraining tooling, and per-user prediction
history with PDF/CSV export.

## Stack

- **Backend:** Django 5, Python 3.11+
- **Database:** SQLite3 (no external database server)
- **ML:** pandas, numpy, scikit-learn, XGBoost, joblib
- **Frontend:** Django templates, Tailwind CSS (CDN, no build step), vanilla JS
- **Charts:** Chart.js 4 (CDN)
- **Maps:** Leaflet.js 1.9 (CDN) with CartoDB dark tiles and Leaflet.markercluster
- **Design system:** Blueprint Slate (dark, drafting/blueprint-styled, tokens in
  `static/css/blueprint-slate.css`)

## Architecture

```
                         +-------------------------------+
                         |          Browser (UI)          |
                         |  Django templates + Tailwind   |
                         |  Chart.js / Leaflet.js (CDN)   |
                         +----------------+----------------+
                                          |
                                          v
+----------------------------------------------------------------------------+
|                              Django Application                             |
|                                                                              |
|  core/        landing page, auth, decorators, CSP middleware                |
|  properties/  Location, Property, Amenity models + import/geocode commands  |
|  predictor/   PredictionForm, PredictionEngine, PredictionLog, ModelMetric,  |
|               RetrainJob, model report + retrain-control views              |
|  analytics/   cached aggregate queries, chart JSON endpoints, GeoJSON map    |
|                                                                              |
+----------------------------+-----------------------------------------------+
                              |
                              v
                    +-------------------+          +----------------------------+
                    |     db.sqlite3     |          |  ml_pipeline/artifacts/    |
                    | Location, Property,|<-------->|  best_model.joblib         |
                    | PredictionLog, ... |  loaded  |  scaler.joblib             |
                    +-------------------+   lazily  |  feature_columns.json      |
                                               by    |  model_meta.json           |
                                          PredictionEngine  location_tier_map.json|
                                                     +----------------------------+
                                                                ^
                                                                | produced by
                                                                |
                    +-----------------------------------------------------------+
                    |                    ml_pipeline/ (offline)                  |
                    |  01_clean.py -> 02_eda.py -> 03_features.py -> 04_train.py |
                    |  run via: python ml_pipeline/run_pipeline.py --step all    |
                    +-----------------------------------------------------------+
```

## Setup: clone to running server

```bash
git clone <your-repo-url> EstateIQ
cd EstateIQ

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env            # fill in SECRET_KEY etc. for a real deployment; dev works with defaults
```

### Get a dataset and run the ML pipeline

The pipeline expects a raw CSV at `ml_pipeline/data/raw/properties_raw.csv` with columns
`area_type, availability, location, size, society, total_sqft, bath, balcony, price`
(the shape of the common Bengaluru/Mumbai Kaggle housing datasets). If you don't have one,
generate a synthetic dataset with the same messy structure to develop against:

```bash
python ml_pipeline/notebooks/generate_synthetic_dataset.py
```

See `ml_pipeline/data/raw/SOURCE.md` for why this exists and how to swap in a real dataset.

Then run the full pipeline (clean -> EDA -> feature engineering -> train five models):

```bash
python ml_pipeline/run_pipeline.py --step all
```

Individual steps: `--step clean`, `--step eda`, `--step features`, `--step train`.

### Set up the database and load data

```bash
python manage.py migrate
python manage.py import_properties      # loads properties_clean.csv into Location/Property
python manage.py sync_model_metrics     # loads model_report.json into ModelMetric
python manage.py geocode_locations      # populates Location lat/lng for the map
python manage.py createsuperuser
```

### Run

```bash
python manage.py runserver
```

Visit `http://127.0.0.1:8000/`.

## Tests

```bash
pytest
```

## Deployment

See `deploy/DEPLOY.md` for the full Hostinger VPS command sequence (gunicorn + systemd + Nginx,
SQLite file permissions, backup cron line).

## Screenshots

_(Add screenshots here before submitting the project report.)_

- [ ] Home page
- [ ] Prediction form
- [ ] Prediction result
- [ ] Analytics dashboard
- [ ] Map intelligence
- [ ] Model report

## Model Results

Five regression models are trained and compared on the same 80/20 split; the lowest test-RMSE
model is deployed. Numbers below are from the last pipeline run in this repository
(`ml_pipeline/artifacts/model_report.json` is the live source of truth and updates on retrain):

| Model | MAE | RMSE | R2 | MAPE | CV R2 (mean +/- std) |
|---|---|---|---|---|---|
| **XGBoost (deployed)** | 842,640 | 1,210,221 | 0.9561 | 9.02% | 0.9505 +/- 0.0017 |
| Gradient Boosting | 877,172 | 1,218,691 | 0.9555 | 9.70% | 0.9484 +/- 0.0017 |
| Random Forest | 923,050 | 1,338,613 | 0.9463 | 9.80% | 0.9395 +/- 0.0032 |
| Decision Tree | 1,014,083 | 1,536,883 | 0.9292 | 10.52% | 0.9278 +/- 0.0055 |
| Linear Regression | 1,291,139 | 1,834,434 | 0.8992 | 17.04% | 0.8912 +/- 0.0060 |

MAE/RMSE are in INR. Full methodology (cleaning rules, engineered features, and the rationale
for each) is on the in-app Model Report page (`/predictor/model-report/`), sourced live from
`cleaning_report.json` so it can't drift from the actual pipeline.

## Limitations and Future Scope

- **Dataset is synthetic by default.** No scraped real-estate dataset was supplied for this
  build; `ml_pipeline/notebooks/generate_synthetic_dataset.py` produces a structurally realistic
  stand-in. Swapping in a genuine scraped dataset (e.g. the Kaggle Bengaluru House Price data)
  requires no code changes, only replacing the raw CSV.
- **Auxiliary Property attributes are synthesised at import time.** The source dataset schema
  doesn't include floor/age/parking/furnishing/property_type/amenities, so `import_properties`
  assigns them with a seeded random generator so the analytics (amenity impact, furnishing
  impact, etc.) have realistic variety to show. In a production deployment with a richer scraped
  source, these would come from the dataset directly.
- **Single-city scope.** The bundled dataset and geocoding fixture cover Bengaluru-style
  localities only; extending to multiple cities would need a `city` field on `Location` and a
  larger coordinate lookup (or a real geocoding API, which this project deliberately avoids to
  stay offline-reproducible).
- **CSP allows `'unsafe-inline'`** for script/style, a deliberate tradeoff documented in
  `core/middleware.py` given the no-build-step constraint on this project; a future iteration
  could move to a nonce-based CSP.
- **Single-process rate limiting.** The prediction rate limiter and the retrain "already running"
  guard both use Django's local-memory cache, which is per-process. A multi-worker gunicorn
  deployment should move both to a shared cache backend (e.g. Redis) for correctness across
  workers.
- **No time-series backtesting.** price_trend_by_month is a genuine aggregate but the underlying
  `listed_on` dates are synthesised at import time (see above), so month-over-month trend lines
  don't reflect a real market trend -- only real listings would make that meaningful.
