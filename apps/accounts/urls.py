from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("join/", views.register, name="register"),
    path("verify/", views.verify, name="verify"),
    path("verify/resend/", views.resend_code, name="resend_code"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("forgot/", views.password_reset_request, name="password_reset"),
    path("forgot/confirm/", views.password_reset_confirm, name="password_reset_confirm"),
    path("portal/identity/", views.identity, name="identity"),
    path("portal/identity/password/", views.change_password, name="change_password"),
]
