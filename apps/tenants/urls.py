from django.urls import path
from .views import WebhookRegisterView

app_name = "tenants"

urlpatterns = [
    path("register/", WebhookRegisterView.as_view(), name="webhook_register"),
]
