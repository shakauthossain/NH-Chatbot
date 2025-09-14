#Basic Packages
import os
import requests
import re
import time
from dotenv import load_dotenv
from collections import defaultdict, deque

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
user_replies = defaultdict(lambda: deque(maxlen=50))
pending_requests = {}
last_user_tagged = None
message_map = {}


# Send message to Telegram agent with user tag
def send_to_telegram(message: str, user_id: str = "anonymous") -> bool:
    try:
        tag = f"[USER:{user_id}]"
        full_message = (
            "👤 New user message\n"
            f"{tag}\n\n"
            f"{message}\n\n"
            f"↩️ Agents: Please REPLY to this message (or include {tag} in your reply)."
        )
        payload = {
            "chat_id": int(AGENT_CHAT_ID),
            "text": full_message,
            "disable_web_page_preview": True,
        }
        url = f"{TELEGRAM_API_BASE}/sendMessage"
        resp = requests.post(url, json=payload, timeout=10)

        print("Sending to Telegram group...")
        print("Payload:", payload)
        print("Telegram response:", resp.status_code, resp.text)

        if not resp.ok:
            return False

        # store message_id -> user_id for robust correlation
        data = resp.json()
        msg_id = (data.get("result") or {}).get("message_id")
        if msg_id is not None:
            message_map[msg_id] = user_id
        return True

    except Exception as e:
        print("Error in send_to_telegram:", str(e))
        return False

def _extract_user_tag(text: str) -> str | None:
    if not text:
        return None
    m = re.search(r"\[USER:(.+?)\]", text)
    return m.group(1).strip() if m else None

def _select_update_payload(data: dict) -> dict | None:
    return (data.get("message")
            or data.get("edited_message")
            or data.get("channel_post")
            or data.get("edited_channel_post"))

def _extract_user_tag(text: str):
    if not text:
        return None
    m = re.search(r"\[USER:(.+?)\]", text)
    return m.group(1).strip() if m else None

@router.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        msg = (
            data.get("message")
            or data.get("edited_message")
            or data.get("channel_post")
            or data.get("edited_channel_post")
        )
        if not msg:
            return {"status": "ignored", "reason": "no usable message"}

        text = msg.get("text") or msg.get("caption") or ""

        # Debug: print the full incoming Telegram update
        print("[webhook] Incoming Telegram update:", msg)
        print("[webhook] Current message_map:", message_map)
        print("[webhook] Current user_replies:", {k: list(v) for k, v in user_replies.items()})

        from_user = (msg.get("from") or {}).get("username") \
                    or (msg.get("from") or {}).get("first_name") \
                    or "agent"

        rt = msg.get("reply_to_message")
        if rt:
            print("[webhook] Found reply_to_message:", rt)
            reply_to_id = rt.get("message_id")
            print("[webhook] reply_to_id:", reply_to_id)
            if reply_to_id in message_map:
                user_id = message_map.pop(reply_to_id)  # one-shot map
                print(f"[webhook] Matched reply_to_id in message_map: {reply_to_id} -> {user_id}")
                # ⬇️ QUEUE the reply instead of overwriting
                user_replies[user_id].append({
                    "reply": text.strip(),
                    "from": from_user,
                    "ts": time.time(),
                })
                print(f"[webhook] matched via reply_to_id -> {user_id}")
                return {"status": "ok", "via": "reply_to_id", "user_id": user_id}

            # fallback: try user tag in the original text
            orig = rt.get("text") or rt.get("caption") or ""
            print("[webhook] fallback: original text for user tag:", orig)
            user_id = _extract_user_tag(orig)
            if user_id:
                print(f"[webhook] Matched user tag in reply_to_message text: {user_id}")
                user_replies[user_id].append({
                    "reply": text.strip(),
                    "from": from_user,
                    "ts": time.time(),
                })
                print(f"[webhook] matched via reply_to_text -> {user_id}")
                return {"status": "ok", "via": "reply_to_text", "user_id": user_id}

        # Last resort: allow inline [USER:...] in the agent's own message
        user_id = _extract_user_tag(text)
        if user_id:
            print(f"[webhook] Matched inline user tag in agent message: {user_id}")
            clean = re.sub(r"\[USER:.+?\]\s*", "", text).strip()
            user_replies[user_id].append({
                "reply": clean,
                "from": from_user,
                "ts": time.time(),
            })
            print(f"[webhook] matched via inline_tag -> {user_id}")
            return {"status": "ok", "via": "inline_tag", "user_id": user_id}

        print("[webhook] ignored: no correlation")
        return {"status": "ignored", "reason": "no correlation"}

    except Exception as e:
        print("Webhook error:", repr(e))
        raise HTTPException(status_code=400, detail=str(e))



# Sending message to agent
@router.get("/telegram/reply/{user_id}")
def get_agent_reply(user_id: str):
    q = user_replies.get(user_id)
    if q and len(q):
        item = q.popleft()  # FIFO
        return {
            "from_agent": True,
            "message": item["reply"],
            "agent": item["from"]
        }
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

@router.get("/telegram/health")
def telegram_health():
    return {
      "getMe": requests.get(f"{TELEGRAM_API_BASE}/getMe", timeout=10).json(),
      "webhook": requests.get(f"{TELEGRAM_API_BASE}/getWebhookInfo", timeout=10).json()
    }

@router.get("/telegram/debug/state")
def tg_state():
    return {"message_map_size": len(message_map), "user_replies_size": len(user_replies)}

@router.get("/telegram/debug/user/{user_id}")
def tg_user(user_id: str):
    return {"stored": user_replies.get(user_id)}