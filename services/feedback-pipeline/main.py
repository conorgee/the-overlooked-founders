import logging
import os

from dotenv import load_dotenv

load_dotenv()

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# CORS — allow any localhost port + production domain
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^http://localhost(:\d+)?$",
    allow_origins=["https://the-overlooked-founders.netlify.app"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and include routers
from routers import health, knowledge, chat, scoring, process, analytics

app.include_router(health.router)
app.include_router(knowledge.router)
app.include_router(chat.router)
app.include_router(scoring.router)
app.include_router(process.router)
app.include_router(analytics.router)

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 3001))
    uvicorn.run(app, host="0.0.0.0", port=port)
