from django.urls import path

from . import views

app_name = "reveal"

urlpatterns = [
    path("portal/reveal/", views.reveal_page, name="reveal"),
    path("portal/reveal/spin/", views.spin_wheel, name="spin"),
]
