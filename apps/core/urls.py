from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.welcome, name="welcome"),
    path("portal/", views.portal, name="portal"),
    path("healthz/", views.healthz, name="healthz"),
    path("favicon.ico", views.favicon, name="favicon"),
]
