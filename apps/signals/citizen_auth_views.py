import logging
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.db import IntegrityError

logger = logging.getLogger(__name__)

def citizen_register(request):
    """
    GET /citizen/register/ - Renders registration form.
    POST /citizen/register/ - Registers citizen and logs them in.
    """
    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect("/coordinator/dashboard/")
        return redirect("/profile/")

    error = None
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")
        confirm_password = request.POST.get("confirm_password", "")

        if not email or not password or not confirm_password:
            error = "All fields are required. / सभी फ़ील्ड भरना आवश्यक है।"
        elif password != confirm_password:
            error = "Passwords do not match. / पासवर्ड मेल नहीं खाते हैं।"
        elif len(password) < 6:
            error = "Password must be at least 6 characters. / पासवर्ड कम से कम 6 अक्षरों का होना चाहिए।"
        else:
            try:
                # Check for existing email in username (since username=email for citizens)
                if User.objects.filter(username=email).exists():
                    error = "An account with this email already exists. / इस ईमेल के साथ एक खाता पहले से मौजूद है।"
                else:
                    # Create native Django User
                    user = User.objects.create_user(
                        username=email,
                        email=email,
                        password=password,
                        is_staff=False
                    )
                    login(request, user)
                    logger.info("Citizen registered successfully: %s", email)
                    return redirect("/profile/")
            except IntegrityError:
                error = "An error occurred. Please try again. / एक त्रुटि हुई। कृपया पुनः प्रयास करें।"

    return render(request, "citizen_register.html", {"error": error})

def citizen_login(request):
    """
    GET /citizen/login/ - Renders citizen login form.
    POST /citizen/login/ - Authenticates and logs citizen in.
    """
    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect("/coordinator/dashboard/")
        return redirect("/profile/")

    error = None
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")

        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            logger.info("Citizen logged in: %s", email)
            if user.is_staff:
                return redirect("/coordinator/dashboard/")
            return redirect("/profile/")
        else:
            error = "Invalid email or password. / अमान्य ईमेल या पासवर्ड।"

    return render(request, "citizen_login.html", {"error": error})

def citizen_logout_view(request):
    """
    GET /citizen/logout/ - Logs out citizen and redirects to home page.
    """
    logout(request)
    return redirect("/")
