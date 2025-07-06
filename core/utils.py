import os
import json
import re
import requests
from datetime import datetime, timedelta

import gspread
from google.oauth2.service_account import Credentials


# Load .env early
from dotenv import load_dotenv
load_dotenv()

# Your Gemini helper
def query_gemini(text):
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    headers = {
        'Content-Type': 'application/json',
        'X-goog-api-key': os.getenv("GEMINI_API_KEY")
    }
    data = {
        "contents": [
            {
                "parts": [
                    {
                        "text": f"Extract JSON keys name,phone,start_time,end_time,hourly_rate,advance,bottle_amount,cash_received, pitch . If any key is not present just put 0 in that:\n\n{text}"
                    }
                ]
            }
        ]
    }
    return requests.post(url, headers=headers, json=data)

service_account_str = os.getenv("SERVICE_ACCOUNT")
if not service_account_str:
    raise ValueError("SERVICE_ACCOUNT environment variable not set or empty")

try:
    service_account_info = json.loads(service_account_str)
except json.JSONDecodeError as e:
    raise ValueError(f"Failed to decode SERVICE_ACCOUNT JSON: {e}")


SENSITIVE_SERVICE = service_account_info
GOOGLE_SHEET_NAME = "June - 2025"

# Sheets setup
creds = Credentials.from_service_account_info(
    SENSITIVE_SERVICE,
    scopes=["https://www.googleapis.com/auth/spreadsheets"]
)
gc = gspread.authorize(creds)
sheet = gc.open_by_key(os.getenv("GOOGLE_SHEET_ID")).worksheet(GOOGLE_SHEET_NAME)


def process_booking(data):
    text = data
    # 1. Gemini call
    resp = query_gemini(text)
    if resp.status_code != 200:
        print(resp.text)
        raise ValueError("Gemini call")
    
    # The response from gemini-2.0-flash is different
    # It's in resp.json()['candidates'][0]['content']['parts'][0]['text']
    # And it might be wrapped in ```json ... ```
    raw_content = resp.json()['candidates'][0]['content']['parts'][0]['text']
    
    # Use regex to robustly extract content within ```json ... ```
    match = re.search(r"```(json)?(.*)```", raw_content, re.DOTALL)
    if match:
        # Extract the content from the second group, which is the JSON part
        clean_content = match.group(2).strip()
    else:
        # If no match, assume the whole string is the content
        clean_content = raw_content.strip()
        
    parsed = json.loads(clean_content)
    
    # Ensure hourly_rate is a float for DB insertion
    if 'hourly_rate' in parsed:
        parsed['hourly_rate'] = int(parsed['hourly_rate'])

    # 3. Google Sheet
    start_time_str = parsed.get('start_time', '00:00')
    end_time_str = parsed.get('end_time', '00:00')
    rate_per_hour = int(parsed.get('hourly_rate', 0))

    time_format = "%H:%M"
    start_time = datetime.strptime(start_time_str, time_format)
    end_time = datetime.strptime(end_time_str, time_format)

    if end_time < start_time:
        end_time += timedelta(days=1)

    duration = end_time - start_time
    duration_in_hours = duration.total_seconds() / 3600
    total_amount = duration_in_hours * rate_per_hour
    if "bottle_amount" in parsed:
        total_amount += int(parsed.get("bottle_amount", 0))
    
    parsed['duration'] = str(duration)
    parsed['duration_in_hours'] = int(duration_in_hours)


    time_slot = f"{start_time_str} - {end_time_str}"
    note = f"Name: {parsed.get('name', '')}, Phone: {parsed.get('phone', '')}"

    date_str = datetime.now().strftime("%d/%m/%Y")
    parsed['note'] = note
    parsed['date_str'] = date_str
    parsed['time_slot'] = time_slot
    parsed['total_amount'] = total_amount
    
    add_booking_to_sheet(parsed)
    return parsed


def add_booking_to_sheet(data):
    sheet.append_row([
        data.get("date_str"),  # date
        data.get("time_slot"), # time slot 
        data.get("rate_per_hour"), # rate per hour
        data.get("advance"),  # Advance
        data.get("cash"),  # Cash Recived
        data.get("bottle_amount"),  # Bottles amount
        0,  # Extra time (using this for duration)
        0,  # Extra time Amount
        data.get("total_amount"),  # Total
        data.get("note"),
    ])





def find_and_validate_court(booking):
    from .models import Court, Booking

    # Find active cricket courts
    cricket_courts = Court.objects.filter(name__icontains="cricket", is_active=True)

    for court in cricket_courts:
        conflicting_bookings = Booking.objects.filter(
            court=court,
            booking_date=booking.booking_date,
            start_time__lt=booking.end_time,
            end_time__gt=booking.start_time,
        )
        # If updating an existing booking, exclude it from the conflict check
        if booking.pk:
            conflicting_bookings = conflicting_bookings.exclude(pk=booking.pk)

        if not conflicting_bookings.exists():
            # Found an available cricket court
            return court

    # If no court is found after checking all cricket courts
    raise ValueError("No available cricket courts for the selected time slot.")
