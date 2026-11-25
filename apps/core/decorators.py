"""Access-control decorators for member and staff views."""

from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
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
    """
    Allow only active staff accounts. Anonymous visitors go to login; a
    signed-in member without staff rights gets 403 (no redirect loop).
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not (user.is_active and user.is_staff):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return wrapper


MANAGER_GROUP = "Manager"


def is_manager(user) -> bool:
    """Cached on the user object, so the decorator and the nav share one query per request."""
    if not (user.is_authenticated and user.is_active and user.is_staff):
        return False
    cached = getattr(user, "_lucid_is_manager", None)
    if cached is None:
        cached = user.is_superuser or user.groups.filter(name=MANAGER_GROUP).exists()
        user._lucid_is_manager = cached
    return cached


def manager_required(view_func):
    """Like staff_required, but only for the Manager group (or superuser)."""

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not is_manager(request.user):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return wrapper
