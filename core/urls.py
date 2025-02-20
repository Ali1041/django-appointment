from django.urls import path
from . import views

urlpatterns = [
    path("", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("bookings/", views.booking_list, name="booking_list"),
    path("booking/create/", views.create_booking, name="create_booking"),
    path("booking/<int:booking_id>/edit/", views.edit_booking, name="edit_booking"),
    path("/blogs", views.get_blogs, name="blogs"),
    path("/blog/<int:blog_id>/", views.get_blog_detail, name="blog"),
]
