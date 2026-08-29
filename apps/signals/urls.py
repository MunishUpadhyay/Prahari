from django.urls import path
from .views import SignalIngestView, SignalVerifyCodeView, SignalCloseSessionView

app_name = "signals"

urlpatterns = [
    path("", SignalIngestView.as_view(), name="ingest"),
    path("<str:signal_id>/verify-code/", SignalVerifyCodeView.as_view(), name="verify_code"),
    path("<str:signal_id>/close-session/", SignalCloseSessionView.as_view(), name="close_session"),
]
