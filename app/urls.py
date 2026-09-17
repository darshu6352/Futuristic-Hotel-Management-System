from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path
from . import views
from django.urls import path, include


urlpatterns = [
    path('', views.home, name="home"),
    path('RoomsBook/', views.RoomsBook, name="RoomsBook"),
    path('problems/', views.problems, name="problems"),
    path('Room_Bookd/', views.Room_Bookd, name="Room_Bookd"),
    path('car_service/', views.car_service, name="car_service"),
    path('register/', views.register, name="register"),
    path('login/', views.login, name="login"),
    path("chatbot/", include("chatbot.urls")),
    path("car-service/", views.car_service, name="car_service"),
    path("send-otp/", views.send_otp, name="send_otp"),
    path("verify-otp/", views.verify_otp, name="verify_otp"),
    


    #**************************adminsite***************************** 
    
    path('Deshbord/',views.Deshbord, name="Deshbord"),
    
    path('Rooms/',views.Rooms, name="Doctor"),
    path('Add_Rooms/',views.Add_Rooms, name="Add_Rooms"),
    path('edit-room/<int:id>/', views.edit_Room, name="edit_Room"),
    path('delete-room/<int:id>/', views.del_Room, name="del_Room"),


    path('Rooms_Booking/',views.Rooms_Booking, name="Rooms_Booking"),
    path("payment-qr/", views.payment_qr, name="payment_qr"),
    path("payment-done/", views.payment_done, name="payment_done"),


    path("Bookd_Services/", views.Bookd_Services, name="Bookd_Services"),
    path('Bookd_Services/delete/<int:booking_id>/',views.delete_car_booking,name='delete_car_booking'),



    path('Problems/', views.Problems, name='Problems'),
    path('Problems/delete/<int:id>/',views.DeleteProblem,name='DeleteProblem'),
    path('Problems/answer/<int:id>/',views.AnswerProblem, name='AnswerProblem'),


    path("confirm-booking/<int:id>/",views.confirm_booking, name="confirm_booking"),
    path("reject-booking/<int:id>/",views.reject_booking, name="reject_booking"),

    path("confirm-booking/<int:id>/",views.confirm_booking,name="confirm_booking"),
    path("reject-booking/<int:id>/",views.reject_booking,name="reject_booking"),
    path("reject-booking-submit/<int:id>/",views.reject_booking_submit,name="reject_booking_submit"),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
