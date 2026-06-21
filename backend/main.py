"""
Koach OS v2 — FastAPI Backend
================================
Thin wrapper around existing Python core modules.
Shares data_manager, router, prompts, bias_detector, learning_engine with Streamlit app.
"""

import os
import sys
from pathlib import Path

# Add project root + backend dir to path so we can import shared modules and routers
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from data_manager import init_all_data_files
from routers import chat, logs, review, memory, settings, analyze, voice, suggestions, calendar, daily_brief, gmail_calendar, tasks, memos, documents

# Initialize data files on startup
init_all_data_files()

app = FastAPI(
    title="Koach OS v2 API",
    description="Structured Reflective AI Partner — Backend API",
    version="2.0.0",
)

# CORS — env override for production (comma-separated origins)
_default_origins = ["http://localhost:3000", "http://localhost:3001"]
_env_origins = os.environ.get("CORS_ORIGINS", "")
_allow_origins = (
    [o.strip() for o in _env_origins.split(",") if o.strip()]
    if _env_origins
    else _default_origins
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(chat.router, prefix="/api")
app.include_router(logs.router, prefix="/api")
app.include_router(review.router, prefix="/api")
app.include_router(memory.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(analyze.router, prefix="/api")
app.include_router(voice.router, prefix="/api")
app.include_router(suggestions.router, prefix="/api")
app.include_router(calendar.router, prefix="/api")
app.include_router(daily_brief.router, prefix="/api")
app.include_router(gmail_calendar.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")
app.include_router(memos.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
from routers import training
app.include_router(training.router, prefix="/api")
from routers import productivity
app.include_router(productivity.router, prefix="/api")
from routers import private_chat
app.include_router(private_chat.router, prefix="/api")
from routers import completions
app.include_router(completions.router, prefix="/api")
from routers import evening_brief, balance, focus_timer, weekly_review, dispatcher, rag_query, health_intake, kpi, voice_intake, ai_services
app.include_router(evening_brief.router, prefix="/api")
app.include_router(balance.router, prefix="/api")
app.include_router(focus_timer.router, prefix="/api")
app.include_router(weekly_review.router, prefix="/api")
app.include_router(dispatcher.router, prefix="/api")
app.include_router(rag_query.router, prefix="/api")
app.include_router(health_intake.router, prefix="/api")
app.include_router(kpi.router, prefix="/api")
app.include_router(voice_intake.router, prefix="/api")
app.include_router(ai_services.router, prefix="/api")
from routers import media_extract
app.include_router(media_extract.router, prefix="/api")
from routers import personas, persona_chat
app.include_router(personas.router, prefix="/api")
app.include_router(persona_chat.router, prefix="/api")
from routers import patterns
app.include_router(patterns.router, prefix="/api")
from routers import agent
app.include_router(agent.router, prefix="/api")
from routers import email_watch, scheduling
app.include_router(email_watch.router, prefix="/api")
app.include_router(scheduling.router, prefix="/api")
from routers import projects
app.include_router(projects.router, prefix="/api")
from routers import secretary
app.include_router(secretary.router, prefix="/api")
from routers import cron
app.include_router(cron.router, prefix="/api")
from routers import external_chats
app.include_router(external_chats.router, prefix="/api")
from routers import dispatch_auto
app.include_router(dispatch_auto.router, prefix="/api")
from routers import self_improve
app.include_router(self_improve.router, prefix="/api")
from routers import research
app.include_router(research.router, prefix="/api")
from routers import work_log
app.include_router(work_log.router, prefix="/api")
from routers import routines
app.include_router(routines.router, prefix="/api")
from routers import assist
app.include_router(assist.router, prefix="/api")


@app.get("/api/health")
def health_check():
    return {"status": "ok", "version": "2.0.0"}
