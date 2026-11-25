from django.urls import path

from . import views

app_name = "checkin"

urlpatterns = [
    path("portal/identity/card.svg", views.card_qr, name="card_qr"),
]
