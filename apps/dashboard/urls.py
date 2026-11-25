from django.urls import path

from .views import manager, operations

app_name = "dashboard"

urlpatterns = [
    path("", operations.home, name="home"),
    # Staff: door, bookings, hand-over
    path("door/", operations.door, name="door"),
    path("door/scan/", operations.door_scan, name="door_scan"),
    path("members/<int:member_id>/spending/", operations.member_spending, name="member_spending"),
    path("bookings/", operations.bookings, name="bookings"),
    path("bookings/<int:booking_id>/confirm/", operations.booking_confirm, name="booking_confirm"),
    path("bookings/<int:booking_id>/decline/", operations.booking_decline, name="booking_decline"),
    path("treasures/", operations.redemptions, name="redemptions"),
    path("treasures/<int:redemption_id>/hand-over/", operations.redemption_hand_over, name="redemption_hand_over"),
    path("treasures/<int:redemption_id>/cancel/", operations.redemption_cancel, name="redemption_cancel"),
    path("reveal/", operations.reveal, name="reveal"),
    path("reveal/draw/", operations.reveal_draw, name="reveal_draw"),
    path("reveal/prizes/<int:spin_id>/hand-over/", operations.prize_hand_over, name="prize_hand_over"),
    # Manager
    path("overview/", manager.overview, name="overview"),
    path("payments/", operations.payments, name="payments"),
    path("payments/<str:reference>/", operations.payment_detail, name="payment_detail"),
    path("payments/<str:reference>/approve/", operations.payment_approve, name="payment_approve"),
    path("payments/<str:reference>/reject/", operations.payment_reject, name="payment_reject"),
    path("slips/<int:slip_id>/image/", operations.slip_image, name="slip_image"),
    path("members/", manager.members, name="members"),
    path("members/<int:member_id>/", manager.member_detail, name="member_detail"),
    path("members/<int:member_id>/suspend/", manager.member_suspend, name="member_suspend"),
    path("members/<int:member_id>/reactivate/", manager.member_reactivate, name="member_reactivate"),
    path("members/<int:member_id>/keys/", manager.member_adjust_keys, name="member_adjust_keys"),
    path("members/<int:member_id>/seal/", manager.member_grant_seal, name="member_grant_seal"),
    path("catalog/", manager.catalog, name="catalog"),
    path("catalog/new/", manager.treasure_edit, name="treasure_new"),
    path("catalog/<int:treasure_id>/", manager.treasure_edit, name="treasure_edit"),
    path("settings/tiers/", manager.tiers, name="tiers"),
    path("settings/tiers/<int:tier_id>/", manager.tier_edit, name="tier_edit"),
    path("settings/prizes/", manager.prizes, name="prizes"),
    path("settings/prizes/new/", manager.prize_edit, name="prize_new"),
    path("settings/prizes/<int:prize_id>/", manager.prize_edit, name="prize_edit"),
    path("broadcasts/", operations.broadcasts, name="broadcasts"),
    path("audit/", manager.audit_log, name="audit"),
]
