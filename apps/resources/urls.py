from django.urls import path
from .views import NearbyResourcesView

app_name = "resources"

urlpatterns = [
    path("nearby/", NearbyResourcesView.as_view(), name="nearby"),
]
