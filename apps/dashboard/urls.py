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
    path("treasures/", views.redemptions, name="redemptions"),
    path("treasures/<int:redemption_id>/hand-over/", views.redemption_hand_over, name="redemption_hand_over"),
    path("treasures/<int:redemption_id>/cancel/", views.redemption_cancel, name="redemption_cancel"),
]
