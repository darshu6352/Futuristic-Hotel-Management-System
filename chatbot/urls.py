from django.urls import path

from .views import test_ai, chat, get_available_rooms, gemini_test


urlpatterns = [

    path("test-ai/", test_ai, name="test_ai"),

    path("chat/", chat, name="chat"),

    path("available-rooms/", get_available_rooms, name="available_rooms"),

    path("gemini-test/", gemini_test, name="gemini_test"),

]