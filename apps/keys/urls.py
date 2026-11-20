from django.urls import path

from . import views

app_name = "keys"

urlpatterns = [
    path("portal/keys/", views.keys_page, name="keys"),
]
