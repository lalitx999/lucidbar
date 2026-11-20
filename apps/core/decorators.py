"""Access-control decorators for member and staff views."""

from functools import wraps

from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect

from apps.accounts.flow import remember_pending_member


def member_required(view_func):
    """
    Allow only signed-in, verified members.

    Anonymous visitors go to login. A signed-in member who has not verified
    their email yet is sent to the verification screen.
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not user.is_verified:
            remember_pending_member(request, user)
            return redirect("accounts:verify")
        return view_func(request, *args, **kwargs)

    return wrapper


def staff_required(view_func):
    """Allow only active staff accounts (used by the dashboard in later phases)."""
    return user_passes_test(lambda u: u.is_authenticated and u.is_active and u.is_staff)(view_func)
