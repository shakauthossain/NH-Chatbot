#FastAPI Packages
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.proxy_headers import ProxyHeadersMiddleware

#Route Calling From faq_routes.py
from faq_routes import router as faq_router
import auth
# from telegram import router as telegram_router

app = FastAPI(title="Notionhive Chatbot")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    ProxyHeadersMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    trusted_hosts="*"
)

# Include FAQ API routes
app.include_router(faq_router)
app.include_router(auth.router)
# app.include_router(telegram_router)
