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
    path("staff/", include("apps.dashboard.urls")),
]
