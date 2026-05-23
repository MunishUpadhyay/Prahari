"""
Signal serializers.
"""
from rest_framework import serializers
from .models import Signal


class SignalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Signal
        fields = [
            "id",
            "tenant",
            "raw_text",
            "image",
            "source_type",
            "location",
            "domain",
            "status",
            "metadata",
            "created_at",
        ]
        read_only_fields = ["id", "domain", "status", "created_at"]


class SignalIngestSerializer(serializers.ModelSerializer):
    """
    Serializer used for the POST /api/signals/ ingest endpoint.
    Tenant is injected from the authenticated JWT claim, not from the request body.
    """

    class Meta:
        model = Signal
        fields = [
            "id",
            "raw_text",
            "image",
            "source_type",
            "location",
            "status",
            "domain",
            "metadata",
            "created_at",
        ]
        read_only_fields = ["id", "status", "domain", "created_at"]

