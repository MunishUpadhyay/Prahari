from rest_framework import serializers
from .models import Incident


class IncidentListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for the list endpoint."""
    signal_raw_text = serializers.CharField(source="signal.raw_text", read_only=True)

    class Meta:
        model = Incident
        fields = [
            "id",
            "signal",
            "signal_raw_text",
            "severity_score",
            "severity_label",
            "domain",
            "situation_brief",
            "is_resolved",
            "coordinator_status",
            "coordinator_notes",
            "status_updated_at",
            "created_at",
            "updated_at",
        ]


class IncidentDetailSerializer(serializers.ModelSerializer):
    """Full serializer including agent_outputs for the detail endpoint."""

    class Meta:
        model = Incident
        fields = [
            "id",
            "signal",
            "severity_score",
            "severity_label",
            "domain",
            "agent_outputs",
            "situation_brief",
            "recommended_resources",
            "is_resolved",
            "resolved_at",
            "coordinator_status",
            "coordinator_notes",
            "status_updated_at",
            "created_at",
            "updated_at",
        ]
