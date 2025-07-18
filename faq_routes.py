#Basic Packages
import io
import pandas as pd
import uuid
import traceback
from dotenv import load_dotenv
import os
import requests
from typing import List, Optional
from datetime import datetime, timedelta
import pytz
import json
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.discovery import build

#API Packages
from fastapi import APIRouter, UploadFile, File, HTTPException, Body, Path, Query
# from fastapi.responses import RedirectResponse

#FAQ CSV Validator Package
from pydantic import BaseModel, EmailStr

#Calling Functions from other py files
from faq_services import gemini_model, db, load_faqs, add_faq_to_csv, faq_path
from chatbot_prompt import generate_prompt

router = APIRouter()

load_dotenv()
CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
ACCESS_TOKEN = os.getenv("GOOGLE_ACCESS_TOKEN")
REFRESH_TOKEN = os.getenv("GOOGLE_REFRESH_TOKEN")
TIMEZONE = "Asia/Dhaka"

SCOPES = ['https://www.googleapis.com/auth/calendar']

# Data validation classes
class QuestionRequest(BaseModel):
    query: str

class FAQItem(BaseModel):
    question: str
    answer: str

# Meeting request model for Google Calendar
class MeetingRequest(BaseModel):
    date: str  # e.g. "2025-07-25"
    time: str  # e.g. "03:00 PM"
    user_email: EmailStr
    summary: str
    description: str
    guest_emails: Optional[List[EmailStr]] = None

# Chat endpoint API
@router.post("/ask")
async def ask_faq(request: QuestionRequest):
    query = request.query
    results = db.similarity_search(query, k=3)
    context = "\n\n".join([doc.page_content for doc in results])
    prompt = generate_prompt(context, query)

    try:
        response = gemini_model.generate_content(prompt)
        return {"answer": response.text.strip()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Add Single FAQ API
@router.post("/add_faq")
async def add_faq(faq: FAQItem):
    try:
        df = pd.read_csv(faq_path, encoding="utf-8")
        if ((df["prompt"] == faq.question) & (df["response"] == faq.answer)).any():
            raise HTTPException(status_code=400, detail="FAQ already exists.")
        new_df = pd.DataFrame([{"id": str(uuid.uuid4()), "prompt": faq.question, "response": faq.answer}])
        updated_df = pd.concat([df, new_df], ignore_index=True)
        updated_df.to_csv(faq_path, index=False, encoding="utf-8")
        global db
        db = load_faqs()
        return {"message": "FAQ added successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Upload CSV API
@router.post("/upload_faqs_csv")
async def upload_faqs_csv(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        return {
            "status": "error",
            "message": "Invalid file type",
            "error": "Only CSV files are supported."
        }

    try:
        contents = await file.read()
        df = pd.read_csv(io.BytesIO(contents))

        if "question" not in df.columns or "answer" not in df.columns:
            return {
                "status": "error",
                "message": "Invalid CSV structure",
                "error": "CSV must contain 'question' and 'answer' columns."
            }

        for _, row in df.iterrows():
            question = str(row["question"]).strip()
            answer = str(row["answer"]).strip()
            if question and answer:
                add_faq_to_csv(question, answer)

        global db
        db = load_faqs()

        return {
            "status": "success",
            "message": "FAQs uploaded and added successfully."
        }

    except Exception as e:
        traceback.print_exc()
        return {
            "status": "error",
            "message": "Failed to process CSV",
            "error": str(e)
        }

# Delete Single FAQ API
@router.delete("/delete_faq")
async def delete_faq(faq: FAQItem = Body(...)):
    try:
        df = pd.read_csv(faq_path, encoding="utf-8")
        filtered_df = df[~((df["prompt"] == faq.question) & (df["response"] == faq.answer))]
        if len(df) == len(filtered_df):
            raise HTTPException(status_code=404, detail="FAQ not found.")
        filtered_df.to_csv(faq_path, index=False, encoding="utf-8")
        global db
        db = load_faqs()
        return {"message": "FAQ deleted successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/deleted/{faq_id}")
async def delete_faq_by_id(faq_id: str = Path(...)):
    try:
        df = pd.read_csv(faq_path, encoding="utf-8")
        if "id" not in df.columns:
            raise HTTPException(status_code=500, detail="CSV does not contain 'id' column.")

        filtered_df = df[df["id"] != faq_id]
        if len(filtered_df) == len(df):
            raise HTTPException(status_code=404, detail="FAQ with given ID not found.")

        filtered_df.to_csv(faq_path, index=False, encoding="utf-8")
        global db
        db = load_faqs()
        return {"message": f"FAQ with ID {faq_id} deleted successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Delete All FAQs API
@router.delete("/delete/deleteall")
async def delete_all_faqs():
    try:
        pd.DataFrame(columns=["id", "prompt", "response"]).to_csv(faq_path, index=False, encoding="utf-8")
        global db
        db = load_faqs()
        return {"message": "All FAQs deleted successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Show All FAQs API
@router.get("/get_faqs")
async def get_faqs():
    try:
        df = pd.read_csv(faq_path, encoding="utf-8")
        df = df.astype(str)
        result = df.rename(columns={"prompt": "question", "response": "answer"}).to_dict(orient="records")
        return result
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="FAQ CSV file not found.")
    except pd.errors.ParserError as e:
        raise HTTPException(status_code=500, detail=f"CSV Parsing Error: {str(e)}")
    except UnicodeDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Encoding Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected Error: {str(e)}")

# Retrain DB
@router.post("/retrain")
async def retrain_db():
    try:
        global db
        db = load_faqs()
        return {"message": "Chatbot retrained successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/google-calendar/freebusy")
def get_busy_slots(
    start_date: str = Query(..., example="2025-07-20"),
    end_date: str = Query(..., example="2025-07-21")
):
    try:
        # Use stored credentials
        creds = Credentials(
            token=ACCESS_TOKEN,
            refresh_token=REFRESH_TOKEN,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            scopes=SCOPES,
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(GoogleRequest())

        service = build("calendar", "v3", credentials=creds)

        body = {
            "timeMin": f"{start_date}T00:00:00Z",
            "timeMax": f"{end_date}T23:59:59Z",
            "timeZone": TIMEZONE,
            "items": [{"id": "primary"}]
        }

        response = service.freebusy().query(body=body).execute()
        busy_slots = response["calendars"]["primary"]["busy"]

        return {"busy": busy_slots}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/google-calendar/schedule")
def schedule_meeting(req: MeetingRequest):
    try:
        # Build credentials using stored tokens
        creds = Credentials(
            token=ACCESS_TOKEN,
            refresh_token=REFRESH_TOKEN,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            scopes=SCOPES,
        )

        # Refresh token if expired
        if creds.expired and creds.refresh_token:
            creds.refresh(GoogleRequest())

        service = build("calendar", "v3", credentials=creds)

        # Parse time
        start = datetime.strptime(f"{req.date} {req.time.upper()}", "%Y-%m-%d %I:%M %p")
        start = pytz.timezone(TIMEZONE).localize(start)
        end = start + timedelta(minutes=30)

        attendees = [{"email": "shakauthossain0@gmail.com"}, {"email": req.user_email}]
        if req.guest_emails:
            attendees += [{"email": guest} for guest in req.guest_emails]

        event = {
            "summary": req.summary,
            "description": req.description,
            "start": {"dateTime": start.isoformat(), "timeZone": TIMEZONE},
            "end": {"dateTime": end.isoformat(), "timeZone": TIMEZONE},
            "attendees": attendees,
            "conferenceData": {
                "createRequest": {
                    "requestId": str(uuid.uuid4()),
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            },
        }

        event_result = service.events().insert(
            calendarId="primary",
            body=event,
            conferenceDataVersion=1,
            sendUpdates="all",
        ).execute()

        return {
            "message": "Meeting scheduled successfully!",
            "event_link": event_result.get("htmlLink"),
            "meet_link": event_result.get("conferenceData", {}).get("entryPoints", [{}])[0].get("uri", "No Meet link")
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail="Input Format Error: " + str(e))