from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from dotenv import load_dotenv
import os

load_dotenv()
router = APIRouter()

CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
ENV_REDIRECT_URI = os.getenv("REDIRECT_URI")  # optional override

SCOPES = ["https://www.googleapis.com/auth/calendar"]

def build_redirect_uri(request: Request) -> str:
    """
    Prefer env REDIRECT_URI if set.
    Otherwise, derive from request with proxy headers so it works on HF + local.
    """
    if ENV_REDIRECT_URI:
        return ENV_REDIRECT_URI.strip().rstrip("/")

    # Respect reverse proxy headers (HF Spaces)
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.hostname
    return f"{proto}://{host}/auth/callback".rstrip("/")

def build_flow(redirect_uri: str) -> Flow:
    return Flow.from_client_config(
        {
            "web": {
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri],
            }
        },
        scopes=SCOPES,
    )

@router.get("/auth/login")
def login(request: Request):
    redirect_uri = build_redirect_uri(request)
    flow = build_flow(redirect_uri)
    flow.redirect_uri = redirect_uri

    # IMPORTANT: offline access so we get refresh_token
    auth_url, _ = flow.authorization_url(
        prompt="consent",
        include_granted_scopes="true",
        access_type="offline",
    )
    return RedirectResponse(auth_url)

@router.get("/auth/callback")
async def auth_callback(request: Request):
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Missing code")

    redirect_uri = build_redirect_uri(request)
    flow = build_flow(redirect_uri)
    flow.redirect_uri = redirect_uri

    try:
        flow.fetch_token(code=code)
        credentials = flow.credentials
        return {
            "access_token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "expiry": credentials.expiry.isoformat() if credentials.expiry else None,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch token: {e}")
