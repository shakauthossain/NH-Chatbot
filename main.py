#FastAPI Packages
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

#Route Calling From faq_routes.py
from faq_routes import router as faq_router
import auth
from telegram import router as telegram_router

app = FastAPI()

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include FAQ API routes
app.include_router(faq_router)
app.include_router(auth.router)
app.include_router(telegram_router)
