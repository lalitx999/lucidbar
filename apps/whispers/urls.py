from django.urls import path

from . import views

app_name = "whispers"

urlpatterns = [
    path("portal/whispers/", views.inbox, name="inbox"),
]
