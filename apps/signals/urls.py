from django.urls import path
from .views import SignalIngestView

app_name = "signals"

urlpatterns = [
    path("", SignalIngestView.as_view(), name="ingest"),
]
