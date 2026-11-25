"""
Account views. Each view only parses the request, calls a service, and
renders or redirects. Business rules live in services/.
"""

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods, require_POST

from apps.checkin.selectors import checkin_selector
from apps.core.decorators import member_required
from apps.memberships.selectors import membership_selector

from . import flow
from .forms import (
    ChangePasswordForm,
    LoginForm,
    OTPForm,
    PasswordResetConfirmForm,
    PasswordResetRequestForm,
    ProfileForm,
    RegistrationForm,
)
from .selectors import member_selector
from .services import auth_service, otp_service, profile_service, registration_service
from .services.registration_service import RegistrationData

AUTH_BACKEND = "django.contrib.auth.backends.ModelBackend"


def _client_ip(request):
    # X-Real-IP is only trusted behind our own Nginx (production); otherwise a
    # client could forge it to dodge the per-IP login limit.
    if settings.TRUST_X_REAL_IP:
        return request.META.get("HTTP_X_REAL_IP") or request.META.get("REMOTE_ADDR", "")
    return request.META.get("REMOTE_ADDR", "")


def _safe_next(request):
    """The ?next= target, only if it points back into this site (no open redirect)."""
    target = request.POST.get("next") or request.GET.get("next") or ""
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return target
    return ""


def _redirect_if_signed_in(request):
    if request.user.is_authenticated and request.user.is_verified:
        return redirect("core:portal")
    return None


# ---------------------------------------------------------------------------
# Registration and verification
# ---------------------------------------------------------------------------
@never_cache
@sensitive_post_parameters("password", "password_confirm")
@require_http_methods(["GET", "POST"])
def register(request):
    if (response := _redirect_if_signed_in(request)) is not None:
        return response

    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = RegistrationData(**{k: v for k, v in form.cleaned_data.items() if k in RegistrationData.__annotations__})
        try:
            member = registration_service.register_member(data)
        except otp_service.OTPError as exc:
            form.add_error(None, str(exc))
        else:
            flow.remember_pending_member(request, member)
            messages.success(request, _("We sent a 6-digit code to %(email)s.") % {"email": member.email})
            return redirect("accounts:verify")
    return render(request, "accounts/register.html", {"form": form})


@never_cache
@require_http_methods(["GET", "POST"])
def verify(request):
    member = member_selector.get_member_by_id(flow.pending_member_id(request))
    if member is None:
        return redirect("accounts:login")
    if member.is_verified:
        flow.forget_pending_member(request)
        return redirect("core:portal")

    form = OTPForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            registration_service.verify_email(member, form.cleaned_data["code"])
        except otp_service.OTPError as exc:
            form.add_error("code", str(exc))
        else:
            flow.forget_pending_member(request)
            login(request, member, backend=AUTH_BACKEND)
            messages.success(request, _("Welcome to Lucid Society."))
            return redirect("core:portal")
    return render(
        request,
        "accounts/verify.html",
        {"form": form, "email": member.email, "minutes": settings.OTP_TTL_SECONDS // 60},
    )


@require_POST
def resend_code(request):
    member = member_selector.get_member_by_id(flow.pending_member_id(request))
    if member is None or member.is_verified:
        return redirect("accounts:login")
    try:
        registration_service.resend_verification(member)
    except otp_service.OTPError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, _("A new code is on its way."))
    return redirect("accounts:verify")


# ---------------------------------------------------------------------------
# Login and logout
# ---------------------------------------------------------------------------
@never_cache
@sensitive_post_parameters("password")
@require_http_methods(["GET", "POST"])
def login_view(request):
    if (response := _redirect_if_signed_in(request)) is not None:
        return response

    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            member = auth_service.authenticate_member(
                request, form.cleaned_data["email"], form.cleaned_data["password"], _client_ip(request)
            )
        except auth_service.LoginError as exc:
            form.add_error(None, str(exc))
        else:
            if not member.is_verified:
                # Right password but email not verified yet: finish verification first.
                flow.remember_pending_member(request, member)
                messages.info(request, _("Please verify your email to continue."))
                return redirect("accounts:verify")
            login(request, member)
            return redirect(_safe_next(request) or "core:portal")
    return render(request, "accounts/login.html", {"form": form, "next": _safe_next(request)})


@require_POST
def logout_view(request):
    logout(request)
    return redirect("core:welcome")


# ---------------------------------------------------------------------------
# Password reset by email code
# ---------------------------------------------------------------------------
@never_cache
@require_http_methods(["GET", "POST"])
def password_reset_request(request):
    form = PasswordResetRequestForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"]
        auth_service.request_password_reset(email)
        flow.remember_reset_email(request, email)
        # Same message whether or not the account exists.
        messages.success(request, _("If an account exists for that email, a reset code has been sent."))
        return redirect("accounts:password_reset_confirm")
    return render(request, "accounts/password_reset_request.html", {"form": form})


@never_cache
@sensitive_post_parameters("new_password", "new_password_confirm")
@require_http_methods(["GET", "POST"])
def password_reset_confirm(request):
    email = flow.reset_email(request)
    if not email:
        return redirect("accounts:password_reset")

    form = PasswordResetConfirmForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            auth_service.reset_password(email, form.cleaned_data["code"], form.cleaned_data["new_password"])
        except otp_service.OTPError as exc:
            form.add_error("code", str(exc))
        else:
            flow.forget_reset_email(request)
            messages.success(request, _("Your password has been reset. Please sign in."))
            return redirect("accounts:login")
    return render(request, "accounts/password_reset_confirm.html", {"form": form, "email": email})


# ---------------------------------------------------------------------------
# Identity (profile)
# ---------------------------------------------------------------------------
@member_required
@require_http_methods(["GET", "POST"])
def identity(request):
    form = ProfileForm(request.POST or None, member=request.user)
    if request.method == "POST" and form.is_valid():
        profile_service.update_profile(request.user, **form.cleaned_data)
        messages.success(request, _("Your profile has been updated."))
        return redirect("accounts:identity")
    context = {
        "form": form,
        "active_tab": "identity",
        "membership": membership_selector.current_membership(request.user),
        "visits": checkin_selector.visit_summary(request.user),
    }
    return render(request, "portal/identity.html", context)


@member_required
@sensitive_post_parameters("current_password", "new_password", "new_password_confirm")
@require_http_methods(["GET", "POST"])
def change_password(request):
    form = ChangePasswordForm(request.POST or None, member=request.user)
    if request.method == "POST" and form.is_valid():
        profile_service.change_password(request, request.user, form.cleaned_data["new_password"])
        messages.success(request, _("Your password has been changed."))
        return redirect("accounts:identity")
    return render(request, "portal/change_password.html", {"form": form, "active_tab": "identity"})
