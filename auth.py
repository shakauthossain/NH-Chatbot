from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from dotenv import load_dotenv
import os

load_dotenv()
router = APIRouter()

CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")

SCOPES = ['https://www.googleapis.com/auth/calendar']

@router.get("/auth/login")
def login():
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [REDIRECT_URI],
            }
        },
        scopes=SCOPES
    )
    flow.redirect_uri = REDIRECT_URI
    auth_url, _ = flow.authorization_url(prompt='consent', include_granted_scopes='true')
    return RedirectResponse(auth_url)

@router.get("/auth/callback")
async def auth_callback(request: Request):
    code = request.query_params.get("code")
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [REDIRECT_URI],
            }
        },
        scopes=SCOPES
    )
    flow.redirect_uri = REDIRECT_URI
    flow.fetch_token(code=code)
    credentials = flow.credentials

    # Print or log this once — copy & store securely
    return {
        "access_token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "expiry": credentials.expiry.isoformat()
    }