from django.urls import path

from . import views

app_name = "treasures"

urlpatterns = [
    path("portal/treasures/", views.catalog, name="catalog"),
    path("portal/treasures/<int:treasure_id>/", views.detail, name="detail"),
    path("portal/treasures/<int:treasure_id>/unlock/", views.unlock, name="unlock"),
]
