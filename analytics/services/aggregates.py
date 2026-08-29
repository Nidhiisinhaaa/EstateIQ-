"""
Pure query functions backing the Phase 6 analytics dashboard. Every function returns a
JSON-serialisable dict/list and is cached in Django's local-memory cache for 15 minutes, since
these aggregates change only when the dataset is reimported or a new prediction is logged --
not on every request.
"""

import statistics

from django.core.cache import cache
from django.db.models import Avg, Count
from django.db.models.functions import TruncMonth

from predictor.models import PredictionLog
from properties.models import Amenity, Location, Property

CACHE_TTL_SECONDS = 60 * 15
MIN_LISTINGS_FOR_RANKING = 5  # avoid a 1-listing location topping "most expensive" by noise


def _cached(key, builder):
    value = cache.get(key)
    if value is None:
        value = builder()
        cache.set(key, value, CACHE_TTL_SECONDS)
    return value


def average_price_by_location(limit=15):
    def build():
        qs = (
            Property.objects.values("location__name")
            .annotate(avg_price=Avg("price_inr"), count=Count("id"))
            .order_by("-avg_price")[:limit]
        )
        return [
            {"location": row["location__name"], "average_price": round(float(row["avg_price"]), 2), "count": row["count"]}
            for row in qs
        ]
    return _cached(f"agg:avg_price_by_location:{limit}", build)


def price_per_sqft_by_location(limit=15, order="desc"):
    def build():
        qs = Property.objects.values("location__name").annotate(avg_ppsf=Avg("price_per_sqft"), count=Count("id"))
        qs = qs.order_by("-avg_ppsf" if order == "desc" else "avg_ppsf")[:limit]
        return [
            {"location": row["location__name"], "price_per_sqft": round(float(row["avg_ppsf"]), 2), "count": row["count"]}
            for row in qs
        ]
    return _cached(f"agg:ppsf_by_location:{limit}:{order}", build)


def bhk_price_distribution():
    def build():
        qs = Property.objects.values("bhk").annotate(avg_price=Avg("price_inr"), count=Count("id")).order_by("bhk")
        return [
            {"bhk": row["bhk"], "average_price": round(float(row["avg_price"]), 2), "count": row["count"]}
            for row in qs
        ]
    return _cached("agg:bhk_price_distribution", build)


def property_type_distribution():
    def build():
        qs = Property.objects.values("property_type").annotate(count=Count("id")).order_by("-count")
        total = sum(row["count"] for row in qs) or 1
        return [
            {"property_type": row["property_type"], "count": row["count"], "share": round(100 * row["count"] / total, 1)}
            for row in qs
        ]
    return _cached("agg:property_type_distribution", build)


def price_trend_by_month():
    def build():
        props = (
            Property.objects.annotate(month=TruncMonth("listed_on"))
            .values("month")
            .annotate(avg_price=Avg("price_inr"), count=Count("id"))
            .order_by("month")
        )
        preds = (
            PredictionLog.objects.annotate(month=TruncMonth("created_at"))
            .values("month")
            .annotate(avg_price=Avg("predicted_price"), count=Count("id"))
            .order_by("month")
        )
        return {
            "listings": [
                {"month": row["month"].strftime("%Y-%m"), "average_price": round(float(row["avg_price"]), 2), "count": row["count"]}
                for row in props if row["month"]
            ],
            "predictions": [
                {"month": row["month"].strftime("%Y-%m"), "average_price": round(float(row["avg_price"]), 2), "count": row["count"]}
                for row in preds if row["month"]
            ],
        }
    return _cached("agg:price_trend_by_month", build)


def most_expensive_locations(limit=10):
    def build():
        qs = (
            Property.objects.values("location__name")
            .annotate(avg_ppsf=Avg("price_per_sqft"), count=Count("id"))
            .filter(count__gte=MIN_LISTINGS_FOR_RANKING)
            .order_by("-avg_ppsf")[:limit]
        )
        return [{"location": row["location__name"], "price_per_sqft": round(float(row["avg_ppsf"]), 2)} for row in qs]
    return _cached(f"agg:most_expensive:{limit}", build)


def most_affordable_locations(limit=10):
    def build():
        qs = (
            Property.objects.values("location__name")
            .annotate(avg_ppsf=Avg("price_per_sqft"), count=Count("id"))
            .filter(count__gte=MIN_LISTINGS_FOR_RANKING)
            .order_by("avg_ppsf")[:limit]
        )
        return [{"location": row["location__name"], "price_per_sqft": round(float(row["avg_ppsf"]), 2)} for row in qs]
    return _cached(f"agg:most_affordable:{limit}", build)


def amenity_price_impact():
    """Mean price with vs without each amenity. Amenities are a JSON list on Property, so this
    filters in Python rather than relying on SQLite-specific JSON operators, keeping the query
    portable. Dataset size (thousands of rows) makes this cheap enough to run in Python."""
    def build():
        all_props = list(Property.objects.values_list("price_inr", "amenities"))
        results = []
        if not all_props:
            return results
        for amenity in Amenity.objects.all():
            with_amenity = [float(p) for p, ams in all_props if ams and amenity.name in ams]
            without_amenity = [float(p) for p, ams in all_props if not (ams and amenity.name in ams)]
            if len(with_amenity) < MIN_LISTINGS_FOR_RANKING or not without_amenity:
                continue
            mean_with = statistics.mean(with_amenity)
            mean_without = statistics.mean(without_amenity)
            delta_pct = round(100 * (mean_with - mean_without) / mean_without, 2) if mean_without else 0
            results.append({
                "amenity": amenity.name,
                "mean_price_with": round(mean_with, 2),
                "mean_price_without": round(mean_without, 2),
                "delta_percent": delta_pct,
            })
        results.sort(key=lambda r: r["delta_percent"], reverse=True)
        return results
    return _cached("agg:amenity_price_impact", build)


def furnishing_price_impact():
    def build():
        qs = Property.objects.values("furnishing").annotate(avg_price=Avg("price_inr"), count=Count("id"))
        rows = {row["furnishing"]: row for row in qs}
        baseline = rows.get("Unfurnished", {}).get("avg_price")
        results = []
        for furnishing, row in rows.items():
            delta_pct = round(100 * (float(row["avg_price"]) - float(baseline)) / float(baseline), 2) if baseline else 0
            results.append({
                "furnishing": furnishing,
                "average_price": round(float(row["avg_price"]), 2),
                "count": row["count"],
                "delta_percent_vs_unfurnished": delta_pct,
            })
        order = {"Unfurnished": 0, "Semi": 1, "Full": 2}
        results.sort(key=lambda r: order.get(r["furnishing"], 99))
        return results
    return _cached("agg:furnishing_price_impact", build)


def tier_price_comparison():
    def build():
        results = []
        for tier in ["Premium", "Mid", "Budget"]:
            ppsf = list(Property.objects.filter(location__tier=tier).values_list("price_per_sqft", flat=True))
            median_ppsf = float(statistics.median(ppsf)) if ppsf else 0
            results.append({"tier": tier, "median_price_per_sqft": round(median_ppsf, 2), "count": len(ppsf)})
        return results
    return _cached("agg:tier_price_comparison", build)


def headline_stats():
    def build():
        total_listings = Property.objects.count()
        locations_covered = Location.objects.count()
        prices = list(Property.objects.values_list("price_inr", flat=True))
        ppsf = list(Property.objects.values_list("price_per_sqft", flat=True))
        median_price = float(statistics.median(prices)) if prices else 0
        median_ppsf = float(statistics.median(ppsf)) if ppsf else 0
        predictions_served = PredictionLog.objects.count()
        return {
            "total_listings": total_listings,
            "locations_covered": locations_covered,
            "median_price": round(median_price, 2),
            "median_price_per_sqft": round(median_ppsf, 2),
            "predictions_served": predictions_served,
        }
    return _cached("agg:headline_stats", build)
