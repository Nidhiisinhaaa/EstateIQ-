import statistics

from django.core.cache import cache
from django.db.models import Avg
from django.http import JsonResponse
from django.shortcuts import render

from core.templatetags.currency_tags import inr_short
from properties.models import Location, Property

from .services import aggregates

GEOJSON_CACHE_KEY = "analytics:geojson_locations"
GEOJSON_CACHE_TTL_SECONDS = 60 * 15

CHART_BUILDERS = {
    "average-price-by-location": lambda: aggregates.average_price_by_location(15),
    "price-per-sqft-by-location": lambda: aggregates.price_per_sqft_by_location(15),
    "bhk-price-distribution": aggregates.bhk_price_distribution,
    "property-type-distribution": aggregates.property_type_distribution,
    "price-trend": aggregates.price_trend_by_month,
    "most-expensive-locations": lambda: aggregates.most_expensive_locations(10),
    "most-affordable-locations": lambda: aggregates.most_affordable_locations(10),
    "amenity-price-impact": aggregates.amenity_price_impact,
    "furnishing-price-impact": aggregates.furnishing_price_impact,
    "tier-price-comparison": aggregates.tier_price_comparison,
}

CHART_CARDS = [
    {"slug": "average-price-by-location", "title": "Average Price by Location", "type": "bar"},
    {"slug": "price-per-sqft-by-location", "title": "Price per Sqft by Location", "type": "bar"},
    {"slug": "bhk-price-distribution", "title": "BHK Price Distribution", "type": "bar"},
    {"slug": "property-type-distribution", "title": "Property Type Mix", "type": "doughnut"},
    {"slug": "price-trend", "title": "Price Trend by Month", "type": "line"},
    {"slug": "most-expensive-locations", "title": "Most Expensive Locations", "type": "bar"},
    {"slug": "most-affordable-locations", "title": "Most Affordable Locations", "type": "bar"},
    {"slug": "amenity-price-impact", "title": "Amenity Price Impact", "type": "bar"},
    {"slug": "furnishing-price-impact", "title": "Furnishing Price Impact", "type": "bar"},
    {"slug": "tier-price-comparison", "title": "Price per Sqft by Tier", "type": "bar"},
]


def _build_insights():
    insights = {}

    avg_by_loc = aggregates.average_price_by_location(1)
    if avg_by_loc:
        top = avg_by_loc[0]
        insights["average-price-by-location"] = (
            f"{top['location']} has the highest average price at {inr_short(top['average_price'])}."
        )

    ppsf_by_loc = aggregates.price_per_sqft_by_location(1)
    if ppsf_by_loc:
        top = ppsf_by_loc[0]
        insights["price-per-sqft-by-location"] = (
            f"{top['location']} commands the highest price per sqft at Rs {top['price_per_sqft']:,.0f}."
        )

    bhk_dist = aggregates.bhk_price_distribution()
    if bhk_dist:
        busiest = max(bhk_dist, key=lambda r: r["count"])
        insights["bhk-price-distribution"] = (
            f"{busiest['bhk']} BHK is the most listed configuration, averaging {inr_short(busiest['average_price'])}."
        )

    type_dist = aggregates.property_type_distribution()
    if type_dist:
        top = type_dist[0]
        insights["property-type-distribution"] = f"{top['property_type']} makes up {top['share']}% of all listings."

    insights["price-trend"] = "Average listing price and prediction activity tracked by month."

    expensive = aggregates.most_expensive_locations(1)
    if expensive:
        insights["most-expensive-locations"] = (
            f"{expensive[0]['location']} is the most expensive location by price per sqft."
        )

    affordable = aggregates.most_affordable_locations(1)
    if affordable:
        insights["most-affordable-locations"] = (
            f"{affordable[0]['location']} is the most affordable location by price per sqft."
        )

    amenity_impact = aggregates.amenity_price_impact()
    if amenity_impact:
        top = amenity_impact[0]
        insights["amenity-price-impact"] = (
            f"{top['amenity']} listings command a {top['delta_percent']:+.1f}% price difference over those without it."
        )

    furnishing_impact = aggregates.furnishing_price_impact()
    full = next((r for r in furnishing_impact if r["furnishing"] == "Full"), None)
    if full:
        insights["furnishing-price-impact"] = (
            f"Fully furnished homes cost {full['delta_percent_vs_unfurnished']:+.1f}% "
            f"versus unfurnished ones on average."
        )

    tiers = {row["tier"]: row["median_price_per_sqft"] for row in aggregates.tier_price_comparison()}
    if tiers.get("Budget"):
        ratio = round(tiers.get("Premium", 0) / tiers["Budget"], 1)
        insights["tier-price-comparison"] = (
            f"Premium tier areas command {ratio}x the median price per sqft of Budget tier."
        )

    return insights


def dashboard(request):
    stats = aggregates.headline_stats()
    insights = _build_insights()
    cards = [{**card, "insight": insights.get(card["slug"], "")} for card in CHART_CARDS]
    return render(request, "analytics/dashboard.html", {"stats": stats, "cards": cards})


def chart_api(request, slug):
    builder = CHART_BUILDERS.get(slug)
    if builder is None:
        return JsonResponse({"error": "unknown chart"}, status=404)
    return JsonResponse({"data": builder()})


def _build_geojson():
    locations = list(Location.objects.exclude(latitude__isnull=True, longitude__isnull=True))
    ppsf_values = [float(loc.median_price_per_sqft) for loc in locations if loc.median_price_per_sqft]
    min_ppsf = min(ppsf_values) if ppsf_values else 0
    max_ppsf = max(ppsf_values) if ppsf_values else 1

    sorted_ppsf = sorted(ppsf_values, reverse=True)
    top_decile_cut = max(0, int(len(sorted_ppsf) * 0.1) - 1)
    top_decile_threshold = sorted_ppsf[top_decile_cut] if sorted_ppsf else 0

    features = []
    for loc in locations:
        ppsf = float(loc.median_price_per_sqft or 0)
        intensity = (ppsf - min_ppsf) / (max_ppsf - min_ppsf) if max_ppsf > min_ppsf else 0.0

        prices = list(Property.objects.filter(location=loc).values_list("price_inr", flat=True))
        median_price = float(statistics.median(prices)) if prices else 0.0

        bhk_rows = (
            Property.objects.filter(location=loc)
            .values("bhk")
            .annotate(avg_price=Avg("price_inr"))
            .order_by("bhk")
        )
        bhk_breakdown = [{"bhk": r["bhk"], "average_price": round(float(r["avg_price"]), 2)} for r in bhk_rows]

        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [loc.longitude, loc.latitude]},
            "properties": {
                "name": loc.name,
                "slug": loc.slug,
                "tier": loc.tier,
                "listing_count": loc.listing_count,
                "median_price_per_sqft": ppsf,
                "median_price": round(median_price, 2),
                "intensity": round(intensity, 3),
                "is_top_decile": bool(ppsf > 0 and ppsf >= top_decile_threshold),
                "is_approximate": loc.is_approximate,
                "bhk_breakdown": bhk_breakdown,
            },
        })

    return {"type": "FeatureCollection", "features": features}


def geojson_locations(request):
    data = cache.get(GEOJSON_CACHE_KEY)
    if data is None:
        data = _build_geojson()
        cache.set(GEOJSON_CACHE_KEY, data, GEOJSON_CACHE_TTL_SECONDS)
    return JsonResponse(data)


def map_view(request):
    return render(request, "analytics/map.html")
