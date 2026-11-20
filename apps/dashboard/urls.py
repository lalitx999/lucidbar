from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.home, name="home"),
    path("payments/", views.payments, name="payments"),
    path("payments/<str:reference>/", views.payment_detail, name="payment_detail"),
    path("payments/<str:reference>/approve/", views.payment_approve, name="payment_approve"),
    path("payments/<str:reference>/reject/", views.payment_reject, name="payment_reject"),
    path("slips/<int:slip_id>/image/", views.slip_image, name="slip_image"),
]
