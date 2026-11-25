"""
Manager-only dashboard pages: overview, members, seal tiers, wheel prizes,
the treasure catalogue and the audit log. Every change goes through a
service that writes an audit entry.
"""

from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST, require_safe

from apps.accounts.models import Member
from apps.accounts.selectors import member_selector
from apps.accounts.services import member_admin_service
from apps.audit.selectors import audit_selector
from apps.core.decorators import manager_required
from apps.core.images import ImageError
from apps.keys.selectors import keys_selector
from apps.keys.services import adjust_service
from apps.memberships.selectors import membership_selector
from apps.memberships.services import membership_service, tier_service
from apps.reveal.services import prize_service
from apps.treasures.services import catalog_service

from ..forms import GrantSealForm, KeysAdjustForm, PrizeForm, SpendingForm, SuspendForm, TierForm, TreasureForm
from ..selectors import manage_selector, report_selector


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------
@never_cache
@manager_required
@require_safe
def overview(request):
    return render(request, "dashboard/overview.html", {"report": report_selector.overview(), "section": "overview"})


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------
@never_cache
@manager_required
@require_safe
def members(request):
    query = request.GET.get("q", "")
    status = request.GET.get("status", "")
    if status not in Member.Status.values:
        status = ""
    context = {
        "query": query,
        "status": status,
        "statuses": Member.Status.choices,
        "members": member_selector.search_members(query, status),
        "section": "members",
    }
    return render(request, "dashboard/members.html", context)


def _member_context(request, member, **forms):
    context = {
        "member": member,
        "membership": membership_selector.current_membership(member),
        "balance": keys_selector.balance_of(member),
        "ledger": keys_selector.history(member)[:15],
        **manage_selector.member_activity(member),
        "audit": audit_selector.for_target(member, 20),
        "suspend_form": forms.get("suspend_form") or SuspendForm(),
        "adjust_form": forms.get("adjust_form") or KeysAdjustForm(),
        "grant_form": forms.get("grant_form") or GrantSealForm(),
        "spending_form": SpendingForm(),
        "section": "members",
    }
    return render(request, "dashboard/member_detail.html", context)


@never_cache
@manager_required
@require_safe
def member_detail(request, member_id):
    return _member_context(request, member_selector.member_for_staff_or_404(member_id))


@manager_required
@require_POST
def member_suspend(request, member_id):
    member = member_selector.member_for_staff_or_404(member_id)
    form = SuspendForm(request.POST)
    if not form.is_valid():
        return _member_context(request, member, suspend_form=form)
    try:
        member_admin_service.suspend(member, request.user, form.cleaned_data["reason"])
    except member_admin_service.MemberAdminError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, _("%(name)s is suspended.") % {"name": member.full_name})
    return redirect("dashboard:member_detail", member_id=member.pk)


@manager_required
@require_POST
def member_reactivate(request, member_id):
    member = member_selector.member_for_staff_or_404(member_id)
    try:
        member_admin_service.reactivate(member, request.user)
    except member_admin_service.MemberAdminError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, _("%(name)s is active again.") % {"name": member.full_name})
    return redirect("dashboard:member_detail", member_id=member.pk)


@manager_required
@require_POST
def member_adjust_keys(request, member_id):
    member = member_selector.member_for_staff_or_404(member_id)
    form = KeysAdjustForm(request.POST)
    if not form.is_valid():
        return _member_context(request, member, adjust_form=form)
    data = form.cleaned_data
    try:
        entry = adjust_service.adjust(
            member, data["delta"], data["note"], request.user, tell_member=data["tell_member"]
        )
    except adjust_service.AdjustError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, _("Keys updated. New balance: %(n)d.") % {"n": entry.balance_after})
    return redirect("dashboard:member_detail", member_id=member.pk)


@manager_required
@require_POST
def member_grant_seal(request, member_id):
    member = member_selector.member_for_staff_or_404(member_id)
    form = GrantSealForm(request.POST)
    if not form.is_valid():
        return _member_context(request, member, grant_form=form)
    data = form.cleaned_data
    membership_service.grant_staff_membership(
        member, data["tier"], data["days"], request.user, credit_keys=data["credit_keys"]
    )
    messages.success(
        request, _("%(tier)s granted for %(days)d days.") % {"tier": data["tier"].name, "days": data["days"]}
    )
    return redirect("dashboard:member_detail", member_id=member.pk)


# ---------------------------------------------------------------------------
# Seal tiers
# ---------------------------------------------------------------------------
@never_cache
@manager_required
@require_safe
def tiers(request):
    context = {"tiers": manage_selector.all_tiers(), "section": "settings"}
    return render(request, "dashboard/tiers.html", context)


@never_cache
@manager_required
@require_http_methods(["GET", "POST"])
def tier_edit(request, tier_id):
    tier = manage_selector.tier_or_404(tier_id)
    form = TierForm(request.POST or None, instance=manage_selector.tier_or_404(tier_id))
    if request.method == "POST" and form.is_valid():
        try:
            tier_service.update(tier, request.user, **form.service_values())
        except tier_service.TierError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, _("%(name)s saved.") % {"name": tier.name})
            return redirect("dashboard:tiers")
    return render(request, "dashboard/edit_form.html", _edit_context(form, tier.name, "dashboard:tiers"))


def _edit_context(form, title, back, multipart=False):
    return {"form": form, "title": title, "back": back, "multipart": multipart, "section": "settings"}


# ---------------------------------------------------------------------------
# Wheel prizes
# ---------------------------------------------------------------------------
@never_cache
@manager_required
@require_safe
def prizes(request):
    context = {"prizes": manage_selector.prizes_with_chance(), "section": "settings"}
    return render(request, "dashboard/prizes.html", context)


@never_cache
@manager_required
@require_http_methods(["GET", "POST"])
def prize_edit(request, prize_id=None):
    prize = manage_selector.prize_or_404(prize_id) if prize_id else None
    form = PrizeForm(request.POST or None, instance=manage_selector.prize_or_404(prize_id) if prize_id else None)
    if request.method == "POST" and form.is_valid():
        try:
            saved = prize_service.save(request.user, prize, **form.service_values())
        except prize_service.PrizeError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, _("%(name)s saved.") % {"name": saved.label})
            return redirect("dashboard:prizes")
    title = prize.label if prize else _("New prize")
    return render(request, "dashboard/edit_form.html", _edit_context(form, title, "dashboard:prizes"))


# ---------------------------------------------------------------------------
# Treasure catalogue
# ---------------------------------------------------------------------------
@never_cache
@manager_required
@require_safe
def catalog(request):
    context = {"treasures": manage_selector.catalog(), "section": "catalog"}
    return render(request, "dashboard/catalog.html", context)


@never_cache
@manager_required
@require_http_methods(["GET", "POST"])
def treasure_edit(request, treasure_id=None):
    treasure = manage_selector.treasure_or_404(treasure_id) if treasure_id else None
    instance = manage_selector.treasure_or_404(treasure_id) if treasure_id else None
    form = TreasureForm(request.POST or None, request.FILES or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        try:
            saved = catalog_service.save(
                request.user,
                treasure,
                image=form.cleaned_data.get("new_image"),
                remove_image=form.cleaned_data.get("remove_image", False),
                **form.service_values(),
            )
        except ImageError as exc:
            form.add_error("new_image", str(exc))
        else:
            messages.success(request, _("%(name)s saved.") % {"name": saved.name})
            return redirect("dashboard:catalog")
    title = treasure.name if treasure else _("New treasure")
    context = _edit_context(form, title, "dashboard:catalog", multipart=True)
    context.update({"section": "catalog", "current_image": treasure.image if treasure else None})
    return render(request, "dashboard/edit_form.html", context)


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------
@never_cache
@manager_required
@require_safe
def audit_log(request):
    prefix = request.GET.get("type", "")
    if prefix not in audit_selector.action_prefixes():
        prefix = ""
    page = Paginator(audit_selector.recent(prefix, limit=2000), 50).get_page(request.GET.get("page"))
    context = {"page": page, "prefix": prefix, "prefixes": audit_selector.action_prefixes(), "section": "audit"}
    return render(request, "dashboard/audit.html", context)
