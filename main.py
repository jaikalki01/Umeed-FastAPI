import time
from contextlib import asynccontextmanager

import uvicorn
import random
from datetime import datetime
from typing import Dict
from app.routers.authenticate import router as auth_router
from app.routers.user_routes import router as user_router  # ✅ Safe aliasing
from app.routers.chat import router as chat_router
from app.routers.admin import router as admin_router

import requests
import uvicorn
from fastapi import FastAPI, Request, HTTPException, Depends, Form, APIRouter
from fastapi.staticfiles import StaticFiles

from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import JSONResponse, RedirectResponse, FileResponse

from starlette.templating import Jinja2Templates

from app.crud import user
from app.models.models import User





from app.utils.database import init_db, get_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ✅ Run on startup
    init_db()
    yield
    # ✅ Run on shutdown (if needed)


# ✅ Initialize FastAPI with Lifespan



app = FastAPI(
    title="UmeedWebApp API",
    description="API for Umeed WebApp.",
    version="1.0.0",
    lifespan=lifespan,
)

# ✅ Include User Routes
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/assets", StaticFiles(directory="static/dist/assets"), name="assets")

templates = Jinja2Templates(directory="templates")
import os
SECRET_KEY = os.urandom(24).hex()
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

app.add_middleware(
    CORSMiddleware,
    allow_origins={"*"},
    #allow_origins=["http://localhost:8080", "https://dash.gurutvapay.com", "https://www.templamart.com"],  # Allow requests from React frontend
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],  # Allow all headers
)

app.include_router(auth_router, prefix="/api/v1/auth", tags=["Login"])
app.include_router(user_router, prefix="/api/v1/users", tags=["Users"])
app.include_router(chat_router, prefix="/api/v1/chat", tags=["Chat"])
app.include_router(admin_router, prefix="/api/v1/admin", tags=["Admin"])  # ✅ Now correct


@app.middleware("http")
async def log_time(request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    #print(f"⏱️ {request.url.path} took {duration:.3f}s")
    return response

# ✅ Basic Root Check
"""@app.get("/")
def index():
    return "Welcome To Umeed"
"""
@app.get("/")
async def serve_react():
    return FileResponse("static/dist/index.html")

# Catch-all to support React Router
@app.get("/{full_path:path}")
async def serve_react_app(full_path: str):
    if full_path.startswith("api/"):
        return {"detail": "Not Found"}, 404
    return FileResponse("static/dist/index.html")


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True,  log_level="debug")
