import qrcode
from django.shortcuts import render
from django.shortcuts import redirect, get_object_or_404
from django.db.models import Q
from .models import CarBooking, Problem
from .models import add_rooms_view
from .models import Booking_Room, Customer
# **********************
from io import BytesIO
import base64
from django.utils import timezone
# **********************
from django.contrib import messages
from datetime import datetime
# For EMAIL Sending
from django.core.mail import send_mail
from django.conf import settings
from .models import Booking_Room
# *********************
from django.contrib.auth.hashers  import make_password, check_password 

import json
import random

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.cache import cache

# Create your views here.

def home(request):
    return render(request,  'home.html')


def problems(request):
    if request.method == "POST":

        name = request.POST.get("name")

        email = request.POST.get("email")

        problem = request.POST.get("problem")

        rating = request.POST.get("rating")

        Problem.objects.create(
            name=name,
            email=email,
            problem=problem,
            rating=rating
        )
        return redirect('problems')

    return render(request, 'problems.html')



def RoomsBook(request):
    search_query = request.GET.get("srch", "").strip()
    rooms = add_rooms_view.objects.all()

    if search_query:
        rooms = rooms.filter(Roomtype__icontains=search_query)

    today = timezone.localdate()

    for room in rooms:
        # Check if room has ANY active booking currently running or starting today onwards
        active_booking = Booking_Room.objects.filter(
            room=room,
            status__in=["Pending", "Confirmed"],
            checkin__lte=today,
            checkout__gte=today  # Current ongoing stay
        ).order_by("-checkout").first()

        if active_booking:
            room.is_available = False
            room.current_booking = active_booking
        else:
            room.is_available = True
            room.current_booking = None

    return render(
        request,
        "RoomsBook.html",
        {"data": rooms, "search_query": search_query},
    )


def Room_Bookd(request):
    room_id = request.GET.get("room")
    room = get_object_or_404(add_rooms_view, id=room_id)

    if request.method == "POST":
        name = request.POST.get("name")
        email = request.POST.get("email")
        phone = request.POST.get("phone")
        checkin = request.POST.get("checkin")
        checkout = request.POST.get("checkout")
        people = int(request.POST.get("people",1))

        # 1. Check Date Overlap
        already_booked = Booking_Room.objects.filter(
            room=room,
            status__in=["Pending", "Confirmed"],
            checkin__lt=checkout,
            checkout__gt=checkin
        ).exists()

        if already_booked:
            return render(
                request,
                "Room_Bookd.html",
                {
                    "room": room,
                    "error": "This room is already booked for selected dates."
                }
            )
        checkin_date = datetime.strptime(checkin, "%Y-%m-%d")
        checkout_date = datetime.strptime(checkout, "%Y-%m-%d")
        total_days = max((checkout_date - checkin_date).days, 1)

        total_amount = people * float(room.Price) * total_days

        # 2. Database me direct Save karein
        booking = Booking_Room.objects.create(
            room=room,                   
            name=name,
            email=email,
            phone=phone,
            room_type=room.Roomtype,     
            checkin=checkin,
            checkout=checkout,
            people=people,
            status="Pending"             
        )


        # 3. Created Booking ID ko session me save karein
        request.session["booking_id"] = booking.id
        request.session["total_amount"] = total_amount

        return redirect("payment_qr")

    return render(request, "Room_Bookd.html", {"room": room})



def reject_booking_submit(request, id):

    booking = get_object_or_404(
        Booking_Room,
        id=id
    )



    if request.method == "POST":

        reason = request.POST.get("reason")

        booking.status = "Rejected"
        booking.reject_reason = reason
        booking.save()

        send_mail(
            "Room Booking Cancelled",
            f"""
            Hello {booking.name},

            Your room booking has been cancelled by the hotel.

            Room: {booking.room_type}

            Reason:
            {reason}

            Thank you.
            """,
            settings.EMAIL_HOST_USER,
            [booking.email],
            fail_silently=False,
        )

    return redirect("Rooms_Booking")



# **********************************************
def payment_qr(request):
    booking_id = request.session.get("booking_id")
    total_amount = request.session.get("total_amount")

    if not booking_id:
        return redirect("home")

    booking = get_object_or_404(Booking_Room, id=booking_id)

    # Agar total_amount session me na ho toh backup calculation
    if not total_amount:
        people = int(booking.people) if booking.people else 1
        room_price = float(booking.room.Price) if hasattr(booking, 'room') and booking.room else 0.0
        
        # Check-in / Check-out days difference calculation
        try:
            checkin_dt = datetime.strptime(str(booking.checkin), "%Y-%m-%d")
            checkout_dt = datetime.strptime(str(booking.checkout), "%Y-%m-%d")
            days = max((checkout_dt - checkin_dt).days, 1)
        except Exception:
            days = 1

        total_amount = people * room_price * days

    if request.method == "POST":
        booking.status = "Confirmed"
        booking.save()

        # Confirmation Email
        send_mail(
            "Room Booking Confirmed",
            f"""Hello {booking.name},

            Your room booking has been confirmed successfully.

            Room Type: {booking.room_type}
            Check-in: {booking.checkin}
            Check-out: {booking.checkout}
            People: {booking.people}
            Total Amount Paid: ₹{total_amount}

            Thank you for booking with us.""",
                        settings.EMAIL_HOST_USER,
                        [booking.email],
                        fail_silently=True,
            )

        # Clear Session
        request.session.pop("booking_id", None)
        request.session.pop("total_amount", None)
            
        return redirect("payment_done")

    # --- Dynamic QR Code Generation ---
    upi_id = "your-upi-id@okicici"  # Apni actual UPI ID dalein
    merchant_name = "Hotel Booking"

    upi_string = f"upi://pay?pa={upi_id}&pn={merchant_name}&am={total_amount}&cu=INR"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=2,
    )
    qr.add_data(upi_string)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    qr_code_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    return render(
        request, 
        "payment_qr.html", 
        {
            "booking": booking, 
            "room": booking.room, 
            "qr_code": qr_code_base64,
            "total_amount": total_amount
        }
    )


def payment_done(request):

    booking_data = request.session.get("booking_data")

    if booking_data:

        room = get_object_or_404(
            add_rooms_view,
            id=booking_data.get("room_id")
        )

        Booking_Room.objects.create(

            room=room,

            name=booking_data.get("name"),

            email=booking_data.get("email"),

            phone=booking_data.get("phone"),

            room_type=booking_data.get("room_type"),

            checkin=booking_data.get("checkin"),

            checkout=booking_data.get("checkout"),

            people=booking_data.get("people"),

            # Payment ke baad automatic confirmation
            status="Confirmed"
        )

        del request.session["booking_data"]

    return render(
        request,
        "payment_done.html"
    )




def register(request):
    if request.method == "POST":
        first_name = request.POST.get("first_name")
        surname = request.POST.get("surname")
        mobile = request.POST.get("mobile")
        aadhaar = request.POST.get("aadhaar")
        dob = request.POST.get("dob")
        email = request.POST.get("email")
        password = request.POST.get("password")

        # Check if email already exists
        if Customer.objects.filter(email=email).exists():
            messages.error(request, "Email already registered.")
            return redirect("register")

        # Check if mobile already exists
        if Customer.objects.filter(mobile=mobile).exists():
            messages.error(request, "Mobile number already registered.")
            return redirect("register")

        # Check if Aadhaar already exists
        if Customer.objects.filter(aadhaar=aadhaar).exists():
            messages.error(request, "Aadhaar number already registered.")
            return redirect("register")

        # Create and save customer with hashed password
        customer = Customer(
            first_name=first_name,
            surname=surname,
            mobile=mobile,
            aadhaar=aadhaar,
            dob=dob,
            email=email,
            password=make_password(password)
        )
        customer.save()

        messages.success(request, "Account created successfully! Please login.")
        return redirect("login") # Apne login URL name se badal sakte hain

    return render(request, "register.html")

def login(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        try:
            customer = Customer.objects.get(email=email)
        except Customer.DoesNotExist:
            messages.error(request, "Invalid email or password.")
            return redirect("login")

        # Check password
        if check_password(password, customer.password):
            request.session["customer_id"] = customer.id
            request.session["customer_name"] = f"{customer.first_name} {customer.surname}"
            
            messages.success(request, f"Welcome {customer.first_name}!")
            
            # Yahan 'home' ki jagah 'RoomsBook' kar diya gaya hai
            return redirect("RoomsBook")
        else:
            messages.error(request, "Invalid email or password.")
            return redirect("login")

    return render(request, "login.html")


#**************************************** Admin site ****************************************

def Deshbord(request):
    total_rooms = add_rooms_view.objects.count()
    total_customers = Customer.objects.count()
    total_bookings = Booking_Room.objects.count()
    total_car_bookings = CarBooking.objects.count()
    total_feedback = Problem.objects.count()

    booked_rooms = Booking_Room.objects.filter(status='Confirmed').count() # ya jo bhi status field ho
    available_rooms = max(0, total_rooms - booked_rooms)
    
    available_percentage = (available_rooms / total_rooms * 100) if total_rooms > 0 else 0
    booked_percentage = (booked_rooms / total_rooms * 100) if total_rooms > 0 else 0

    confirmed_bookings = Booking_Room.objects.filter(status='Confirmed').count()
    pending_bookings = Booking_Room.objects.filter(status='Pending').count()
    rejected_bookings = Booking_Room.objects.filter(status='Rejected').count()

    car_revenue = 0 # CarBooking mein price field ho toh Sum('price') karein
    total_revenue = car_revenue # + hotel_revenue agar ho toh

    paid_car_bookings = CarBooking.objects.filter(is_paid=True).count() 
    unpaid_car_bookings = CarBooking.objects.filter(is_paid=False).count()
    solved_problems = Problem.objects.filter(answer__isnull=True).count() # Aapke model ke status ke anusaar
    pending_problems = Problem.objects.filter(answer__isnull=True).count() + Problem.objects.filter(answer="").count()
    
    average_rating = 4.5 # Example

    context = {
        'total_rooms': total_rooms,
        'total_customers': total_customers,
        'total_bookings': total_bookings,
        'total_car_bookings': total_car_bookings,
        'total_feedback': total_feedback,
        'available_rooms': available_rooms,
        'booked_rooms': booked_rooms,
        'available_percentage': round(available_percentage, 1),
        'booked_percentage': round(booked_percentage, 1),
        'confirmed_bookings': confirmed_bookings,
        'pending_bookings': pending_bookings,
        'rejected_bookings': rejected_bookings,
        'total_revenue': total_revenue,
        'car_revenue': car_revenue,
        'paid_car_bookings': 0, # Apne model fields ke hisaab se update karein
        'unpaid_car_bookings': 0,
        'solved_problems': solved_problems,
        'pending_problems': pending_problems,
        'average_rating': average_rating,
        'total_people': total_customers, # Agar guests ka alag count hai toh wo dein
        
        # --- Chart Data (JSON format mein pass karna hoga) ---
        'revenue_labels': ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
        'revenue_data': [1000, 2500, 4000, 3000, 5000, total_revenue],
        
        'people_labels': ["Cust 1", "Cust 2"],
        'people_data': [10, 20],
    }

    return render(request, 'admin/Deshbord.html', context) # Apni html file ka path dein


def Rooms(request):

    data = add_rooms_view.objects.all()

    today = timezone.localdate()

    for room in data:

        booking_count = Booking_Room.objects.filter(
            room=room,
            status__in=["Pending", "Confirmed"],
            checkin__lte=today,
            checkout__gt=today
        ).count()

        room.booking_count = booking_count
        room.is_available = booking_count < 5


    return render(
        request,
        "admin/Rooms.html",
        {
            "data": data
        }
    )


def Add_Rooms(request):
    if request.method == "POST":
        room_type = request.POST.get('Roomtype')
        # address_details = request.POST.get('address')
        facilities = request.POST.get("facilities")
        
        main_image = request.FILES.get('image')
        img2 = request.FILES.get('image2')
        img3 = request.FILES.get('image3')
        price = request.POST.get("Price")
        room_number = request.POST.get("room_number")

        add_rooms_view.objects.create(
            Roomtype=room_type,
            # address=address_details,
            facilities=facilities,
            image=main_image,
            image2=img2,
            image3=img3,
            Price=price,
            room_number=room_number,
        )
        return redirect('Add_Rooms')
    
    data = add_rooms_view.objects.all()
    return render(request, "admin/Add_Rooms.html",{'data': data})

def Rooms_Booking(request):

    bookings = Booking_Room.objects.all().order_by('-id')

    return render(request, "admin/Rooms_Booking.html", {"bookings": bookings})


def confirm_booking(request, id):

    booking = get_object_or_404(Booking_Room, id=id)
    booking.status = "Confirmed"
    booking.save()

    return redirect("Rooms_Booking")


def reject_booking(request, id):

    booking = get_object_or_404(Booking_Room, id=id)
    booking.status = "Rejected"
    booking.save()

    return redirect("Rooms_Booking")




def confirm_booking(request, id):

    booking = get_object_or_404(Booking_Room, id=id)

    booking.status = "Confirmed"
    booking.save()

    send_mail(
        "Room Booking Confirmed",
                f"""
        Hello {booking.name},

        Your room booking has been confirmed successfully.

        Room Type: {booking.room_type}
        Check-in: {booking.checkin}
        Check-out: {booking.checkout}
        People: {booking.people}

        Thank you for booking with our hotel.
        """,
        settings.EMAIL_HOST_USER,
        [booking.email],
        fail_silently=False,
    )

    return redirect("Rooms_Booking")


def reject_booking(request, id):

    booking = get_object_or_404(
        Booking_Room,
        id=id
    )

    return render(
        request,
        "admin/reject_booking.html",
        {
            "booking": booking
        }
    )


def reject_booking_submit(request, id):

    booking = get_object_or_404(
        Booking_Room,
        id=id
    )

    if request.method == "POST":

        reason = request.POST.get("reason")

        booking.status = "Rejected"
        booking.reject_reason = reason
        booking.save()

        send_mail(
            "Room Booking Rejected",
            f"""
            Hello {booking.name},

            We are sorry.

            Your room booking has been rejected.

            Reason:
            {reason}

            Thank you.
            """,
                        settings.EMAIL_HOST_USER,
                        [booking.email],
                        fail_silently=False,
                    )

    return redirect("Rooms_Booking")



def Rooms(request):

    data = add_rooms_view.objects.all()

    for i in data:

        booking_count = Booking_Room.objects.filter(
            room=i,
            status__in=["Pending", "Confirmed"]
        ).count()

        i.is_available = booking_count < 10

    return render(request, "admin/Rooms.html", {
        "data": data
    })


# --- DELETE ROOM ---
def del_Room(request, id):
    room = get_object_or_404(add_rooms_view, id=id)
    room.delete()
    return redirect('Add_Rooms')

def edit_Room(request, id):
    room = get_object_or_404(add_rooms_view, id=id)

    if request.method == "POST":
        room.Roomtype = request.POST.get('Roomtype')
        room.address = request.POST.get('address')
        room.Price = request.POST.get("Price")
        room.room_number = request.POST.get("room_number")

        # Images ko tabhi update karein jab nayi image select ki gayi ho
        if request.FILES.get('image'):
            room.image = request.FILES.get('image')
        if request.FILES.get('image2'):
            room.image2 = request.FILES.get('image2')
        if request.FILES.get('image3'):
            room.image3 = request.FILES.get('image3')

        room.save()  # Database me save karein
        return redirect('Add_Rooms') # Save hone ke baad list page par redirect karein

    return render(request, 'admin/edit_Room.html', {'room': room})



# *************************************************

# ********************* CAR BOOKING ************************************
# Function ka naam 'single_page_car_booking' ki jagah 'car_service' karein


# =========================================================
# SEND OTP
# =========================================================

@require_POST
def send_otp(request):

    try:

        data = json.loads(request.body)

        room_number = data.get(
            "room_number",
            ""
        ).strip()

        phone_number = data.get(
            "phone_number",
            ""
        ).strip()


        # =================================================
        # ROOM NUMBER CHECK
        # =================================================

        if not room_number:

            return JsonResponse({
                "success": False,
                "error": "Room number enter karo."
            }, status=400)


        # =================================================
        # MOBILE NUMBER CHECK
        # =================================================

        if (
            not phone_number.isdigit()
            or len(phone_number) != 10
            or phone_number[0] not in "6789"
        ):

            return JsonResponse({
                "success": False,
                "error": "Valid 10 digit mobile number enter karo."
            }, status=400)


        # =================================================
        # FIND ROOM
        # =================================================

        room = add_rooms_view.objects.filter(
            room_number=room_number
        ).first()


        if not room:

            return JsonResponse({
                "success": False,
                "error": "Ye room number exist nahi karta."
            })


        # =================================================
        # FIND ROOM BOOKING
        # =================================================

        room_booking = Booking_Room.objects.filter(
            room=room
        ).order_by("-id").first()


        if not room_booking:

            return JsonResponse({
                "success": False,
                "error": (
                    "Is room number ki koi room booking "
                    "nahi mili."
                )
            })


        # =================================================
        # REGISTERED MOBILE NUMBER CHECK
        # =================================================

        registered_phone = str(
            room_booking.phone
        ).strip()


        if registered_phone != phone_number:

            return JsonResponse({
                "success": False,
                "error": (
                    "Mobile number is room ke "
                    "registered mobile number se "
                    "match nahi karta."
                )
            })


        # =================================================
        # GENERATE 6 DIGIT OTP
        # =================================================

        otp = str(
            random.randint(
                100000,
                999999
            )
        )


        # =================================================
        # SAVE OTP FOR 2 MINUTES
        # =================================================

        cache.set(
            f"booking_otp_{phone_number}",
            otp,
            timeout=120
        )


        # =================================================
        # TESTING OTP
        # OTP TERMINAL ME DIKHEGA
        # =================================================

        print()
        print("=" * 60)
        print("             CAR BOOKING OTP")
        print("=" * 60)
        print("Room Number  :", room_number)
        print("Mobile Number:", phone_number)
        print("OTP          :", otp)
        print("Valid Time   : 2 Minutes")
        print("=" * 60)
        print()


        # =================================================
        # RESPONSE
        # =================================================

        return JsonResponse({

            "success": True,

            "message": (
                "Mobile number verified with room booking. "
                "OTP generated successfully."
            )

        })


    except Exception as e:

        print(
            "SEND OTP ERROR:",
            e
        )

        return JsonResponse({

            "success": False,

            "error": str(e)

        }, status=500)


# =========================================================
# VERIFY OTP
# =========================================================

@require_POST
def verify_otp(request):

    try:

        data = json.loads(request.body)


        phone_number = data.get(
            "phone_number",
            ""
        ).strip()


        otp = data.get(
            "otp",
            ""
        ).strip()


        # =================================================
        # CHECK DATA
        # =================================================

        if not phone_number or not otp:

            return JsonResponse({

                "success": False,

                "error":
                    "Mobile number aur OTP required hai."

            }, status=400)


        # =================================================
        # GET SAVED OTP
        # =================================================

        saved_otp = cache.get(

            f"booking_otp_{phone_number}"

        )


        # =================================================
        # OTP EXPIRED
        # =================================================

        if saved_otp is None:

            return JsonResponse({

                "success": False,

                "error":
                    "OTP expire ho gaya. Dobara OTP send karo."

            })


        # =================================================
        # WRONG OTP
        # =================================================

        if str(saved_otp) != str(otp):

            return JsonResponse({

                "success": False,

                "error":
                    "Wrong OTP."

            })


        # =================================================
        # CORRECT OTP
        # =================================================

        cache.delete(

            f"booking_otp_{phone_number}"

        )


        # =================================================
        # SAVE OTP VERIFICATION IN SESSION
        # =================================================

        request.session[
            f"otp_verified_{phone_number}"
        ] = True


        # =================================================
        # SUCCESS RESPONSE
        # =================================================

        return JsonResponse({

            "success": True,

            "message":
                "Mobile number verified successfully."

        })


    except Exception as e:

        print(
            "VERIFY OTP ERROR:",
            e
        )

        return JsonResponse({

            "success": False,

            "error": str(e)

        }, status=500)


# =========================================================
# CAR SERVICE
# =========================================================

def car_service(request):

    success_booking = None


    # =====================================================
    # POST REQUEST
    # =====================================================

    if request.method == "POST":


        # =================================================
        # COMMON FORM DATA
        # =================================================

        room_number = request.POST.get(
            "room_number",
            ""
        ).strip()


        full_name = request.POST.get(
            "full_name",
            ""
        ).strip()


        car_capacity = request.POST.get(
            "car_capacity",
            ""
        )


        selected_places = request.POST.get(
            "selected_places_hidden",
            ""
        )


        booking_date = request.POST.get(
            "booking_date",
            ""
        )


        booking_time = request.POST.get(
            "booking_time",
            ""
        )


        estimated_km = request.POST.get(
            "estimated_km_hidden",
            ""
        )


        total_amount = request.POST.get(
            "total_amount_hidden",
            ""
        )


        phone_number = request.POST.get(
            "phone_number",
            ""
        ).strip()


        action = request.POST.get(
            "action_type",
            ""
        )


        # =================================================
        # CASE 1
        # NEW CAR BOOKING
        # =================================================

        if action == "book":


            # =============================================
            # MOBILE NUMBER VALIDATION
            # =============================================

            if (
                not phone_number.isdigit()
                or len(phone_number) != 10
                or phone_number[0] not in "6789"
            ):

                return render(

                    request,

                    "car_service.html",

                    {
                        "error_message":
                            "Valid mobile number enter karo."
                    }

                )


            # =============================================
            # ROOM NUMBER CHECK
            # =============================================

            if not room_number:

                return render(

                    request,

                    "car_service.html",

                    {
                        "error_message":
                            "Room number enter karo."
                    }

                )


            # =============================================
            # FIND ROOM
            # =============================================

            room = add_rooms_view.objects.filter(

                room_number=room_number

            ).first()


            if not room:

                return render(

                    request,

                    "car_service.html",

                    {
                        "error_message":
                            "Ye room number exist nahi karta."
                    }

                )


            # =============================================
            # FIND ROOM BOOKING
            # =============================================

            room_booking = Booking_Room.objects.filter(

                room=room

            ).order_by("-id").first()


            if not room_booking:

                return render(

                    request,

                    "car_service.html",

                    {
                        "error_message":
                            "Is room ki booking nahi mili."
                    }

                )


            # =============================================
            # REGISTERED MOBILE CHECK
            # =============================================

            registered_phone = str(

                room_booking.phone

            ).strip()


            if registered_phone != phone_number:

                return render(

                    request,

                    "car_service.html",

                    {
                        "error_message": (
                            "Mobile number room booking "
                            "ke mobile number se "
                            "match nahi karta."
                        )
                    }

                )


            # =============================================
            # OTP VERIFICATION CHECK
            # =============================================

            otp_verified = request.session.get(

                f"otp_verified_{phone_number}",

                False

            )


            if not otp_verified:

                return render(

                    request,

                    "car_service.html",

                    {
                        "error_message": (
                            "Booking se pehle "
                            "mobile OTP verify karo."
                        )
                    }

                )


            # =============================================
            # CREATE CAR BOOKING
            # =============================================

            booking = CarBooking.objects.create(

                room_number=room_number,

                full_name=full_name,

                car_capacity=car_capacity,

                selected_places=selected_places,

                booking_date=booking_date,

                booking_time=booking_time,

                estimated_km=(
                    float(estimated_km)
                    if estimated_km
                    else 0.0
                ),

                total_amount=(
                    float(total_amount)
                    if total_amount
                    else 500.0
                ),

                phone_number=phone_number,

                is_paid=False

            )


            # =============================================
            # OTP VERIFICATION REMOVE
            # =============================================

            request.session.pop(

                f"otp_verified_{phone_number}",

                None

            )


            # =============================================
            # SHOW QR PAYMENT
            # =============================================

            return render(

                request,

                "car_service.html",

                {

                    "booking":
                        booking,

                    "show_qr":
                        True

                }

            )


        # =================================================
        # CASE 2
        # PAYMENT CONFIRM
        # =================================================

        elif action == "pay_confirm":


            booking_id = request.POST.get(

                "booking_id"

            )


            # =============================================
            # CHECK BOOKING ID
            # =============================================

            if not booking_id:

                return render(

                    request,

                    "car_service.html",

                    {
                        "error_message":
                            "Booking ID nahi mila."
                    }

                )


            try:


                # =========================================
                # FIND CAR BOOKING
                # =========================================

                booking = CarBooking.objects.get(

                    id=booking_id

                )


                # =========================================
                # PAYMENT STATUS
                # =========================================

                booking.is_paid = True

                booking.save()


                # =========================================
                # SUCCESS BOOKING
                # =========================================

                success_booking = booking


                # =========================================
                # FIND ROOM
                # =========================================

                room = add_rooms_view.objects.filter(

                    room_number=booking.room_number

                ).first()


                room_booking = None


                if room:

                    room_booking = Booking_Room.objects.filter(

                        room=room

                    ).order_by("-id").first()


                # =========================================
                # SEND EMAIL
                # =========================================

                if (
                    room_booking
                    and room_booking.email
                ):


                    send_mail(

                        "Your Car Booking is Successful",


                        f"""
Hello {booking.full_name},

Your car booking has been successfully confirmed.

----------------------------------------
CAR BOOKING DETAILS
----------------------------------------

Booking ID:
{booking.id}

Room Number:
{booking.room_number}

Mobile Number:
{booking.phone_number}

Car Capacity:
{booking.car_capacity}

Booking Date:
{booking.booking_date}

Booking Time:
{booking.booking_time}

Selected Places:
{booking.selected_places}

Estimated Distance:
{booking.estimated_km} KM

Total Amount:
₹{booking.total_amount}

Payment Status:
PAID

----------------------------------------

Thank you for choosing our hotel service.

Hotel Management
""",

                        settings.DEFAULT_FROM_EMAIL,

                        [room_booking.email],

                        fail_silently=False

                    )


                    # =====================================
                    # TERMINAL MESSAGE
                    # =====================================

                    print()

                    print(
                        "=" * 60
                    )

                    print(
                        "CAR BOOKING EMAIL SENT"
                    )

                    print(
                        "Email:",
                        room_booking.email
                    )

                    print(
                        "Booking ID:",
                        booking.id
                    )

                    print(
                        "=" * 60
                    )

                    print()


            except CarBooking.DoesNotExist:

                return render(

                    request,

                    "car_service.html",

                    {
                        "error_message":
                            "Car booking nahi mili."
                    }

                )


            except Exception as e:

                print(
                    "PAYMENT/EMAIL ERROR:",
                    e
                )

                return render(

                    request,

                    "car_service.html",

                    {
                        "error_message":
                            f"Payment process error: {e}"
                    }

                )


    # =====================================================
    # FINAL RESPONSE
    # =====================================================

    return render(

        request,

        "car_service.html",

        {
            "success_booking":
                success_booking
        }

    )


# **********************************************************
# ********************* END CAR BOOKING ********************
# **********************************************************

def Bookd_Services(request):
    car_bookings = CarBooking.objects.all().order_by('-id')

    return render(
        request,
        'admin/Bookd_services.html',
        {
            'car_bookings': car_bookings
        }
    )

def delete_car_booking(request, booking_id):

    booking = get_object_or_404(
        CarBooking,
        id=booking_id
    )

    booking.delete()

    return redirect('Bookd_Services')


# ################################################################

def Problems(request):
    problems = Problem.objects.all().order_by('-id')

    return render(request, 'admin/Problems.html', {
        'problems': problems
    })


def DeleteProblem(request, id):
    problem = get_object_or_404(Problem, id=id)
    problem.delete()

    return redirect('Problems')


def AnswerProblem(request, id):
    problem = get_object_or_404(Problem, id=id)

    if request.method == "POST":
        answer = request.POST.get("answer")

        problem.answer = answer
        problem.save()

        return redirect('Problems')

    return render(request, 'admin/answer_problem.html', {
        'problem': problem
    })

