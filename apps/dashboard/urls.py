from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.home, name="home"),
    path("door/", views.door, name="door"),
    path("door/scan/", views.door_scan, name="door_scan"),
    path("bookings/", views.bookings, name="bookings"),
    path("bookings/<int:booking_id>/confirm/", views.booking_confirm, name="booking_confirm"),
    path("bookings/<int:booking_id>/decline/", views.booking_decline, name="booking_decline"),
    path("payments/", views.payments, name="payments"),
    path("payments/<str:reference>/", views.payment_detail, name="payment_detail"),
    path("payments/<str:reference>/approve/", views.payment_approve, name="payment_approve"),
    path("payments/<str:reference>/reject/", views.payment_reject, name="payment_reject"),
    path("slips/<int:slip_id>/image/", views.slip_image, name="slip_image"),
    path("treasures/", views.redemptions, name="redemptions"),
    path("treasures/<int:redemption_id>/hand-over/", views.redemption_hand_over, name="redemption_hand_over"),
    path("treasures/<int:redemption_id>/cancel/", views.redemption_cancel, name="redemption_cancel"),
    path("reveal/", views.reveal, name="reveal"),
    path("reveal/draw/", views.reveal_draw, name="reveal_draw"),
    path("reveal/prizes/<int:spin_id>/hand-over/", views.prize_hand_over, name="prize_hand_over"),
    path("broadcasts/", views.broadcasts, name="broadcasts"),
]
