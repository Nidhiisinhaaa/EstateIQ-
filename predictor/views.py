import csv
import io
import json
import subprocess
import sys
import threading

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.decorators import rate_limit_post

from .forms import PredictionForm
from .methodology import CLEANING_STEP_RATIONALE, ENGINEERED_FEATURES
from .models import ModelMetric, PredictionLog, RetrainJob
from .services.engine import PredictionEngine

LOG_TAIL_MAX_CHARS = 6000
MAX_COMPARE_ITEMS = 4


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


@rate_limit_post("predict")
def predict(request):
    health = PredictionEngine.health_check()

    initial = {}
    location_param = request.GET.get("location")
    if location_param:
        initial["location"] = location_param

    if request.method == "POST":
        form = PredictionForm(request.POST)
        if not health["ok"]:
            messages.error(
                request,
                "Prediction model artifacts are not available yet. "
                "Run the ML pipeline first: python ml_pipeline/run_pipeline.py --step all",
            )
        elif form.is_valid():
            location_obj = form.cleaned_data["location"]
            payload = {
                "location": location_obj.name,
                "area_sqft": form.cleaned_data["area_sqft"],
                "bhk": form.cleaned_data["bhk"],
                "bathrooms": form.cleaned_data["bathrooms"],
                "balcony": form.cleaned_data.get("balcony") or 0,
            }
            engine = PredictionEngine()
            try:
                result = engine.predict(payload)
            except ValidationError as exc:
                form.add_error("location", str(exc))
            else:
                if not request.session.session_key:
                    request.session.create()
                amenities = [a.name for a in form.cleaned_data.get("amenities", [])]
                model_meta = engine.get_model_meta()
                log = PredictionLog.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    session_key=request.session.session_key or "",
                    location=location_obj,
                    location_name=location_obj.name,
                    area_sqft=payload["area_sqft"],
                    bhk=payload["bhk"],
                    bathrooms=payload["bathrooms"],
                    balcony=payload["balcony"],
                    floor=form.cleaned_data.get("floor"),
                    total_floors=form.cleaned_data.get("total_floors"),
                    age_years=form.cleaned_data.get("age_years") or 0,
                    parking=form.cleaned_data.get("parking", False),
                    furnishing=form.cleaned_data["furnishing"],
                    property_type=form.cleaned_data["property_type"],
                    amenities=amenities,
                    predicted_price=result.point_estimate,
                    lower_bound=result.lower_bound,
                    upper_bound=result.upper_bound,
                    confidence_score=result.confidence_score,
                    model_name=result.model_name,
                    model_version=str(model_meta.get("trained_at", "")),
                    ip_address=_client_ip(request),
                )
                return redirect("predictor:result", pk=log.pk)
    else:
        form = PredictionForm(initial=initial)

    return render(request, "predictor/predict.html", {"form": form, "artifacts_ready": health["ok"]})


def result(request, pk):
    log = get_object_or_404(PredictionLog, pk=pk)

    owns_log = (
        (log.user_id and log.user_id == getattr(request.user, "id", None))
        or (not log.user_id and log.session_key and log.session_key == request.session.session_key)
    )
    if not owns_log:
        raise Http404

    engine = PredictionEngine()
    comparables, comparable_count = [], 0
    if log.location:
        comparables, comparable_count = engine.find_comparables(log.location.name, log.area_sqft, log.bhk)

    model_r2 = None
    health = PredictionEngine.health_check()
    if health["ok"]:
        model_r2 = engine.get_model_meta().get("r2")

    return render(request, "predictor/result.html", {
        "log": log,
        "comparables": comparables,
        "comparable_count": comparable_count,
        "model_r2": model_r2,
    })


def model_report(request):
    metrics = ModelMetric.objects.all()  # default ordering: rmse ascending, i.e. best first

    cleaning_report = {}
    report_path = settings.ML_ARTIFACTS_DIR / "cleaning_report.json"
    if report_path.exists():
        with open(report_path) as f:
            cleaning_report = json.load(f)

    methodology_steps = [
        {**step, "rationale": CLEANING_STEP_RATIONALE.get(step["step"], step.get("note", ""))}
        for step in cleaning_report.get("steps", [])
    ]

    return render(request, "predictor/model_report.html", {
        "metrics": metrics,
        "cleaning_report": cleaning_report,
        "methodology_steps": methodology_steps,
        "engineered_features": ENGINEERED_FEATURES,
    })


def export_model_comparison_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="estateiq_model_comparison.csv"'
    writer = csv.writer(response)
    writer.writerow(["Model", "MAE", "RMSE", "R2", "MAPE", "CV R2 Mean", "CV R2 Std", "Train Seconds", "Is Best", "Trained At"])
    for m in ModelMetric.objects.all():
        writer.writerow([
            m.model_name, m.mae, m.rmse, m.r2, m.mape, m.cv_r2_mean, m.cv_r2_std,
            m.train_seconds, m.is_best, m.trained_at.isoformat(),
        ])
    return response


def _run_retrain_job(job_id):
    job = RetrainJob.objects.get(pk=job_id)
    job.status = "running"
    job.started_at = timezone.now()
    job.save(update_fields=["status", "started_at"])

    cmd = [sys.executable, str(settings.BASE_DIR / "ml_pipeline" / "run_pipeline.py"), "--step", "all"]
    log_chunks = []
    success = False
    try:
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=str(settings.BASE_DIR),
        )
        for line in process.stdout:
            log_chunks.append(line)
            RetrainJob.objects.filter(pk=job_id).update(log_tail="".join(log_chunks)[-LOG_TAIL_MAX_CHARS:])
        process.wait()
        success = process.returncode == 0
    except Exception as exc:
        log_chunks.append(f"\nERROR: {exc}\n")

    job.refresh_from_db()
    job.status = "success" if success else "failed"
    job.finished_at = timezone.now()
    job.log_tail = "".join(log_chunks)[-LOG_TAIL_MAX_CHARS:]
    job.save(update_fields=["status", "finished_at", "log_tail"])

    if success:
        try:
            call_command("sync_model_metrics")
        except Exception as exc:
            RetrainJob.objects.filter(pk=job_id).update(
                log_tail=(job.log_tail + f"\nsync_model_metrics failed: {exc}\n")[-LOG_TAIL_MAX_CHARS:]
            )
        PredictionEngine.reset()


@staff_member_required
def retrain(request):
    if request.method == "POST":
        already_running = RetrainJob.objects.filter(status__in=["queued", "running"]).exists()
        if already_running:
            messages.warning(request, "A retrain job is already running.")
        else:
            job = RetrainJob.objects.create(status="queued", triggered_by=request.user)
            thread = threading.Thread(target=_run_retrain_job, args=(job.id,), daemon=True)
            thread.start()
        return redirect("predictor:retrain")

    latest_job = RetrainJob.objects.first()
    return render(request, "predictor/retrain.html", {"job": latest_job})


@staff_member_required
def retrain_status(request, pk):
    job = get_object_or_404(RetrainJob, pk=pk)
    return JsonResponse({
        "status": job.status,
        "log_tail": job.log_tail,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    })


@login_required
def history(request):
    qs = PredictionLog.objects.filter(user=request.user)

    location_filter = request.GET.get("location") or ""
    date_from = request.GET.get("date_from") or ""
    date_to = request.GET.get("date_to") or ""

    if location_filter:
        qs = qs.filter(location_name=location_filter)
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)

    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get("page"))

    locations = (
        PredictionLog.objects.filter(user=request.user)
        .order_by("location_name")
        .values_list("location_name", flat=True)
        .distinct()
    )

    return render(request, "account/history.html", {
        "page": page,
        "locations": locations,
        "location_filter": location_filter,
        "date_from": date_from,
        "date_to": date_to,
        "max_compare_items": MAX_COMPARE_ITEMS,
    })


@login_required
@require_POST
def history_delete(request, pk):
    log = get_object_or_404(PredictionLog, pk=pk, user=request.user)
    log.delete()
    messages.success(request, "Prediction deleted.")
    return redirect("account:history")


@login_required
def history_clear(request):
    if request.method == "POST":
        deleted, _ = PredictionLog.objects.filter(user=request.user).delete()
        messages.success(request, f"Cleared {deleted} predictions from your history.")
        return redirect("account:history")
    return render(request, "account/history_clear_confirm.html")


@login_required
def compare(request):
    ids = request.GET.getlist("id")[:MAX_COMPARE_ITEMS]
    logs = list(PredictionLog.objects.filter(user=request.user, pk__in=ids))
    logs.sort(key=lambda log: ids.index(str(log.pk)))
    return render(request, "account/compare.html", {"logs": logs})


@login_required
def export_history_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="estateiq_prediction_history.csv"'
    writer = csv.writer(response)
    writer.writerow([
        "Date", "Location", "BHK", "Area Sqft", "Bathrooms", "Predicted Price",
        "Lower Bound", "Upper Bound", "Confidence", "Model",
    ])
    for log in PredictionLog.objects.filter(user=request.user):
        writer.writerow([
            log.created_at.isoformat(), log.location_name, log.bhk, log.area_sqft, log.bathrooms,
            log.predicted_price, log.lower_bound, log.upper_bound, log.confidence_score, log.model_name,
        ])
    return response


@login_required
def export_prediction_pdf(request, pk):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    log = get_object_or_404(PredictionLog, pk=pk, user=request.user)

    engine = PredictionEngine()
    comparables = []
    if log.location:
        comparables, _ = engine.find_comparables(log.location.name, log.area_sqft, log.bhk)

    navy = colors.HexColor("#0B1420")
    accent = colors.HexColor("#2A5F8C")
    paleAccent = colors.HexColor("#E6EEF7")

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("EstateIQTitle", parent=styles["Title"], textColor=navy)
    heading_style = ParagraphStyle("EstateIQHeading", parent=styles["Heading2"], textColor=navy, spaceBefore=6)
    body_style = ParagraphStyle("EstateIQBody", parent=styles["Normal"], textColor=navy)

    table_style = TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, accent),
        ("BACKGROUND", (0, 0), (0, -1), paleAccent),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (-1, -1), navy),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ])

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20 * mm, bottomMargin=20 * mm)

    elements = [
        Paragraph("EstateIQ -- Prediction Report", title_style),
        Paragraph(f"{log.location_name} -- {log.bhk} BHK, {log.area_sqft:.0f} sqft", body_style),
        Spacer(1, 8 * mm),
        Paragraph("Inputs", heading_style),
        Table([
            ["Location", log.location_name],
            ["Area (sqft)", f"{log.area_sqft:.0f}"],
            ["BHK", str(log.bhk)],
            ["Bathrooms", str(log.bathrooms)],
            ["Balcony", str(log.balcony)],
            ["Floor / Total Floors", f"{log.floor or '-'} / {log.total_floors or '-'}"],
            ["Age (years)", str(log.age_years)],
            ["Parking", "Yes" if log.parking else "No"],
            ["Furnishing", log.furnishing],
            ["Property Type", log.property_type],
            ["Amenities", ", ".join(log.amenities) or "None"],
        ], colWidths=[50 * mm, 100 * mm]),
        Spacer(1, 6 * mm),
        Paragraph("Estimate", heading_style),
        Table([
            ["Predicted Price", f"Rs {log.predicted_price:,.0f}"],
            ["Lower Bound", f"Rs {log.lower_bound:,.0f}"],
            ["Upper Bound", f"Rs {log.upper_bound:,.0f}"],
            ["Confidence Score", f"{log.confidence_score}"],
            ["Model", log.model_name],
            ["Generated", log.created_at.strftime("%Y-%m-%d %H:%M")],
        ], colWidths=[50 * mm, 100 * mm]),
    ]
    for el in elements:
        if isinstance(el, Table):
            el.setStyle(table_style)

    if comparables:
        elements.append(Spacer(1, 6 * mm))
        elements.append(Paragraph("Comparable Properties", heading_style))
        comp_rows = [["Location", "BHK", "Area", "Price", "Price/Sqft"]]
        for c in comparables:
            comp_rows.append([
                c.location.name, str(c.bhk), f"{c.area_sqft:.0f}",
                f"Rs {c.price_inr:,.0f}", f"Rs {c.price_per_sqft:,.0f}",
            ])
        comp_table = Table(comp_rows, colWidths=[45 * mm, 15 * mm, 20 * mm, 35 * mm, 35 * mm])
        comp_table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, accent),
            ("BACKGROUND", (0, 0), (-1, 0), paleAccent),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("TEXTCOLOR", (0, 0), (-1, -1), navy),
        ]))
        elements.append(comp_table)

    doc.build(elements)
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="estateiq-prediction-{log.pk}.pdf"'
    return response
