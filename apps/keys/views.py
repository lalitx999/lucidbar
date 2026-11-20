from django.core.paginator import Paginator
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from apps.core.decorators import member_required

from .selectors import keys_selector

PAGE_SIZE = 25


@never_cache
@member_required
@require_safe
def keys_page(request):
    page = Paginator(keys_selector.history(request.user), PAGE_SIZE).get_page(request.GET.get("page"))
    context = {
        "balance": keys_selector.balance_of(request.user),
        "page": page,
        "active_tab": "keys",
    }
    return render(request, "keys/keys.html", context)
