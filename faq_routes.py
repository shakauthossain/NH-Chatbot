#Basic Packages
import io
import os
import uuid
import traceback
import requests
import pytz
import json
import time
import asyncio
import redis
import pandas as pd
from dotenv import load_dotenv
from typing import List, Optional
from datetime import datetime, timedelta
from collections import deque
from urllib.parse import urlparse

#Google API Packages
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.discovery import build

#API Packages
from fastapi import APIRouter, UploadFile, File, HTTPException, Body, Path, Query

#FAQ CSV Validator Package
from pydantic import BaseModel, EmailStr

#Calling Functions from other py files
from faq_services import gemini_model, db, load_faqs, add_faq_to_csv, faq_path
from chatbot_prompt import generate_prompt, detect_schedule_intent, detect_agent_intent
from telegram import send_to_telegram, pending_requests

router = APIRouter()

load_dotenv()
CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
ACCESS_TOKEN = os.getenv("GOOGLE_ACCESS_TOKEN")
REFRESH_TOKEN = os.getenv("GOOGLE_REFRESH_TOKEN")
redis_url = os.getenv("REDIS_URL")
TIMEZONE = "Asia/Dhaka"
SCOPES = ['https://www.googleapis.com/auth/calendar']
r = redis.from_url(redis_url, decode_responses=True)

agent_active_users = set()
user_sessions = {}
REDIS_KEY_PREFIX = "chat_session:"
MAX_HISTORY = 7

# Data validation classes
class QuestionRequest(BaseModel):
    query: str
    user_id: Optional[str] = None

class FAQItem(BaseModel):
    question: str
    answer: str

# Meeting request model for Google Calendar
class MeetingRequest(BaseModel):
    date: str  # "YYYY-MM-DD" format, e.g. "2025-07-20"
    time: str  # "HH:MM PM" format, e.g. "03:00 PM"
    user_email: EmailStr
    summary: Optional[str] = None
    description: Optional[str] = None
    guest_emails: Optional[List[EmailStr]] = None
    
def get_history(user_id):
    key = f"{REDIS_KEY_PREFIX}{user_id}"
    history = r.lrange(key, 0, -1)
    return [json.loads(x) for x in history]

def update_history(user_id, role, content):
    key = f"{REDIS_KEY_PREFIX}{user_id}"
    r.rpush(key, json.dumps({"role": role, "content": content}))
    r.ltrim(key, -MAX_HISTORY, -1)
    r.expire(key, 1800)
    
def build_prompt_from_history(history):
    return "\n".join(f"{msg['role']}: {msg['content']}" for msg in history) + "\nuser:"

@router.get("/")
def greet_json():
    return {"Hello": "It is working!"}

# Chat endpoint API
@router.post("/ask")
async def ask_faq(request: QuestionRequest):
    query = request.query.strip()
    user_id = request.user_id or f"user_{int(time.time()*1000)}"

    # Detect agent intent
    if user_id in agent_active_users:
        send_to_telegram(query, user_id=user_id)
        return {
            "from_agent": True,
            "message": "📨 Message sent to your agent. Please wait for their reply."
        }

    if detect_agent_intent(query):
        agent_active_users.add(user_id)
        send_to_telegram(query, user_id=user_id)
        return {
            "action": "connect_agent",
            "user_id": user_id,
            "message": "✅ Connecting you to a human agent..."
        }

    # Detect scheduling
    if detect_schedule_intent(query):
        return {
            "action": "schedule_meeting",
            "message": "Sure! Let's schedule your meeting. Please choose a date and time."
        }

    # Prepare prompt with history
    update_history(user_id, "user", query)
    history = get_history(user_id)
    prompt = build_prompt_from_history(history)

    # Call Gemini LLM
    try:
        response = gemini_model.generate_content(prompt)
        answer = response.text.strip()

        # Add bot response to history
        # user_sessions[user_id].append({"role": "bot", "content": answer})
        update_history(user_id, "bot", answer) 

        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/end-agent-session/{user_id}")
def end_agent_session(user_id: str):
    if user_id in agent_active_users:
        agent_active_users.remove(user_id)
    r.delete(f"{REDIS_KEY_PREFIX}{user_id}")

    return {"message": f"Agent session ended and memory cleared for {user_id}"}

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

# Google Calendar API routes
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
            "timeMin": start_date,
            "timeMax": end_date,
            "timeZone": TIMEZONE,
            "items": [{"id": "primary"}]
        }

        response = service.freebusy().query(body=body).execute()
        busy_slots = response["calendars"]["primary"]["busy"]

        return {"busy": busy_slots}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Schedule Meeting API
@router.post("/google-calendar/schedule")
def schedule_meeting(req: MeetingRequest):
    try:
        print("Received meeting data:", req.dict())
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