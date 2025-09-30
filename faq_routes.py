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
from collections import defaultdict, deque

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
from chatbot_prompt import detect_schedule_intent, detect_agent_intent, detect_services_intent, detect_specific_service_inquiry
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
r = None
try:
    if redis_url:
        # Upstash often needs TLS (rediss://). from_url handles it.
        r = redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
            retry_on_timeout=True,
        )
        r.ping()  # fail fast if unreachable
        print("Redis connected")
    else:
        print("REDIS_URL not set, using in-memory history")
except Exception as e:
    print(f"Redis unavailable ({e}), using in-memory history")
    r = None

agent_active_users = set()
user_sessions = {}
REDIS_KEY_PREFIX = "chat_session:"
MAX_HISTORY = 7

# Greeting status tracking
greeted_users = set()  # Track users who have been greeted
GREETING_KEYWORDS = ['hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening', 'greetings', 'who are you?', 'what is your name']

_fallback_histories = defaultdict(lambda: deque(maxlen=MAX_HISTORY))
HISTORY_TTL_SECONDS = 1800
_last_seen = {}

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

def _fallback_update(user_id, item):
    dq = _fallback_histories[user_id]
    dq.append(item)
    _last_seen[user_id] = time.time()

def _fallback_get(user_id):
    # optional TTL pruning
    ts = _last_seen.get(user_id)
    if ts and (time.time() - ts) > HISTORY_TTL_SECONDS:
        _fallback_histories.pop(user_id, None)
        _last_seen.pop(user_id, None)
        return []
    return list(_fallback_histories.get(user_id, []))

def get_history(user_id):
    key = f"{REDIS_KEY_PREFIX}{user_id}"
    if r:
        try:
            items = r.lrange(key, -MAX_HISTORY, -1)
            return [json.loads(x) for x in items]
        except Exception as e:
            print(f"Redis read failed: {e}; using fallback")
    return _fallback_get(user_id)

def update_history(user_id, role, content):
    item = {"role": role, "content": content}
    key = f"{REDIS_KEY_PREFIX}{user_id}"
    if r:
        try:
            pipe = r.pipeline()
            pipe.rpush(key, json.dumps(item))
            pipe.ltrim(key, -MAX_HISTORY, -1)
            pipe.expire(key, HISTORY_TTL_SECONDS)
            pipe.execute()
            return
        except Exception as e:
            print(f"Redis write failed: {e}; using fallback")
    _fallback_update(user_id, item)

def clear_history(user_id):
    key = f"{REDIS_KEY_PREFIX}{user_id}"
    if r:
        try:
            r.delete(key)
        except Exception as e:
            print(f"Redis delete failed: {e}")
    _fallback_histories.pop(user_id, None)
    _last_seen.pop(user_id, None)

def is_greeting(user_input: str) -> bool:
    """Check if user input is a greeting"""
    input_lower = user_input.lower().strip()
    return any(greeting in input_lower for greeting in GREETING_KEYWORDS)

def should_greet_user(user_id: str, user_input: str) -> bool:
    """Determine if user should be greeted"""
    # If user hasn't been greeted and is saying hello
    if user_id not in greeted_users and is_greeting(user_input):
        greeted_users.add(user_id)
        return True
    return False

def enhanced_generate_prompt(context: str, query: str, user_id: str) -> str:
    """Generate prompt with greeting logic"""
    has_been_greeted = user_id in greeted_users
    
    if not has_been_greeted and is_greeting(query):
        greeting_instruction = "When responding to this greeting, introduce yourself once as NH Buddy, Notionhive's virtual assistant, then answer their question helpfully."
        greeted_users.add(user_id)  # Mark as greeted
    elif has_been_greeted:
        greeting_instruction = "CRITICAL: You have already introduced yourself to this user. NEVER say 'NH Buddy here', 'I am NH Buddy', 'I'm NH Buddy', or 'Notionhive's virtual assistant' again. Simply answer their questions directly and helpfully."
    else:
        greeting_instruction = "CRITICAL: Answer the user's question directly without introducing yourself. Do NOT say 'NH Buddy here', 'I am NH Buddy', or introduce yourself unless they specifically ask who you are."
    
    return f"""
You are NH Buddy, a smart, witty, and helpful virtual assistant proudly representing Notionhive. You are designed to be the best FAQ chatbot — charming, fast-thinking, and always on-brand.
Your primary mission is to assist users by answering their questions with clarity, accuracy, and a touch of clever personality, based on the official Notionhive FAQs and website: [https://notionhive.com](https://notionhive.com).

{greeting_instruction}

Your tone is:
Helpful, but never robotic
Confident, but not cocky
Professional, but always friendly
Occasionally sprinkled with tasteful humor or smart quips (you're sharp, not silly)

### Core Instructions:

* For all Notionhive-related questions (services, process, team, pricing, contact, case studies, etc.), search and respond using the official FAQs and website content at [https://notionhive.com](https://notionhive.com).
* If the information isn't found in your internal data and the question is relevant or critical, you may attempt a web search limited to notionhive.com.
* If no answer is found, politely recommend the user to visit the site directly or contact the Notionhive team.
* If the question is basic/general and not covered on the site (e.g., "What is digital marketing?"), you may briefly answer with factual, easy-to-understand info — but always steer the user back toward how Notionhive can help.
* If no answer is found, then provide an answer like in funny way: "Sorry, I am unable to answer your query right now. Please call +880 140 447 4990 📞 or email hello@notionhive.com 📧 Thanks!" but in a good and funny way
* CRITICAL: Never repeat "NH Buddy here, Notionhive's virtual assistant." you need to say it only once when greeted first time, never after that.
* NEVER start responses with "NH Buddy here," or "I am NH Buddy" or "I'm NH Buddy" or similar introductions.

### Do's and Don'ts:

Always be polite, funny and respectful.
Act like first person, use "we" appropriately instead of "Notionhive".
Be witty, crisp, and precise.
Rephrase "yes" or "no" answers into helpful, human-sounding sentences.
Keep responses relevant and readable — no tech babble unless asked.  
If unsure, be honest — suggest checking the site or asking the team.
Never invent details or claim things not listed on Notionhive's site.
Don't answer personal, financial, or legal questions. That's not your jam.
Don't answer anything personal, financial, or legal related questions of Notionhive.
Make sure no sensitive or private info is shared.
Make sure no leads can be extracted from your responses.
Avoid repetitive filler phrases or "As an AI..." language.
Avoid add "bot:" in front of any of your responses.
CRITICAL: Do NOT start responses with "NH Buddy here," or "I am NH Buddy" or any form of self-identification unless specifically asked who you are.

You're NH Buddy — the face of Notionhive's brilliance and creativity. Show it.
Do not return in markdown format, just in fantastic plain text.
Use the following context to answer the user's question:

{context}

User Question: {query}
Answer:"""
    
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
    # if user_id in agent_active_users:
    #     send_to_telegram(query, user_id=user_id)
    #     return {
    #         "from_agent": True,
    #         "answer": "Message sent to your agent. Please wait for their reply."
    #     }

    # if detect_agent_intent(query):
    #     agent_active_users.add(user_id)

    #     history = get_history(user_id)
    #     history_text = "\n".join(f"{msg['role']}: {msg['content']}" for msg in history[-5:])
    #     summary_msg = f"New agent request from user: {user_id}*\n\n Chat Summary:\n{history_text}"

    #     # First send summary
    #     send_to_telegram(summary_msg, user_id=user_id)

    #     # Then send the live message
    #     send_to_telegram(query, user_id=user_id)

    #     return {
    #         "action": "connect_agent",
    #         "user_id": user_id,
    #         "answer": "Connecting you to a human agent..."
    #     }

    # Detect scheduling
    if detect_schedule_intent(query):
        return {
            "action": "schedule_meeting",
            "answer": "Sure! Let's schedule your meeting. Please choose a date and time."
        }

    # Check for specific service inquiries first
    is_specific_service, enhanced_query, service_name = detect_specific_service_inquiry(query)
    if is_specific_service:
        # Use the enhanced query to search FAQs for specific service information
        try:
            docs = db.similarity_search(enhanced_query, k=3)
            context = "\n".join([doc.page_content for doc in docs])
        except Exception as e:
            print(f"FAQ search failed for specific service: {e}")
            context = "No specific FAQ context available."
        
        # Prepare prompt for specific service inquiry
        update_history(user_id, "user", query)
        prompt = enhanced_generate_prompt(context, f"Tell me about {service_name} services that Notionhive offers. {query}", user_id)
        
        # Call Gemini LLM
        try:
            response = gemini_model.generate_content(prompt)
            answer = response.text.strip()
            update_history(user_id, "bot", answer)
            return {
                "action": "specific_service_inquiry", 
                "service": service_name,
                "answer": answer
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # Detect general services inquiry (show service list)
    if detect_services_intent(query):
        services_list = [
            {
                "name": "🌐 Web & App Development",
                "description": "Custom websites and mobile applications tailored to your needs"
            },
            {
                "name": "🎨 User Experience Design", 
                "description": "Intuitive and engaging user interfaces that delight your customers"
            },
            {
                "name": "📊 Strategy & Digital Marketing",
                "description": "Data-driven marketing strategies to grow your business"
            },
            {
                "name": "🎥 Video Production & Photography",
                "description": "Professional visual content that tells your story"
            },
            {
                "name": "🏷️ Branding & Communication",
                "description": "Complete brand identity and messaging solutions"
            },
            {
                "name": "🔍 Search Engine Optimization",
                "description": "Get found online with our proven SEO strategies"
            },
            {
                "name": "👥 Resource Augmentation",
                "description": "Skilled professionals to extend your team capabilities"
            }
        ]

        return {
            "action": "services_inquiry",
            "services": services_list,
            "answer": "Here are our comprehensive services. Ready to transform your digital presence?"
        }

    # Search FAQ database for relevant context
    try:
        # Get relevant FAQ content from vector database
        docs = db.similarity_search(query, k=3)  # Get top 3 most relevant FAQs
        context = "\n".join([doc.page_content for doc in docs])
    except Exception as e:
        print(f"FAQ search failed: {e}")
        context = "No specific FAQ context available."

    # Prepare prompt with history and FAQ context
    update_history(user_id, "user", query)
    history = get_history(user_id)
    
    # Generate prompt using FAQ context and greeting logic
    prompt = enhanced_generate_prompt(context, query, user_id)

    # Call Gemini LLM
    try:
        response = gemini_model.generate_content(prompt)
        answer = response.text.strip()

        update_history(user_id, "bot", answer) 

        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/end-agent-session/{user_id}")
def end_agent_session(user_id: str):
    agent_active_users.discard(user_id)
    greeted_users.discard(user_id)  # Clear greeting status
    clear_history(user_id)
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