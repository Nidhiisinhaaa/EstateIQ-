from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from predictor import views as predictor_views

from . import views

app_name = "account"

urlpatterns = [
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(template_name="registration/logged_out.html"), name="logout"),
    path("signup/", views.signup, name="signup"),
    path(
        "password-change/",
        auth_views.PasswordChangeView.as_view(
            template_name="registration/password_change.html",
            success_url=reverse_lazy("account:password_change_done"),
        ),
        name="password_change",
    ),
    path(
        "password-change/done/",
        auth_views.PasswordChangeDoneView.as_view(template_name="registration/password_change_done.html"),
        name="password_change_done",
    ),

    path("history/", predictor_views.history, name="history"),
    path("history/<int:pk>/delete/", predictor_views.history_delete, name="history_delete"),
    path("history/clear/", predictor_views.history_clear, name="history_clear"),
    path("history/compare/", predictor_views.compare, name="compare"),
    path("history/<int:pk>/export/pdf/", predictor_views.export_prediction_pdf, name="export_prediction_pdf"),
    path("history/export/csv/", predictor_views.export_history_csv, name="export_history_csv"),
]
