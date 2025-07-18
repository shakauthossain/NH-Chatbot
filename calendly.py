from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from UUID import uuid
import os


def schedule_event(access_token, refresh_token, summary, description, start_dt, end_dt, user_email, guest_emails):
    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        scopes=["https://www.googleapis.com/auth/calendar"]
    )

    service = build("calendar", "v3", credentials=creds)

    attendees = [{"email": user_email}]
    if guest_emails:
        attendees += [{"email": guest} for guest in guest_emails]

    event = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": start_dt, "timeZone": "Asia/Dhaka"},
        "end": {"dateTime": end_dt, "timeZone": "Asia/Dhaka"},
        "attendees": attendees,
        "conferenceData": {
            "createRequest": {
                "requestId": str(uuid.uuid4()),
                "conferenceSolutionKey": {"type": "hangoutsMeet"}
            }
        }
    }

    event_result = service.events().insert(
        calendarId='primary',
        body=event,
        conferenceDataVersion=1,
        sendUpdates="all"
    ).execute()

    return {
        "event_link": event_result.get("htmlLink"),
        "meet_link": event_result.get("conferenceData", {}).get("entryPoints", [{}])[0].get("uri")
    }