from django.core.paginator import Paginator
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from apps.core.decorators import member_required

from .selectors import whisper_selector
from .services import whisper_service

PAGE_SIZE = 20


@never_cache
@member_required
@require_safe
def inbox(request):
    page = Paginator(whisper_selector.inbox(request.user), PAGE_SIZE).get_page(request.GET.get("page"))
    # Render the unread markers first, then clear them for next time.
    unread_ids = {w.pk for w in page.object_list if not w.is_read}
    response = render(
        request,
        "whispers/inbox.html",
        {"page": page, "unread_ids": unread_ids, "active_tab": "portal", "unread_whispers": 0},
    )
    if unread_ids:
        whisper_service.mark_all_read(request.user)
    return response
