"""
Incident API views.

GET /api/incidents/       — Paginated list of incidents for the requesting tenant.
GET /api/incidents/<id>/  — Full incident detail including agent outputs.

Tenant filtering:
    Queries are scoped to the tenant associated with the JWT token.
    The FK join goes: JWT → tenant_id → Signal → Incident.
"""

import logging

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, RetrieveUpdateAPIView
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rag.retriever import retrieve_similar_incidents

from .models import Incident
from .serializers import IncidentDetailSerializer, IncidentListSerializer

logger = logging.getLogger(__name__)


class IncidentListView(ListAPIView):
    """
    GET /api/incidents/

    Returns a paginated list of incidents belonging to the requesting tenant,
    ordered by creation date (newest first).
    """

    permission_classes = [IsAuthenticated]
    serializer_class = IncidentListSerializer

    def get_queryset(self):
        # TODO: filter by tenant once JWT claim wiring is in place
        # tenant_id = self.request.auth.get("tenant_id")
        # return Incident.objects.filter(signal__tenant_id=tenant_id).select_related("signal")
        logger.warning("Tenant filtering not yet wired — returning all incidents.")
        return Incident.objects.select_related("signal").all()


class IncidentDetailView(RetrieveUpdateAPIView):
    """
    GET /api/incidents/<id>/
    PATCH /api/incidents/<id>/

    Returns the full incident record and allows updates.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = IncidentDetailSerializer
    lookup_field = "id"

    def get_queryset(self):
        return Incident.objects.select_related("signal").all()

    def perform_update(self, serializer):
        instance = serializer.instance
        status_changed = ('coordinator_status' in self.request.data and self.request.data['coordinator_status'] != instance.coordinator_status)
        notes_changed = ('coordinator_notes' in self.request.data and self.request.data['coordinator_notes'] != instance.coordinator_notes)
        
        if status_changed:
            new_status = self.request.data['coordinator_status']
            extra = {'status_updated_at': timezone.now()}
            if new_status == 'resolved':
                extra['is_resolved'] = True
                extra['resolved_at'] = timezone.now()
            else:
                extra['is_resolved'] = False
                extra['resolved_at'] = None
            serializer.save(**extra)
        elif notes_changed:
            serializer.save(status_updated_at=timezone.now())
        else:
            serializer.save()


class SimilarIncidentsView(APIView):
    """
    GET /api/incidents/<uuid:id>/similar/
    Returns the top similar past incidents and their outcome statistics.
    """
    permission_classes = [AllowAny]

    def get(self, request, id):
        incident = get_object_or_404(Incident.objects.select_related("signal"), id=id)
        query_text = incident.situation_brief or ""
        if not query_text:
            query_text = incident.signal.raw_text

        results = retrieve_similar_incidents(
            query=query_text,
            n_results=5,
            exclude_id=str(id)
        )
        
        # Look up similar Incident details from Postgres DB to retrieve Hindi situation brief
        incident_ids = [r["incident_id"] for r in results if r.get("incident_id")]
        incidents_by_id = {}
        if incident_ids:
            try:
                db_incidents = Incident.objects.filter(id__in=incident_ids)
                for db_inc in db_incidents:
                    incidents_by_id[str(db_inc.id)] = db_inc
            except Exception:
                pass

        for r in results:
            inc_id = r.get("incident_id")
            db_inc = incidents_by_id.get(str(inc_id))
            if db_inc:
                outputs = db_inc.agent_outputs or {}
                lang_data = outputs.get("language") or {}
                pref_lang = lang_data.get("preferred", "hindi")
                lang_out = lang_data.get(pref_lang, {}) or lang_data.get("hindi", {})
                r["situation_brief_hi"] = lang_out.get("situation_brief") or db_inc.situation_brief or ""
            else:
                r["situation_brief_hi"] = ""
        
        total_similar = len(results)
        if total_similar < 2:
            outcome_stats = None
        else:
            resolved_count = 0
            for item in results:
                meta = item.get('metadata', item)
                if not isinstance(meta, dict):
                    meta = item
                resolved_val = meta.get('resolved')
                if resolved_val is True or resolved_val == 'true' or resolved_val == 'True':
                    resolved_count += 1
            
            resolution_rate = f"{round(resolved_count / total_similar * 100)}%"
            
            severities = []
            for item in results:
                meta = item.get('metadata', item)
                if not isinstance(meta, dict):
                    meta = item
                severities.append(meta.get('severity') or 'medium')
            avg_severity = max(set(severities), key=severities.count) if severities else 'medium'
            
            authorities = []
            domains = []
            for item in results:
                meta = item.get('metadata', item)
                if not isinstance(meta, dict):
                    meta = item
                
                auth = meta.get('authority_to_contact')
                if auth:
                    authorities.append(auth)
                
                dom = meta.get('domain')
                if dom:
                    domains.append(dom)
            
            if authorities:
                typical_resolution = max(set(authorities), key=authorities.count)
            elif domains:
                typical_resolution = max(set(domains), key=domains.count)
            else:
                typical_resolution = 'unknown'
                
            outcome_stats = {
                "total_similar": total_similar,
                "resolved_count": resolved_count,
                "resolution_rate": resolution_rate,
                "avg_severity": avg_severity,
                "typical_resolution": typical_resolution
            }

        return Response({
            "similar_incidents": results,
            "outcome_stats": outcome_stats
        }, status=status.HTTP_200_OK)



from apps.agents.agents import LegalNoticeAgent

class LegalNoticeView(APIView):
    """
    GET /api/incidents/<uuid:id>/legal-notice/
    Generates a formal legal notice draft for the incident.
    """
    permission_classes = [AllowAny]

    def get(self, request, id):
        incident = get_object_or_404(Incident.objects.select_related("signal"), id=id)
        signal = incident.signal
        
        # Check domain
        domain = (incident.domain or "").lower()
        if domain not in ["legal", "cross", "cross_domain"]:
            return Response(
                {"detail": "Legal notice only available for legal domain incidents", "message": "Legal notice only available for legal domain incidents"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        agent_outputs = incident.agent_outputs or {}
        rights_result = agent_outputs.get("rights")
        if not rights_result:
            return Response(
                {"detail": "Rights assessment not yet complete", "message": "Rights assessment not yet complete"},
                status=status.HTTP_400_BAD_REQUEST
            )

        lang = request.query_params.get("lang") or signal.preferred_language or "english"
        notice_text = LegalNoticeAgent().run(signal, rights_result, target_language=lang)
        return Response({"notice": notice_text}, status=status.HTTP_200_OK)

