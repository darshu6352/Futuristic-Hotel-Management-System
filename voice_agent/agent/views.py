import os
import json
import time

from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from google import genai


client = genai.Client(
    api_key=os.environ.get("GEMINI_API_KEY")
)


def home(request):
    return render(request, "agent/index.html")


@csrf_exempt
def chat(request):

    if request.method != "POST":
        return JsonResponse({
            "success": False,
            "error": "Only POST request allowed"
        })


    try:

        data = json.loads(request.body)

        user_message = data.get("message", "").strip()


        if not user_message:
            return JsonResponse({
                "success": False,
                "error": "Message empty hai"
            }, status=400)


        prompt = f"""
Tum ek helpful Hindi AI voice assistant ho.

User ne kaha:
{user_message}

Simple, natural aur short Hindi mein jawab do.
Voice assistant ki tarah friendly jawab do.
"""


        # Gemini request
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt
        )


        return JsonResponse({
            "success": True,
            "reply": response.text
        })


    except Exception as e:

        print("GEMINI ERROR:", e)

        return JsonResponse({
            "success": False,
            "error": str(e)
        }, status=500)