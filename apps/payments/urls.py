from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path("portal/seal/", views.choose_seal, name="choose_seal"),
    path("portal/pay/<str:reference>/", views.pay, name="pay"),
    path("portal/pay/<str:reference>/slip/", views.upload_slip, name="upload_slip"),
    path("portal/pay/<str:reference>/cancel/", views.cancel, name="cancel"),
    path("portal/pay/<str:reference>/status/", views.status, name="status"),
]
