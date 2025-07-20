#Basic Packages
import os
import requests
import re
from dotenv import load_dotenv

# FastAPI Packages
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

load_dotenv()
router = APIRouter()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
AGENT_CHAT_ID = int(-1002796640614)  #Group Chat ID starts with -100, Normal chat ID starts with Normal ID
TELEGRAM_API_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# Temporary in-memory reply store
user_replies = {}
pending_requests = {}
last_user_tagged = None

# Send message to Telegram agent with user tag
def send_to_telegram(message: str, user_id: str = "anonymous") -> bool:
    try:
        tag = f"[USER:{user_id}]"
        full_message = f"{tag}\n\n{message}"
        chat_id = int(AGENT_CHAT_ID)

        payload = {
            "chat_id": chat_id,
            "text": full_message
        }

        url = f"{TELEGRAM_API_BASE}/sendMessage"
        response = requests.post(url, json=payload)

        print("Sending to Telegram group...")
        print("Payload:", payload)
        print("Telegram response:", response.status_code, response.text)

        return response.status_code == 200

    except Exception as e:
        print("Error in send_to_telegram:", str(e))
        return False

# Telegram Webhook
@router.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        print("Telegram data:", data)

        msg = data.get("message", {})
        print("Telegram msg:", msg)
        message_text = msg.get("text", "")
        from_user = msg.get("from", {}).get("username", "agent")

        # Case 1: Agent used "Reply" to respond to bot's message
        reply_to = msg.get("reply_to_message", {})
        original_text = reply_to.get("text", "")
        print("Original text from reply_to_message:", original_text)

        user_tag_match = re.search(r"\[USER:(.+?)\]", original_text)
        if user_tag_match:
            user_id = user_tag_match.group(1).strip()
            print(f"Matched user tag from reply_to_message: {user_id}")

            reply_data = {
                "reply": message_text,
                "from": from_user
            }

            user_replies[user_id] = reply_data

            if user_id in pending_requests:
                future = pending_requests.pop(user_id)
                if not future.done():
                    future.set_result(reply_data)

            return {"status": "reply matched", "user_id": user_id}

        # Case 2: Agent directly typed message without reply (ignored)
        print("No [USER:...] found in reply_to_message.")
        return {"status": "ignored - no tag"}

    except Exception as e:
        print("Webhook error:", str(e))
        raise HTTPException(status_code=400, detail=str(e))

# Sending message to agent
@router.get("/telegram/reply/{user_id}")
def get_agent_reply(user_id: str):
    if user_id in user_replies:
        reply = user_replies.pop(user_id)
        print("Reply from user:", reply)
        return {
            "from_agent": True,
            "message": reply["reply"],
            "agent": reply["from"]
        }
    else:
        return {"from_agent": False, "message": None}

# Optional: Ping route to test
@router.get("/telegram/test")
def test_send():
    payload = {
        "chat_id": AGENT_CHAT_ID,
        "text": "This is a test message from your FastAPI bot"
    }

    url = f"{TELEGRAM_API_BASE}/sendMessage"
    response = requests.post(url, json=payload)

    print("Payload:", payload)
    print("Status:", response.status_code)
    print("Telegram response:", response.text)

    return JSONResponse(content={
        "status": response.status_code,
        "response": response.json()
    })