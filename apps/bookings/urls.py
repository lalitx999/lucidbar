from django.urls import path

from . import views

app_name = "bookings"

urlpatterns = [
    path("portal/chamber/", views.chamber, name="chamber"),
    path("portal/chamber/<str:reference>/cancel/", views.cancel, name="cancel"),
]
