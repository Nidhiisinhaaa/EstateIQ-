from django.contrib.auth import login as auth_login
from django.shortcuts import redirect, render

from .forms import SignupForm


def home(request):
    """Landing page: hero, CTAs, and headline stat cards backed by the database."""
    from predictor.models import ModelMetric, PredictionLog
    from properties.models import Location, Property

    total_listings = Property.objects.count()
    locations_covered = Location.objects.count()
    best_model = ModelMetric.objects.filter(is_best=True).first()
    predictions_served = PredictionLog.objects.count()

    stats = [
        {"label": "Listings Analysed", "value": f"{total_listings:,}", "sub": "dataset rows processed", "trend": "flat"},
        {"label": "Locations Covered", "value": f"{locations_covered:,}", "sub": "unique localities", "trend": "flat"},
        {
            "label": "Model Accuracy",
            "value": f"{best_model.r2:.3f}" if best_model else "--",
            "sub": f"R-squared, {best_model.model_name}" if best_model else "run the ML pipeline",
            "trend": "up" if best_model else "flat",
        },
        {"label": "Predictions Served", "value": f"{predictions_served:,}", "sub": "all time", "trend": "up" if predictions_served else "flat"},
    ]
    return render(request, "core/home.html", {"stats": stats})


def signup(request):
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            return redirect("home")
    else:
        form = SignupForm()
    return render(request, "registration/signup.html", {"form": form})
