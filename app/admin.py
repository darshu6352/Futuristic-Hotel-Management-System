from django.contrib import admin
from .models import add_rooms_view,  Booking_Room, Customer, Problem, CarBooking
# Register your models here.

admin.site.register(add_rooms_view)
admin.site.register(Booking_Room)
admin.site.register(Customer)
admin.site.register(Problem)
admin.site.register(CarBooking)
