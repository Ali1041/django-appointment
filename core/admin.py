from django.contrib import admin
from .models import Booking, Court, Blogs

# Register your models here.
admin.site.register(Court)
admin.site.register(Booking)
admin.site.register(Blogs)
