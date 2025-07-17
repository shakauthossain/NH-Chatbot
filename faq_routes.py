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

#API Packages
from fastapi import APIRouter, UploadFile, File, HTTPException, Body, Path

#FAQ CSV Validator Package
from pydantic import BaseModel, EmailStr

#Calling Functions from other py files
from faq_services import gemini_model, db, load_faqs, add_faq_to_csv, faq_path
from chatbot_prompt import generate_prompt

router = APIRouter()

load_dotenv()
calendly_api_key = os.getenv("CALENDLY_API")

# Data validation classes
class QuestionRequest(BaseModel):
    query: str

class FAQItem(BaseModel):
    question: str
    answer: str

CALENDLY_HOST_URL = "https://api.calendly.com/users/8374a3f7-29e8-4ef8-8609-59e01cce6733"
EVENT_NAME = "Service Inquiry Notionhive"
DEFAULT_TIMEZONE = "Asia/Dhaka"
EVENT_TYPE= "https://calendly.com/shakaut-notionhive/service-inquiry-notionhive"

HEADERS = {
    "Authorization": f"Bearer {calendly_api_key}",
    "Content-Type": "application/json"
}

# Pydantic model for incoming chatbot data
class ScheduleMeetingRequest(BaseModel):
    date: str
    time: str
    user_name: str
    user_email: EmailStr
    guest_email: Optional[EmailStr] = None
    details: Optional[str] = ""

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

@router.post("/calendly/schedule-fixed")
async def schedule_fixed_event(req: ScheduleMeetingRequest):
    try:
        print("🟡 Input Date:", req.date)
        print("🟡 Input Time:", req.time)

        # Step 1: Parse date and time separately
        date_part = datetime.strptime(req.date.strip(), "%Y %m %d").date()
        time_part = datetime.strptime(req.time.strip(), "%I.%M %p").time()

        # Step 2: Combine into full datetime
        combined = datetime.combine(date_part, time_part)

        # Step 3: Localize and convert
        tz = pytz.timezone(DEFAULT_TIMEZONE)
        dt_local = tz.localize(combined)

        # Used for validation/log
        start_time_iso = dt_local.isoformat()
        end_time_iso = (dt_local + timedelta(minutes=30)).isoformat()

        # Only use date part for Calendly's one_off_event_types
        date_str = dt_local.strftime("%Y-%m-%d")

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Date/time parse error: {str(e)}")

    payload = {
        "name": EVENT_NAME,
        "host": CALENDLY_HOST_URL,
        "duration": 30,
        "timezone": DEFAULT_TIMEZONE,
        "date_setting": {
            "type": "date_range",
            "start_date": date_str,
            "end_date": date_str
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

    print("📤 Payload to Calendly:")
    print(json.dumps(payload, indent=2))

    response = requests.post(
        "https://api.calendly.com/one_off_event_types",
        headers=HEADERS,
        json=payload
    )

    if response.status_code != 201:
        print("❌ Calendly Error:")
        print(response.text)
        raise HTTPException(status_code=response.status_code, detail=response.text)

    data = response.json()
    return {
        "message": "Meeting scheduled successfully!",
        "booking_url": data["resource"]["scheduling_url"]
    }

# @router.post("/calendly/schedule-fixed")
# async def schedule_fixed_event(req: ScheduleMeetingRequest):
#     try:
#         # Parse date + time
#         combined_str = f"{req.date} {req.time}"
#         dt_naive = datetime.strptime(combined_str, "%Y %m %d %I.%M %p")
#         tz = pytz.timezone("Asia/Dhaka")
#         dt_local = tz.localize(dt_naive)
#
#         # Convert to UTC for logs
#         start_utc = dt_local.astimezone(pytz.utc)
#         end_utc = start_utc + timedelta(minutes=30)
#         start_time_iso = start_utc.isoformat()
#         end_time_iso = end_utc.isoformat()
#
#         # Format date for Calendly
#         date_str = dt_local.strftime("%Y-%m-%d")
#
#     except Exception as e:
#         raise HTTPException(status_code=400, detail=str(e))
#
#     payload = {
#         "name": EVENT_NAME,
#         "event_type": EVENT_TYPE,
#         "host": CALENDLY_HOST_URL,
#         "duration": 30,
#         "timezone": DEFAULT_TIMEZONE,
#         "date_setting": {
#             "type": "date_range",
#             "start_time": date_str,
#             "end_time": date_str
#         },
#         "invitees": [
#             {
#                 "email": req.user_email,
#                 "name": req.user_name
#             }
#         ],
#         "location": {
#             "kind": "physical",
#             "location": "Virtual",
#             "additonal_info": req.details
#         }
#     }
#     print("👉 Raw inputs:")
#     print("Date:", req.date)
#     print("Time:", req.time)
#
#     response = requests.post(
#         "https://api.calendly.com/one_off_event_types",
#         headers=HEADERS,
#         json=payload
#     )
#     print(date_str)
#     if response.status_code != 201:
#         raise HTTPException(status_code=response.status_code, detail=response.text)
#
#     return {
#         "message": "Meeting scheduled successfully!",
#         "event": response.json()
#     }