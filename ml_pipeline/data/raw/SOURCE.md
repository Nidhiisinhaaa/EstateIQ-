# Raw dataset source note

`properties_raw.csv` in this directory is a **synthetically generated** dataset produced by
`ml_pipeline/notebooks/generate_synthetic_dataset.py`. It was created for this project because no
scraped Kaggle-style CSV (e.g. the Bengaluru House Price dataset) was supplied at build time.

The generator reproduces the same messy real-world structure as the common Bengaluru/Mumbai
Kaggle housing datasets on purpose, so the Phase 1 cleaning pipeline has genuine work to do:

- `size` as free text ("2 BHK", "3 Bedroom")
- `total_sqft` as ranges ("1200 - 1400"), alternate units ("34.46Sq. Meter", "5Perch"), and a
  handful of unparseable strings
- a `society` column with heavy nulls (intentionally, to exercise the "drop columns with
  excessive nulls" rule)
- a long tail of rare localities (to exercise the "locations with < 10 listings become Other" rule)
- injected outliers (undersized floor plans, mismatched bath/bhk counts, per-location price
  spikes) to exercise every outlier-removal rule in `01_clean.py`

Prices are generated from a location-tier base rate (Premium / Mid / Budget) plus size and noise,
so the resulting features carry a genuine learnable signal for Phase 3 model training.

**For a real academic submission**, replace this file with an actual scraped dataset (for example
the Kaggle "Bengaluru House Price Data" CSV) using the same column names -- the pipeline does not
care how the file was produced, only that its columns match. Regenerate with:

    python ml_pipeline/notebooks/generate_synthetic_dataset.py
