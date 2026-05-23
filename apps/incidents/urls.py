from django.urls import path
from .views import IncidentListView, IncidentDetailView

app_name = "incidents"

urlpatterns = [
    path("", IncidentListView.as_view(), name="list"),
    path("<uuid:id>/", IncidentDetailView.as_view(), name="detail"),
]
