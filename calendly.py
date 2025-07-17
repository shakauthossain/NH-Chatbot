import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
import pytz

router = APIRouter()

CALENDLY_HOST_URL = "https://api.calendly.com/users/me"
EVENT_NAME = "Service Inquiry Notionhive"
DEFAULT_TIMEZONE = "Asia/Dhaka"

HEADERS = {
    "Authorization": f"Bearer {calendly_api_key}",
    "Content-Type": "application/json"
}

# Pydantic model for incoming chatbot data
class ScheduleMeetingRequest(BaseModel):
    date: str  # Format: MM DD, YYYY
    time: str  # Format: HH.MM am/pm
    user_name: str
    user_email: EmailStr
    guest_email: Optional[EmailStr] = None
    details: Optional[str] = ""

@router.post("/calendly/schedule")
def schedule_meeting(req: ScheduleMeetingRequest):
    try:
        # Combine and parse date + time
        combined_str = f"{req.date} {req.time}"
        dt_naive = datetime.strptime(combined_str, "%m %d, %Y %I.%M %p")
        tz = pytz.timezone(DEFAULT_TIMEZONE)
        dt_aware = tz.localize(dt_naive)
        start_time_iso = dt_aware.isoformat()

    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid date/time format")

    payload = {
        "event_type": "https://calendly.com/shakaut-notionhive/service-inquiry-notionhive",
        "host": CALENDLY_HOST_URL,
        "duration": 30,
        "timezone": DEFAULT_TIMEZONE,
        "date_setting": {
            "type": "single_start_time",
            "start_time": start_time_iso
        },
        "location": {
            "kind": "physical",
            "location": "Virtual",
            "additonal_info": req.details
        },
        "invitees": [
            {
                "email": req.user_email,
                "name": req.user_name
            }
        ]
    }

    # Optional co-host if guest email provided
    if req.guest_email:
        payload["co_hosts"] = [f"https://api.calendly.com/users/{req.guest_email}"]

    response = requests.post(
        "https://api.calendly.com/one_off_event_types",
        headers=HEADERS,
        json=payload
    )

    if response.status_code != 201:
        raise HTTPException(status_code=response.status_code, detail=response.text)

    data = response.json()
    return {
        "message": "Meeting scheduled successfully.",
        "booking_url": data["resource"]["scheduling_url"]  # or "booking_url"
    }
