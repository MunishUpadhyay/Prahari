import logging
import hashlib
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from apps.signals.models import Signal
from apps.signals.citizen_views import resolve_signal

logger = logging.getLogger(__name__)

@login_required(login_url="/citizen/login/")
def citizen_profile(request):
    """
    GET /profile/ - Renders citizen profile dashboard.
    """
    if request.user.is_staff:
        return redirect("/coordinator/dashboard/")

    # Fetch signals owned by the logged-in citizen
    owned_signals = Signal.objects.filter(user=request.user).order_by("-created_at")
    
    reports_list = []
    for sig in owned_signals:
        date_str = sig.created_at.strftime("%Y%m%d")
        uuid_first_4 = str(sig.id)[:4].upper()
        tracking_id = f"PRAH-{date_str}-{uuid_first_4}"
        
        reports_list.append({
            "id": sig.id,
            "tracking_id": tracking_id,
            "domain": sig.domain or "Pending",
            "status": sig.status,
            "created_at": sig.created_at
        })

    return render(request, "profile.html", {
        "reports": reports_list
    })

@login_required(login_url="/citizen/login/")
def link_existing_report(request):
    """
    POST /profile/link/ - Links an anonymous report to the logged-in user.
    """
    if request.user.is_staff:
        return redirect("/coordinator/dashboard/")

    if request.method == "POST":
        tracking_id = request.POST.get("tracking_id", "").strip()
        return_key = request.POST.get("return_key", "").strip().upper()

        if not tracking_id or not return_key:
            messages.error(request, "Please fill in all fields. / कृपया सभी फ़ील्ड भरें।")
            return redirect("/profile/")

        try:
            signal = resolve_signal(tracking_id)
        except Exception:
            messages.error(request, "Report not found. / रिपोर्ट नहीं मिली।")
            return redirect("/profile/")

        # If already owned
        if signal.user is not None:
            messages.error(request, "This report is already linked to an account. / यह रिपोर्ट पहले से ही एक खाते से लिंक है।")
            return redirect("/profile/")

        # Verify Return Key
        stored_hash = signal.metadata.get("anonymous_code") if signal.metadata else None
        if not stored_hash:
            messages.error(request, "This report cannot be linked. / यह रिपोर्ट लिंक नहीं की जा सकती।")
            return redirect("/profile/")

        entered_hash = hashlib.sha256(return_key.encode()).hexdigest()
        if entered_hash == stored_hash:
            # Associate ownership
            signal.user = request.user
            signal.save(update_fields=["user"])
            messages.success(request, "Report successfully linked! / रिपोर्ट सफलतापूर्वक लिंक हो गई!")
            logger.info("Report %s linked to citizen: %s", signal.id, request.user.email)
        else:
            messages.error(request, "Invalid Return Key. / अमान्य रिटर्न कुंजी।")

    return redirect("/profile/")
