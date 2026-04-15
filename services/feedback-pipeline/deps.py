"""
Shared dependencies — Supabase client, Groq client, auth middleware.
Separated from main.py to avoid circular imports with routers.
"""

import os

from fastapi import Header, HTTPException
from groq import Groq
from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
groq_client = Groq(api_key=os.environ["GROQ_API_KEY"])

API_KEY = os.environ.get("PIPELINE_API_KEY")


async def authenticate(x_api_key: str | None = Header(None)):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
