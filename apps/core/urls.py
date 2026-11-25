from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.welcome, name="welcome"),
    path("portal/", views.portal, name="portal"),
    path("healthz/", views.healthz, name="healthz"),
    path("favicon.ico", views.favicon, name="favicon"),
    path("manifest.webmanifest", views.web_manifest, name="manifest"),
    path("sw.js", views.service_worker, name="service_worker"),
    path("offline/", views.offline, name="offline"),
]
