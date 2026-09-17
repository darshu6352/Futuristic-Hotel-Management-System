from django.db import models
    

class add_rooms_view(models.Model):
    image = models.ImageField(upload_to='Rooms/')
    image2 = models.ImageField(upload_to='Rooms/', blank=True, null=True)
    image3 = models.ImageField(upload_to='Rooms/', blank=True, null=True)

    room_number = models.CharField(max_length=1000, null=True, blank=True)
    Roomtype = models.CharField(max_length=100, null=False, blank=False)
    # address = models.TextField(default="", blank=True)  
    facilities = models.TextField(default="", blank=True)
    Price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)


    def __str__(self):
        return f"Room {self.room_number} - {self.Roomtype}"
        # return self.Roomtype

    
class Booking_Room(models.Model):

    room = models.ForeignKey(
        add_rooms_view,
        on_delete=models.CASCADE,
        related_name="bookings",
        null=True,
        blank=True
    )

    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('Confirmed', 'Confirmed'),
        ('Rejected', 'Rejected'),
    )

    
    name = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField() 
    phone = models.CharField(max_length=10)

    room_type = models.CharField(
        max_length=1000,
        blank=True,
        null=True
    )

    checkin = models.DateField()
    checkout = models.DateField()

    people = models.PositiveIntegerField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='Pending'
    )
    

    reject_reason = models.TextField(
        blank=True,
        null=True
    )




class Customer(models.Model):
    first_name = models.CharField(max_length=100) 
    surname = models.CharField(max_length=100) 
    mobile = models.CharField(max_length=10, unique=True) 
    aadhaar = models.CharField(max_length=12, unique=True) 
    dob = models.DateField() 
    email = models.EmailField(unique=True) 
    password = models.CharField(max_length=128) 
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self): 
        return f"{self.first_name} {self.surname}"


class CarBooking(models.Model):
    room_number = models.CharField(max_length=50)
    full_name = models.CharField(max_length=100)
    car_capacity = models.IntegerField()
    selected_places = models.TextField()
    booking_date = models.DateField()
    booking_time = models.TimeField()
    estimated_km = models.FloatField(default=0.0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    is_paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    phone_number = models.CharField(max_length=10, blank=True, null=True)

    def __str__(self):
        return f"Room {self.room_number} - {self.full_name}"



class Problem(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    problem = models.TextField(max_length=200)
    rating = models.IntegerField()
    answer = models.TextField(max_length=500, blank=True, null=True)

    def __str__(self):
        return self.name
