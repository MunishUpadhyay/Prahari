"""
Resources API views.

GET /api/resources/nearby/ — Geospatial resource lookup within a radius.

Query parameters:
    lat  (float)  — WGS84 latitude
    lon  (float)  — WGS84 longitude
    radius_m (int) — Search radius in metres (default: 5000)
    type   (str)  — Optional resource_type filter

The queryset is annotated with `distance_m` for ordering and display.
"""

import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Resource
from .serializers import NearbyResourceSerializer

logger = logging.getLogger(__name__)


class NearbyResourcesView(APIView):
    """
    GET /api/resources/nearby/?lat=<lat>&lon=<lon>&radius_m=<m>&type=<type>

    Returns available resources within `radius_m` metres of the given point,
    sorted by distance ascending.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        lat = request.query_params.get("lat")
        lon = request.query_params.get("lon")
        radius_m = int(request.query_params.get("radius_m", 5000))
        resource_type = request.query_params.get("type")

        if not lat or not lon:
            return Response(
                {"detail": "Query parameters `lat` and `lon` are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            lat, lon = float(lat), float(lon)
        except ValueError:
            return Response(
                {"detail": "`lat` and `lon` must be numeric."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # TODO: implement PostGIS Distance annotation
        # from django.contrib.gis.geos import Point
        # from django.contrib.gis.db.models.functions import Distance
        # ref_point = Point(lon, lat, srid=4326)
        # qs = (
        #     Resource.objects
        #     .filter(is_available=True, location__distance_lte=(ref_point, D(m=radius_m)))
        #     .annotate(distance_m=Distance("location", ref_point))
        #     .order_by("distance_m")
        # )
        # if resource_type:
        #     qs = qs.filter(resource_type=resource_type)

        logger.info("Nearby resources endpoint hit — PostGIS query not yet wired.")
        return Response(
            {"detail": "Geospatial query scaffold — PostGIS wiring pending."},
            status=status.HTTP_501_NOT_IMPLEMENTED,
        )
