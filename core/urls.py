from django.urls import path
from . import views

urlpatterns = [
    path("", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("bookings/", views.booking_list, name="booking_list"),
    path("booking/create/", views.create_booking, name="create_booking"),
    path("booking/<int:booking_id>/edit/", views.edit_booking, name="edit_booking"),
    path("booking/<int:booking_id>/delete/", views.delete_booking, name="delete_booking"),
    path("booking/ai-create/", views.ai_create_booking, name="ai_create_booking"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("/blogs", views.get_blogs, name="blogs"),
    path("/blog/<int:blog_id>/", views.get_blog_detail, name="blog"),
    path("customers/", views.customer_list, name="customer_list"),
    path("customer/create/", views.create_customer, name="create_customer"),
    path("customer/<int:customer_id>/edit/", views.edit_customer, name="edit_customer"),
    path("customer/<int:customer_id>/delete/", views.delete_customer, name="delete_customer"),
]
