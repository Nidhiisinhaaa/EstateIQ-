"""
Upserts ModelMetric rows from ml_pipeline/artifacts/model_report.json.

Run after any retrain (Phase 3 --step train, or the Phase 8 retrain view) so the Model Report
page reflects the latest comparison without a manual step.
"""

import json
from datetime import datetime, timezone

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime

from predictor.models import ModelMetric


class Command(BaseCommand):
    help = "Upsert ModelMetric rows from ml_pipeline/artifacts/model_report.json"

    def handle(self, *args, **options):
        report_path = settings.ML_ARTIFACTS_DIR / "model_report.json"
        meta_path = settings.ML_ARTIFACTS_DIR / "model_meta.json"
        if not report_path.exists():
            raise CommandError(
                f"{report_path} not found. Run the ML pipeline first: "
                f"python ml_pipeline/run_pipeline.py --step train"
            )

        with open(report_path) as f:
            report = json.load(f)

        trained_at = datetime.now(timezone.utc)
        if meta_path.exists():
            with open(meta_path) as f:
                meta = json.load(f)
            parsed = parse_datetime(meta.get("trained_at", ""))
            if parsed:
                trained_at = parsed

        updated, created = 0, 0
        for entry in report:
            obj, was_created = ModelMetric.objects.update_or_create(
                model_name=entry["name"],
                defaults={
                    "params": entry.get("params", {}),
                    "mae": entry["mae"],
                    "rmse": entry["rmse"],
                    "r2": entry["r2"],
                    "mape": entry["mape"],
                    "cv_r2_mean": entry["cv_r2_mean"],
                    "cv_r2_std": entry.get("cv_r2_std", 0),
                    "train_seconds": entry["train_seconds"],
                    "is_best": entry.get("is_best", False),
                    "trained_at": trained_at,
                },
            )
            created += int(was_created)
            updated += int(not was_created)

        self.stdout.write(self.style.SUCCESS(
            f"Synced {len(report)} model metrics ({created} created, {updated} updated)"
        ))
