import requests
import json
import re
import os

from datetime import datetime, timedelta

from django.http import JsonResponse
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail

from app.models import add_rooms_view, Booking_Room
from google import genai


# =========================================================
# GEMINI HELPER
# =========================================================

def ask_gemini(prompt):

    client = genai.Client(
        api_key=os.environ.get("GEMINI_API_KEY")
    )

    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt
    )

    return response.text.strip()


# =========================================================
# TEST AI - OLLAMA
# =========================================================

def test_ai(request):

    rooms = add_rooms_view.objects.all()

    room_data = []

    for room in rooms:

        room_data.append({
            "room_number": room.room_number,
            "room_type": room.Roomtype,
            "price": str(room.Price),
            "facilities": room.facilities
        })

    prompt = f"""
You are an AI assistant for a hotel management system.

Hotel rooms:

{json.dumps(room_data, indent=2)}

Rules:

- Use only the database information.
- Do not invent information.
- Prices are in Indian Rupees (₹).
- Give short and helpful answers.

User question:

How many rooms are available?
"""

    try:

        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3.2:3b",
                "prompt": prompt,
                "stream": False
            },
            timeout=120
        )

        response.raise_for_status()

        data = response.json()

        answer = data.get(
            "response",
            "AI response nahi mila."
        )

        return JsonResponse({
            "answer": answer.strip().strip('"')
        })

    except Exception as e:

        return JsonResponse({
            "error": "AI response generate nahi ho paya.",
            "details": str(e)
        })


# =========================================================
# DATE PARSER
# =========================================================

def parse_user_date(text):

    text = text.strip()

    date_formats = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%d %B %Y",
        "%d %b %Y",
        "%d %B",
        "%d %b",
    ]

    for date_format in date_formats:

        try:

            parsed_date = datetime.strptime(
                text,
                date_format
            ).date()

            # Agar year nahi diya hai
            if "%Y" not in date_format:

                today = timezone.localdate()

                parsed_date = parsed_date.replace(
                    year=today.year
                )

            return parsed_date

        except ValueError:

            continue

    return None


# =========================================================
# CANCELLATION HELPER
# =========================================================

def start_cancellation(request):

    request.session["cancel_booking"] = {

        "step": "room_number",

        "room_number": "",

        "name": "",

        "email": "",

        "phone": "",

        "checkin": "",

        "checkout": "",

        "reason": "",

        "booking_id": None
    }

    request.session.modified = True


# =========================================================
# MAIN CHATBOT
# =========================================================

def chat(request):

    user_message = request.GET.get(
        "message",
        ""
    ).strip()

    if not user_message:

        return JsonResponse({
            "error": "Message required."
        })

    today = timezone.localdate()

    message_lower = user_message.lower()


    # =====================================================
    # CHECK EXISTING CANCELLATION SESSION
    # =====================================================

    cancel_data = request.session.get(
        "cancel_booking"
    )


    # =====================================================
    # START CANCELLATION
    # =====================================================

    cancellation_keywords = [

        "cancel booking",

        "cancel my booking",

        "cancel room",

        "booking cancel",

        "room cancel",

        "cancel"
    ]


    # Only start new cancellation if there is
    # no existing cancellation process.

    if (
        cancel_data is None
        and any(
            keyword in message_lower
            for keyword in cancellation_keywords
        )
    ):

        start_cancellation(request)

        return JsonResponse({

            "answer": (
                "Sure 👍 Let's verify your booking first.\n\n"
                "Please enter your room number."
            ),

            "cancellation": True,

            "step": "room_number"
        })


    # =====================================================
    # CANCELLATION PROCESS
    # =====================================================

    if cancel_data:

        step = cancel_data.get("step")


        # =================================================
        # STEP 1 - ROOM NUMBER
        # =================================================

        if step == "room_number":

            room_match = re.fullmatch(

                r"\s*(?:room\s*)?(\d{3,4})\s*",

                user_message,

                re.IGNORECASE
            )


            if not room_match:

                return JsonResponse({

                    "answer": (
                        "Please enter a valid room number.\n"
                        "Example: 101"
                    ),

                    "cancellation": True,

                    "step": "room_number"
                })


            room_number = room_match.group(1)


            # Check whether room exists

            room = add_rooms_view.objects.filter(

                room_number=room_number

            ).first()


            if not room:

                return JsonResponse({

                    "answer": (

                        f"❌ Room {room_number} was not found "
                        "in the hotel database.\n\n"

                        "Please enter a valid room number."
                    ),

                    "cancellation": True,

                    "step": "room_number"
                })


            cancel_data["room_number"] = room_number

            cancel_data["step"] = "name"

            request.session["cancel_booking"] = cancel_data

            request.session.modified = True


            return JsonResponse({

                "answer": (

                    f"Room {room_number} found. 👍\n\n"

                    "Please enter the name used for the booking."
                ),

                "cancellation": True,

                "step": "name"
            })


        # =================================================
        # STEP 2 - NAME
        # =================================================

        elif step == "name":

            name = user_message.strip()


            if len(name) < 2:

                return JsonResponse({

                    "answer": "Please enter a valid name.",

                    "cancellation": True,

                    "step": "name"
                })


            cancel_data["name"] = name

            cancel_data["step"] = "email"

            request.session["cancel_booking"] = cancel_data

            request.session.modified = True


            return JsonResponse({

                "answer": (

                    "Thank you. 👍\n\n"

                    "Please enter the email address "
                    "used for the booking."
                ),

                "cancellation": True,

                "step": "email"
            })


        # =================================================
        # STEP 3 - EMAIL
        # =================================================

        elif step == "email":

            email = user_message.strip().lower()


            email_pattern = (

                r"^[A-Za-z0-9._%+-]+@"
                r"[A-Za-z0-9.-]+\."
                r"[A-Za-z]{2,}$"
            )


            if not re.fullmatch(

                email_pattern,

                email
            ):

                return JsonResponse({

                    "answer": (

                        "❌ Please enter a valid email address.\n"

                        "Example: example@gmail.com"
                    ),

                    "cancellation": True,

                    "step": "email"
                })


            cancel_data["email"] = email

            cancel_data["step"] = "phone"

            request.session["cancel_booking"] = cancel_data

            request.session.modified = True


            return JsonResponse({

                "answer": (

                    "Email verified. 👍\n\n"

                    "Please enter the 10-digit phone number "
                    "used for the booking."
                ),

                "cancellation": True,

                "step": "phone"
            })


        # =================================================
        # STEP 4 - PHONE
        # =================================================

        elif step == "phone":

            phone = re.sub(

                r"\D",

                "",

                user_message
            )


            if not re.fullmatch(

                r"\d{10}",

                phone
            ):

                return JsonResponse({

                    "answer": (

                        "❌ Please enter a valid "
                        "10-digit phone number."
                    ),

                    "cancellation": True,

                    "step": "phone"
                })


            cancel_data["phone"] = phone

            cancel_data["step"] = "checkin"

            request.session["cancel_booking"] = cancel_data

            request.session.modified = True


            return JsonResponse({

                "answer": (

                    "Phone number verified. 👍\n\n"

                    "Please enter your check-in date.\n\n"

                    "Example: 2026-09-06"
                ),

                "cancellation": True,

                "step": "checkin"
            })


        # =================================================
        # STEP 5 - CHECK-IN
        # =================================================

        elif step == "checkin":

            checkin = parse_user_date(

                user_message
            )


            if not checkin:

                return JsonResponse({

                    "answer": (

                        "❌ Invalid date.\n\n"

                        "Please enter the check-in date "
                        "like: 2026-09-06"
                    ),

                    "cancellation": True,

                    "step": "checkin"
                })


            cancel_data["checkin"] = str(checkin)

            cancel_data["step"] = "checkout"

            request.session["cancel_booking"] = cancel_data

            request.session.modified = True


            return JsonResponse({

                "answer": (

                    f"Check-in date: {checkin}\n\n"

                    "Please enter your check-out date.\n\n"

                    "Example: 2026-09-08"
                ),

                "cancellation": True,

                "step": "checkout"
            })


        # =================================================
        # STEP 6 - CHECK-OUT
        # =================================================

        elif step == "checkout":

            checkout = parse_user_date(

                user_message
            )


            if not checkout:

                return JsonResponse({

                    "answer": (

                        "❌ Invalid date.\n\n"

                        "Please enter the check-out date "
                        "like: 2026-09-08"
                    ),

                    "cancellation": True,

                    "step": "checkout"
                })


            checkin = datetime.strptime(

                cancel_data["checkin"],

                "%Y-%m-%d"

            ).date()


            if checkout <= checkin:

                return JsonResponse({

                    "answer": (

                        "❌ Check-out date must be "
                        "after the check-in date.\n\n"

                        "Please enter the correct "
                        "check-out date."
                    ),

                    "cancellation": True,

                    "step": "checkout"
                })


            cancel_data["checkout"] = str(checkout)


            # =============================================
            # FIND ROOM
            # =============================================

            room_number = cancel_data["room_number"]


            room = add_rooms_view.objects.filter(

                room_number=room_number

            ).first()


            if not room:

                request.session.pop(

                    "cancel_booking",

                    None
                )

                return JsonResponse({

                    "answer": "❌ Room not found."
                })


            # =============================================
            # FIND ACTIVE BOOKING
            # =============================================

            booking = Booking_Room.objects.filter(

                room=room,

                name__iexact=cancel_data["name"],

                email__iexact=cancel_data["email"],

                phone=cancel_data["phone"],

                checkin=checkin,

                checkout=checkout,

                status__in=[

                    "Pending",

                    "Confirmed"
                ]

            ).first()


            # =============================================
            # BOOKING NOT FOUND
            # =============================================

            if not booking:

                request.session.pop(

                    "cancel_booking",

                    None
                )

                return JsonResponse({

                    "answer": (

                        "❌ Sorry, I could not find a "
                        "matching active booking.\n\n"

                        "Please check your:\n"

                        "• Room number\n"

                        "• Name\n"

                        "• Email\n"

                        "• Phone number\n"

                        "• Check-in date\n"

                        "• Check-out date"
                    ),

                    "cancellation": False
                })


            # =============================================
            # SAVE BOOKING ID
            # =============================================

            cancel_data["booking_id"] = booking.id

            cancel_data["step"] = "confirmation"

            request.session["cancel_booking"] = cancel_data

            request.session.modified = True


            # =============================================
            # ROOM DETAILS
            # =============================================

            price = booking.room.Price

            room_type = booking.room.Roomtype


            # =============================================
            # SHOW FINAL VERIFICATION
            # =============================================

            return JsonResponse({

                "answer": (

                    "🔍 Please verify your booking details:\n\n"

                    f"🏨 Room Number: "
                    f"{booking.room.room_number}\n"

                    f"🏷️ Room Type: "
                    f"{room_type}\n"

                    f"👤 Name: "
                    f"{booking.name}\n"

                    f"📧 Email: "
                    f"{booking.email}\n"

                    f"📱 Phone: "
                    f"{booking.phone}\n"

                    f"📅 Check-in: "
                    f"{booking.checkin}\n"

                    f"📅 Check-out: "
                    f"{booking.checkout}\n"

                    f"💰 Room Price: ₹{price}\n\n"

                    "Do you want to cancel this booking?\n\n"

                    "Please type YES or NO."
                ),

                "cancellation": True,

                "step": "confirmation",

                "booking": {

                    "room_number":
                        booking.room.room_number,

                    "room_type":
                        room_type,

                    "name":
                        booking.name,

                    "email":
                        booking.email,

                    "phone":
                        booking.phone,

                    "checkin":
                        str(booking.checkin),

                    "checkout":
                        str(booking.checkout),

                    "price":
                        str(price)
                }
            })


        # =================================================
        # STEP 7 - YES / NO
        # =================================================

        elif step == "confirmation":

            answer = message_lower.strip()


            # =============================================
            # NO
            # =============================================

            if answer in [

                "no",

                "n",

                "nope"
            ]:

                request.session.pop(

                    "cancel_booking",

                    None
                )


                return JsonResponse({

                    "answer": (

                        "Okay 👍 Your booking has "
                        "not been cancelled."
                    ),

                    "cancellation": False,

                    "step": "cancelled"
                })


            # =============================================
            # YES
            # =============================================

            elif answer in [

                "yes",

                "y",

                "yeah",

                "yep"
            ]:

                cancel_data["step"] = "reason"

                request.session["cancel_booking"] = cancel_data

                request.session.modified = True


                return JsonResponse({

                    "answer": (

                        "Please tell me the reason "
                        "for cancelling your booking."
                    ),

                    "cancellation": True,

                    "step": "reason"
                })


            # =============================================
            # INVALID YES / NO
            # =============================================

            else:

                return JsonResponse({

                    "answer": (

                        "Please confirm the cancellation "
                        "by typing YES or NO."
                    ),

                    "cancellation": True,

                    "step": "confirmation"
                })


        # =================================================
        # STEP 8 - REASON
        # =================================================

        elif step == "reason":

            reason = user_message.strip()


            if len(reason) < 3:

                return JsonResponse({

                    "answer": (

                        "Please provide a valid reason "
                        "for cancellation."
                    ),

                    "cancellation": True,

                    "step": "reason"
                })


            booking_id = cancel_data.get(

                "booking_id"
            )


            # =============================================
            # GET BOOKING AGAIN
            # =============================================

            booking = Booking_Room.objects.filter(

                id=booking_id,

                status__in=[

                    "Pending",

                    "Confirmed"
                ]

            ).first()


            if not booking:

                request.session.pop(

                    "cancel_booking",

                    None
                )

                return JsonResponse({

                    "answer": (

                        "❌ This booking could not be "
                        "cancelled because it is no longer "
                        "active."
                    ),

                    "cancellation": False
                })


            # =============================================
            # REJECT BOOKING = CANCEL
            # =============================================

            booking.status = "Rejected"

            booking.reject_reason = reason

            booking.save()


            # =============================================
            # SAVE DETAILS BEFORE CLEARING SESSION
            # =============================================

            room_number = booking.room.room_number

            checkin = booking.checkin

            checkout = booking.checkout

            price = booking.room.Price

            room_type = booking.room.Roomtype

            customer_name = booking.name

            customer_email = booking.email


            # =============================================
            # SEND CANCELLATION EMAIL
            # =============================================

            email_sent = False

            email_error = ""


            try:

                send_mail(

                    subject="Room Booking Cancelled - Hotel HOS",

                    message=f"""
Dear {customer_name},

Your room booking has been cancelled successfully.

Booking Details:
--------------------------------

Room Number: {room_number}

Room Type: {room_type}

Check-in: {checkin}

Check-out: {checkout}

Room Price: ₹{price}

Cancellation Reason:
{reason}

--------------------------------

Your refund has been initiated.

The refund amount will be credited to your account within 24 hours.

If you have any questions, please contact Hotel HOS.

Thank you,

Hotel HOS
""",

                    from_email=settings.DEFAULT_FROM_EMAIL,

                    recipient_list=[customer_email],

                    fail_silently=False
                )


                email_sent = True


                print(
                    "Cancellation email sent successfully."
                )


            except Exception as e:

                email_error = str(e)


                print(
                    "Cancellation email error:",
                    e
                )


            # =============================================
            # CLEAR SESSION
            # =============================================

            request.session.pop(

                "cancel_booking",

                None
            )

            request.session.modified = True


            # =============================================
            # FINAL SUCCESS RESPONSE
            # =============================================

            if email_sent:

                final_message = (

                    "✅ Your booking has been "
                    "cancelled successfully.\n\n"

                    f"🏨 Room Number: {room_number}\n"

                    f"🏷️ Room Type: {room_type}\n"

                    f"📅 Check-in: {checkin}\n"

                    f"📅 Check-out: {checkout}\n"

                    f"💰 Room Price: ₹{price}\n"

                    f"📝 Reason: {reason}\n\n"

                    f"📧 Cancellation confirmation "
                    f"has been sent to:\n"
                    f"{customer_email}\n\n"

                    "💰 Your refund has been initiated "
                    "and will be credited to your account "
                    "within 24 hours.\n\n"

                    "The room is now available again. 👍"
                )

            else:

                final_message = (

                    "✅ Your booking has been "
                    "cancelled successfully.\n\n"

                    f"🏨 Room Number: {room_number}\n"

                    f"🏷️ Room Type: {room_type}\n"

                    f"📅 Check-in: {checkin}\n"

                    f"📅 Check-out: {checkout}\n"

                    f"💰 Room Price: ₹{price}\n"

                    f"📝 Reason: {reason}\n\n"

                    "⚠️ Booking cancellation email "
                    "could not be sent.\n\n"

                    "Please contact Hotel HOS regarding "
                    "your refund.\n\n"

                    "The room is now available again. 👍"
                )


            # =============================================
            # FINAL JSON
            # =============================================

            return JsonResponse({

                "answer": final_message,

                "cancellation": True,

                "step": "completed",

                "booking_cancelled": True,

                "booking_id": booking.id,

                "room_number": room_number,

                "email_sent": email_sent
            })


        # =================================================
        # INVALID SESSION STEP
        # =================================================

        else:

            request.session.pop(

                "cancel_booking",

                None
            )

            return JsonResponse({

                "answer": (

                    "Cancellation process reset. "

                    "Please type 'cancel room' "
                    "to start again."
                ),

                "cancellation": False
            })


    # =====================================================
    # DATE DETECTION
    # =====================================================

    selected_date = None


    if "today" in message_lower:

        selected_date = today


    elif "tomorrow" in message_lower:

        selected_date = today + timedelta(days=1)


    else:

        date_match = re.search(

            r"\b(\d{1,2})\s+"

            r"(January|February|March|April|May|June|July|August|"
            r"September|October|November|December)"

            r"(?:\s+(\d{4}))?\b",

            user_message,

            re.IGNORECASE
        )


        if date_match:

            day = int(

                date_match.group(1)
            )

            month_name = date_match.group(2)

            year = date_match.group(3)


            if year:

                year = int(year)

            else:

                year = today.year


            try:

                selected_date = datetime.strptime(

                    f"{day} {month_name} {year}",

                    "%d %B %Y"

                ).date()


            except ValueError:

                selected_date = None


    if selected_date is None:

        selected_date = today


    # =====================================================
    # ROOM NUMBER DETECTION
    # =====================================================

    room_number = None


    room_match = re.search(

        r"\b(?:room\s*)?(\d{3,4})\b",

        message_lower
    )


    if room_match:

        room_number = room_match.group(1)


    # =====================================================
    # ROOM TYPE DETECTION
    # =====================================================

    room_type_filter = None


    if "deluxe" in message_lower:

        room_type_filter = "deluxe"


    elif "suite" in message_lower:

        room_type_filter = "suite"


    elif "single" in message_lower:

        room_type_filter = "single"


    elif "double" in message_lower:

        room_type_filter = "double"


    # =====================================================
    # ROOM DETAILS QUESTION
    # =====================================================

    detail_question = False


    detail_keywords = [

        "facility",

        "facilities",

        "amenities",

        "amenity",

        "price",

        "cost",

        "room details",

        "details",

        "information",

        "wifi",

        "wi-fi",

        "ac",

        "tv"
    ]


    for keyword in detail_keywords:

        if keyword in message_lower:

            detail_question = True

            break


    # =====================================================
    # GET ALL ROOMS
    # =====================================================

    rooms = add_rooms_view.objects.all()


    available_rooms = []

    room_details = []


    # =====================================================
    # PROCESS ROOMS
    # =====================================================

    for room in rooms:


        # -----------------------------------------------
        # Specific room number requested
        # -----------------------------------------------

        if room_number:

            if str(room.room_number) != room_number:

                continue


        # -----------------------------------------------
        # Room type filter
        # -----------------------------------------------

        if room_type_filter:

            if room.Roomtype.lower() != room_type_filter:

                continue


        # -----------------------------------------------
        # Room details
        # -----------------------------------------------

        room_details.append({

            "room_number": room.room_number,

            "room_type": room.Roomtype,

            "price": str(room.Price),

            "facilities": room.facilities
        })


        # -----------------------------------------------
        # Check booking availability
        # -----------------------------------------------

        booked = Booking_Room.objects.filter(

            room=room,

            status__in=[

                "Pending",

                "Confirmed"
            ],

            checkin__lte=selected_date,

            checkout__gt=selected_date

        ).exists()


        # -----------------------------------------------
        # Available room
        # -----------------------------------------------

        if not booked:

            available_rooms.append({

                "room_number": room.room_number,

                "room_type": room.Roomtype,

                "price": str(room.Price),

                "facilities": room.facilities
            })


    # =====================================================
    # DATA FOR AI
    # =====================================================

    available_room_data = json.dumps(

        available_rooms,

        indent=2
    )


    room_detail_data = json.dumps(

        room_details,

        indent=2
    )


    # =====================================================
    # ROOM DETAILS QUESTION
    # =====================================================

    if detail_question and room_number:


        if len(room_details) == 0:

            final_prompt = f"""

You are a hotel assistant.

User asked:

{user_message}

The requested room does not exist
in the hotel database.

Tell the user politely that
the room was not found.

Do not invent any information.

Keep the answer short.

"""


        else:

            final_prompt = f"""

You are a hotel assistant for a hotel management system.

User question:

{user_message}

Room requested:

{room_number}

ACTUAL DATABASE INFORMATION:

{room_detail_data}

STRICT RULES:

- Answer using ONLY the database information above.
- Do NOT invent facilities.
- Do NOT invent prices.
- Do NOT invent room information.
- Price is in Indian Rupees (₹).
- If the user asks for facilities, give the facilities field.
- If the user asks for price, give the price in ₹.
- If the user asks for room type, give the room type.
- Keep the answer short and natural.
- Do not talk about other rooms.

Answer the user's question directly.

"""


    # =====================================================
    # NO AVAILABLE ROOM
    # =====================================================

    elif len(available_rooms) == 0:

        final_prompt = f"""

You are a hotel assistant.

User question:

{user_message}

Requested date:

{selected_date}

The hotel database shows ZERO available rooms
matching the user's request.

Tell the user politely that no matching rooms
are available on this date.

Do not invent any rooms.

Do not invent any prices.

Keep the answer short.

"""


    # =====================================================
    # NORMAL ROOM AVAILABILITY
    # =====================================================

    else:

        final_prompt = f"""

You are a hotel assistant for a hotel management system.

User question:

{user_message}

Requested date:

{selected_date}

ACTUAL DATABASE RESULT:

Total available rooms:

{len(available_rooms)}

Available rooms:

{available_room_data}

STRICT RULES:

- These rooms are actually available in the database.
- You MUST say that rooms are available.
- NEVER say that these rooms are unavailable.
- NEVER say that there are zero rooms.
- Use ONLY the room numbers, room types, prices and facilities provided above.
- Do NOT invent any room.
- Do NOT invent any price.
- Do NOT invent any facility.
- Prices are in Indian Rupees (₹), not dollars.
- If the user asked for Deluxe rooms, mention only Deluxe rooms.
- If the user asked for Suite rooms, mention only Suite rooms.
- Mention the requested date.
- Give a short and natural answer.

Answer the user's question directly.

"""


    # =====================================================
    # CALL OLLAMA
    # =====================================================

    try:

        response = requests.post(

            "http://localhost:11434/api/generate",

            json={

                "model": "llama3.2:3b",

                "prompt": final_prompt,

                "stream": False

            },

            timeout=180
        )


        response.raise_for_status()


        ai_response = response.json()


        answer = ai_response.get(

            "response",

            "Sorry, answer generate nahi ho paya."
        )


        answer = answer.strip().strip('"')


    except Exception as e:

        return JsonResponse({

            "error": "AI response generate nahi ho paya.",

            "details": str(e)
        })


    # =====================================================
    # FINAL RESPONSE
    # =====================================================

    return JsonResponse({

        "answer": answer,

        "date": str(selected_date),

        "total_available": len(available_rooms),

        "available_rooms": available_rooms
    })


# =========================================================
# AVAILABLE ROOMS API
# =========================================================

def get_available_rooms(request):

    date_str = request.GET.get(

        "date",

        ""
    ).strip()


    # =====================================================
    # DATE
    # =====================================================

    if date_str:

        try:

            check_date = datetime.strptime(

                date_str,

                "%Y-%m-%d"

            ).date()


        except ValueError:

            return JsonResponse({

                "error": (
                    "Date format YYYY-MM-DD hona chahiye."
                )
            })

    else:

        check_date = timezone.localdate()


    # =====================================================
    # GET ROOMS
    # =====================================================

    rooms = add_rooms_view.objects.all()


    available_rooms = []


    # =====================================================
    # CHECK AVAILABILITY
    # =====================================================

    for room in rooms:

        booked = Booking_Room.objects.filter(

            room=room,

            status__in=[

                "Pending",

                "Confirmed"
            ],

            checkin__lte=check_date,

            checkout__gt=check_date

        ).exists()


        if not booked:

            available_rooms.append({

                "room_number": room.room_number,

                "room_type": room.Roomtype,

                "price": str(room.Price),

                "facilities": room.facilities
            })


    # =====================================================
    # RESPONSE
    # =====================================================

    return JsonResponse({

        "date": str(check_date),

        "available_rooms": available_rooms,

        "total_available": len(available_rooms)
    })


# =========================================================
# GEMINI TEST
# =========================================================

def gemini_test(request):

    try:

        answer = ask_gemini(

            "Say hello to my hotel chatbot in one short sentence."
        )


        return JsonResponse({

            "answer": answer
        })


    except Exception as e:

        return JsonResponse({

            "error": "Gemini response generate nahi ho paya.",

            "details": str(e)
        })