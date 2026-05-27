from django.urls import path
from .views import IncidentListView, IncidentDetailView, SimilarIncidentsView, LegalNoticeView

app_name = "incidents"

urlpatterns = [
    path("", IncidentListView.as_view(), name="list"),
    path("<uuid:id>/", IncidentDetailView.as_view(), name="detail"),
    path("<uuid:id>/similar/", SimilarIncidentsView.as_view(), name="similar"),
    path("<uuid:id>/legal-notice/", LegalNoticeView.as_view(), name="legal-notice"),
]

