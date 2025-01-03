from django.urls import path
from . import views

urlpatterns = [
    path("", views.booking_list, name="booking_list"),
    path("booking/create/", views.create_booking, name="create_booking"),
    path("booking/<int:booking_id>/edit/", views.edit_booking, name="edit_booking"),
]
