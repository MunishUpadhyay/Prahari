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
        from apps.tenants.utils import get_authorized_tenant
        tenant = get_authorized_tenant(self.request)
        return Incident.objects.filter(signal__tenant=tenant).select_related("signal")


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
        from apps.tenants.utils import get_authorized_tenant
        tenant = get_authorized_tenant(self.request)
        return Incident.objects.filter(signal__tenant=tenant).select_related("signal")

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
            
            if new_status == 'resolved':
                from apps.audit.models import AuditLog
                AuditLog.log_event(
                    incident=instance,
                    action='incident_resolved',
                    performed_by=self.request.user.username if (self.request.user and self.request.user.is_authenticated) else "unknown"
                )
        elif notes_changed:
            serializer.save(status_updated_at=timezone.now())
        else:
            serializer.save()


from drf_spectacular.utils import extend_schema

@extend_schema(request=None, responses={200: None})
class SimilarIncidentsView(APIView):
    """
    GET /api/incidents/<uuid:id>/similar/
    Returns the top similar past incidents and their outcome statistics.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        from apps.tenants.utils import get_authorized_tenant
        tenant = get_authorized_tenant(request)
        incident = get_object_or_404(Incident.objects.filter(signal__tenant=tenant).select_related("signal"), id=id)
        query_text = incident.situation_brief or ""
        if not query_text:
            query_text = incident.signal.raw_text

        from rag.retriever import retrieve_similar_incidents
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



from rest_framework.permissions import AllowAny
from apps.agents.agents import LegalNoticeAgent

@extend_schema(request=None, responses={200: None})
class LegalNoticeView(APIView):
    """
    GET /api/incidents/<id>/legal-notice/
    Generates a formal legal notice draft for the incident. Supports UUIDs and PRAH tracking IDs.
    """
    permission_classes = [AllowAny]

    def get(self, request, id):
        incident = None
        try:
            import uuid
            uuid_obj = uuid.UUID(str(id))
            incident = Incident.objects.filter(id=uuid_obj).select_related("signal").first()
        except (ValueError, TypeError):
            pass

        if not incident:
            from apps.signals.citizen_views import resolve_signal
            try:
                sig = resolve_signal(id)
                incident = getattr(sig, "incident", None)
            except Exception:
                incident = None

        if not incident:
            return Response(
                {"detail": "Incident not found", "message": "Incident not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        if request.user.is_authenticated and not request.user.is_staff:
            from apps.tenants.utils import get_authorized_tenant
            tenant = get_authorized_tenant(request)
            if tenant and incident.signal and incident.signal.tenant_id != tenant.id:
                return Response(
                    {"detail": "Unauthorized access to incident", "message": "Unauthorized access to incident"},
                    status=status.HTTP_403_FORBIDDEN
                )

        signal = incident.signal or getattr(incident, 'signal', None)
        agent_outputs = incident.agent_outputs or {}
        rights_result = agent_outputs.get("rights") or agent_outputs.get("legal") or agent_outputs.get("sentinel")
        
        if not isinstance(rights_result, dict):
            rights_result = {
                "rights_violated": [incident.title or "Right to peaceful possession and legal protection"],
                "legal_provisions": [
                    {
                        "provision": "Applicable Statutory Laws & Civil Rights",
                        "description": "Protection against illegal eviction, unlawful intimidation, or denial of legal process.",
                        "relevance": "Directly applicable to reported incident."
                    }
                ],
                "immediate_actions": ["Issue formal statutory legal notice", "Preserve all records and evidence"],
                "authority_to_contact": "Police Station / Civil Court / NALSA Helpline (15100)"
            }

        lang = (request.query_params.get("lang") or (signal.preferred_language if signal else "english") or "english").lower()
        
        try:
            notice_text = LegalNoticeAgent().run(signal, rights_result, target_language=lang)
        except Exception as exc:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("[LegalNoticeView] Agent execution failed, using fallback template generator: %s", exc)
            
            raw_text = signal.raw_text if signal else (incident.summary or "Incident details reported")
            tracking_code = getattr(signal, "tracking_id", None) or str(id)
            
            if "hi" in lang or "hindi" in lang:
                notice_text = (
                    f"कानूनी नोटिस प्रारूप (LEGAL NOTICE DRAFT)\n"
                    f"दिनांक: {incident.created_at.strftime('%d/%m/%Y') if incident.created_at else 'आज'}\n"
                    f"संदर्भ रिपोर्ट आईडी: {tracking_code}\n\n"
                    f"प्रतिकूल पक्ष / उत्तरदाता के नाम:\n\n"
                    f"विषय: अवैध कार्रवाई एवं उत्पीड़न के संबंध में औपचारिक वैधानिक सूचना\n\n"
                    f"1. घटना का विवरण:\n"
                    f"पीड़ित पक्ष द्वारा दर्ज शिकायत के अनुसार: {raw_text}\n\n"
                    f"2. कानूनी अधिकार एवं प्रावधान:\n"
                    f"भारतीय न्याय संहिता (BNS) तथा प्रासंगिक सिविल कानूनों के तहत शिकायतकर्ता को शांतिपूर्ण अधिकार एवं न्याय सुरक्षा का पूर्ण अधिकार प्राप्त है।\n\n"
                    f"3. वैधानिक मांगें:\n"
                    f"आपको इस नोटिस के माध्यम से निर्देश दिया जाता है कि आप तुरंत किसी भी अवैध हस्तक्षेप, जबरन बेदखली या धमकी को रोकें।\n\n"
                    f"4. समय सीमा:\n"
                    f"इस सूचना की प्राप्ति के 7 दिनों के भीतर अनुपालन न करने पर सक्षम न्यायालय के समक्ष आवश्यक दीवानी एवं आपराधिक कार्यवाही शुरू की जाएगी।\n\n"
                    f"(निःशुल्क औपचारिक कानूनी सहायता एवं प्रतिनिधित्व के लिए NALSA हेल्पलाइन 15100 पर संपर्क करें)"
                )
            else:
                notice_text = (
                    f"FORMAL LEGAL NOTICE DRAFT\n"
                    f"Date: {incident.created_at.strftime('%Y-%m-%d') if incident.created_at else 'Current Date'}\n"
                    f"Report Reference ID: {tracking_code}\n\n"
                    f"TO: OPPOSITE PARTY / RESPONDENT\n"
                    f"FROM: AGGRIEVED PARTY (via ResQGrid Prahari Civic Assistance)\n\n"
                    f"SUBJECT: STATUTORY DEMAND NOTICE REGARDING UNLAWFUL ACTS / DISPUTE\n\n"
                    f"1. STATEMENT OF FACTS:\n"
                    f"Notice is hereby issued regarding the incident reported under Tracking ID {tracking_code}: {raw_text}\n\n"
                    f"2. STATUTORY RIGHTS & LEGAL GROUNDS:\n"
                    f"The acts complained of violate fundamental legal protections and relevant statutory provisions prohibiting intimidation, forcible interference, or illegal eviction.\n\n"
                    f"3. DEMANDS:\n"
                    f"You are hereby called upon to immediately cease and desist from all unlawful actions, threats, or unauthorized interference.\n\n"
                    f"4. COMPLIANCE TIMELINE:\n"
                    f"Take notice that failure to comply within seven (7) days of receipt will result in appropriate legal proceedings before the competent Court of Law at your sole risk and consequence.\n\n"
                    f"(For free formal representation and legal aid, dial the NALSA Helpline 15100)"
                )

        import re
        def clean_markdown_legal_notice(text: str) -> str:
            if not text:
                return text
            cleaned = re.sub(r'^[ \t]*#+[ \t]*', '', text, flags=re.MULTILINE)
            cleaned = re.sub(r'\*\*([^*]+)\*\*', r'\1', cleaned)
            cleaned = re.sub(r'\*([^*]+)\*', r'\1', cleaned)
            cleaned = re.sub(r'^[ \t]*\*[ \t]+', '• ', cleaned, flags=re.MULTILINE)
            return cleaned.replace('**', '').replace('###', '').replace('##', '').strip()

        notice_text = clean_markdown_legal_notice(notice_text)

        return Response({
            "notice": notice_text,
            "notice_en": notice_text,
            "notice_hi": notice_text
        }, status=status.HTTP_200_OK)


