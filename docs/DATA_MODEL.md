# EstateIQ Data Model

SQLite3 only. Four Django apps contribute models: `properties` (locations and listings) and
`predictor` (prediction logs and model metrics). `core` and `analytics` are query/view layers
with no dedicated models of their own -- `analytics` reads from `properties` and `predictor`.

## ER Diagram

```
+-----------------------+          +-----------------------------+
|        Location       |          |           Amenity            |
+-----------------------+          +-----------------------------+
| id (PK)               |          | id (PK)                      |
| name          (unique)|          | name          (unique)       |
| slug          (unique)|          | icon_key                     |
| tier    Premium/Mid/  |          +-----------------------------+
|         Budget        |          (lookup table only -- validates
| latitude               |          the free-form `amenities` JSON
| longitude              |          list on Property, not a FK)
| is_approximate         |
| listing_count          |
| median_price_per_sqft  |
+-----------+------------+
            | 1
            |
            | N
+-----------v------------------------------+
|                Property                   |
+--------------------------------------------+
| id (PK)                                    |
| location_id (FK -> Location)               |
| area_sqft, bhk, bathrooms, balcony         |
| floor, total_floors, age_years             |
| parking (bool)                             |
| furnishing      Unfurnished/Semi/Full      |
| property_type   Apartment/Villa/           |
|                  Independent House/Plot    |
| amenities       JSONField (list of names,  |
|                  validated against Amenity)|
| price_inr, price_per_sqft (computed on save)|
| listed_on                                   |
| source          Dataset/Manual              |
+---------------------------------------------+

+---------------------------------------------+        +----------------------------+
|               PredictionLog                  |        |         ModelMetric        |
+-----------------------------------------------+        +----------------------------+
| id (PK)                                       |        | id (PK)                    |
| user_id (FK -> auth.User, nullable)           |        | model_name (unique)        |
| session_key    (anonymous persistence)        |        | params      JSONField      |
| location_id (FK -> Location, nullable)        |        | mae, rmse, r2, mape         |
| location_name   (denormalised snapshot)       |        | cv_r2_mean, cv_r2_std       |
| area_sqft, bhk, bathrooms, balcony            |        | train_seconds               |
| floor, total_floors, age_years                |        | is_best                     |
| parking, furnishing, property_type            |        | trained_at                  |
| amenities       JSONField                     |        +----------------------------+
| predicted_price, lower_bound, upper_bound     |        (one row per model from the
| confidence_score                              |         Phase 3 comparison; upserted
| model_name, model_version                     |         by sync_model_metrics)
| created_at (indexed), ip_address              |
+------------------------------------------------+
```

## Design notes

- **Location is denormalised on purpose.** `listing_count` and `median_price_per_sqft` are
  precomputed at import time (`import_properties`) rather than aggregated live on every
  dashboard/map request, since they change only when the dataset is reimported.
- **`Property.price_per_sqft` is computed on `save()`**, not stored redundantly by callers. Bulk
  imports (which bypass `save()`) compute it manually with the same formula -- see
  `import_properties.py`.
- **`PredictionLog.location` is a nullable FK, `location_name` is a plain string snapshot.** If a
  Location is later renamed or removed, historical prediction logs still show what the user saw
  at prediction time.
- **`Amenity` is a validation lookup, not a FK target.** `Property.amenities` and
  `PredictionLog.amenities` are JSON lists of amenity names for simplicity (avoids an M2M
  through-table for what is display-only data); `Amenity` exists so those names can be validated
  against a known set.
- **`is_approximate` on Location** is set by `geocode_locations` when a locality has no entry in
  the bundled `location_coords.json` lookup and falls back to the city centroid (jittered so
  markers don't stack). The Phase 7 map renders these with a distinct hollow-ring marker.

## Management commands (in run order for a fresh clone)

1. `python manage.py migrate`
2. `python manage.py import_properties` -- reads `ml_pipeline/data/processed/properties_clean.csv`,
   upserts `Location` rows, bulk-creates `Property` rows in batches of 1000 inside a transaction.
   Idempotent: clears prior `source="Dataset"` rows first.
3. `python manage.py sync_model_metrics` -- reads `ml_pipeline/artifacts/model_report.json`,
   upserts `ModelMetric` rows.
4. `python manage.py geocode_locations` -- populates `Location.latitude/longitude` from the
   bundled static coordinate lookup, no live API calls.
