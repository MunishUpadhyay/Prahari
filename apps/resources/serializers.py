from rest_framework import serializers
from .models import Resource


class ResourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resource
        fields = [
            "id",
            "tenant",
            "name",
            "resource_type",
            "location",
            "is_available",
            "contact_info",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class NearbyResourceSerializer(ResourceSerializer):
    """
    Extends ResourceSerializer with a computed `distance_m` field
    populated by the annotated queryset in NearbyResourcesView.
    """

    distance_m = serializers.FloatField(read_only=True, required=False)

    class Meta(ResourceSerializer.Meta):
        fields = ResourceSerializer.Meta.fields + ["distance_m"]
