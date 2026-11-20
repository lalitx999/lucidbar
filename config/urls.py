from django.conf import settings
from django.contrib import admin
from django.urls import include, path

# Django Admin is for the superuser only. Its URL comes from the environment
# so it is not guessable. Staff use the custom dashboard (later phase).
ADMIN_URL = settings.ADMIN_URL

urlpatterns = [
    path(ADMIN_URL, admin.site.urls),
    path("", include("apps.core.urls")),
    path("", include("apps.accounts.urls")),
    path("", include("apps.payments.urls")),
    path("", include("apps.keys.urls")),
    path("", include("apps.treasures.urls")),
    path("staff/", include("apps.dashboard.urls")),
]

if settings.DEBUG:
    # Public media (treasure images) in local development. In production
    # Nginx serves /media/. Payment slips are in private storage, never here.
    from django.conf.urls.static import static

    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
