"""Portfoli-AI  --  Main FastAPI application."""

import logging
import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import (  # type: ignore
    FastAPI, Request, Depends, HTTPException, UploadFile, File, Form, status,
)
from fastapi.exceptions import RequestValidationError  # type: ignore
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse  # type: ignore
from fastapi.staticfiles import StaticFiles  # type: ignore
from fastapi.templating import Jinja2Templates  # type: ignore
from pydantic import BaseModel, EmailStr  # type: ignore
from sqlalchemy.orm import Session  # type: ignore
from slowapi import Limiter, _rate_limit_exceeded_handler  # type: ignore
from slowapi.util import get_remote_address  # type: ignore
from slowapi.errors import RateLimitExceeded  # type: ignore

from config import UPLOAD_DIR, MAX_PDF_SIZE_MB, CHAT_RATE_LIMIT, OPENROUTER_API_KEY  # type: ignore
from database import get_db, init_db  # type: ignore
from models import User, Portfolio  # type: ignore
from auth import (  # type: ignore
    create_user, authenticate_user, create_access_token,
    get_current_user, get_optional_user, get_user_by_username, get_user_by_email,
    verify_password, hash_password
)
from generator import process_resume  # type: ignore
from exporter import generate_portfolio_ppt  # type: ignore
from rag_engine import index_resume, chat as rag_chat, delete_index  # type: ignore

# ---------- Logging ----------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# ---------- App setup ----------
app = FastAPI(title="Portfoli-AI", version="1.0.0")

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.on_event("startup")
def on_startup():
    init_db()
    logger.info("Portfoli-AI started")

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Validation error for {request.url}: {exc.errors()}")
    # Don't log the body as it might contain non-serializable data
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception for {request.url}: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)},
    )


# ========================================================================
# Pydantic request schemas
# ========================================================================

class SignupRequest(BaseModel):
    username: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class ChatRequest(BaseModel):
    message: str
    history: Optional[list] = None

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class ApiKeyUpdate(BaseModel):
    openrouter_api_key: str

# ========================================================================
# Page routes (HTML)
# ========================================================================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, user: Optional[User] = Depends(get_optional_user)):
    return templates.TemplateResponse("index.html", {"request": request, "user": user})


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "mode": "login"})


@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "mode": "signup"})


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(
    request: Request,
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    if user is None:
        return RedirectResponse(url="/login", status_code=302)
    portfolio = db.query(Portfolio).filter(Portfolio.user_id == user.id).first()
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "portfolio": portfolio,
    })


@app.get("/p/{slug}", response_class=HTMLResponse)
async def portfolio_page(
    request: Request,
    slug: str,
    db: Session = Depends(get_db),
):
    portfolio = db.query(Portfolio).filter(Portfolio.slug == slug).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    owner = db.query(User).filter(User.id == portfolio.user_id).first()
    return templates.TemplateResponse("portfolio.html", {
        "request": request,
        "portfolio": portfolio,
        "owner": owner,
    })

@app.get("/test_chat", response_class=HTMLResponse)
async def test_chat_page(request: Request):
    return templates.TemplateResponse("test_chat.html", {"request": request})


# ========================================================================
# Auth API routes
# ========================================================================

@app.post("/api/signup")
async def api_signup(payload: SignupRequest, db: Session = Depends(get_db)):
    if get_user_by_username(db, payload.username):
        raise HTTPException(status_code=400, detail="Username already taken")
    if get_user_by_email(db, payload.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    if len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    user = create_user(db, payload.username, payload.email, payload.password)
    token = create_access_token({"sub": user.username})
    resp = JSONResponse({"message": "Account created", "token": token})
    resp.set_cookie("access_token", token, httponly=False, samesite="lax", max_age=86400, path="/")
    return resp


@app.post("/api/login")
async def api_login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": user.username})
    resp = JSONResponse({"message": "Logged in", "token": token})
    resp.set_cookie("access_token", token, httponly=False, samesite="lax", max_age=86400, path="/")
    return resp

@app.post("/api/user/change-password")
async def api_change_password(
    payload: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect current password")
    user.hashed_password = hash_password(payload.new_password)
    db.commit()
    return {"message": "Password updated successfully"}


@app.post("/api/logout")
async def api_logout():
    resp = JSONResponse({"message": "Logged out"})
    resp.delete_cookie("access_token", path="/")
    return resp


# ========================================================================
# Portfolio API routes
# ========================================================================

@app.post("/api/upload")
async def upload_resume(
    file: UploadFile = File(..., description="PDF resume file"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    logger.info(f"Upload request received for user: {user.username}")
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    logger.info(f"File received: {file.filename}, content type: {file.content_type}")
    contents = await file.read()
    assert isinstance(contents, bytes)
    size_mb = len(contents) / (1024 * 1024)
    logger.info(f"File size: {size_mb:.2f} MB")
    if size_mb > MAX_PDF_SIZE_MB:
        raise HTTPException(status_code=400, detail=f"File exceeds {MAX_PDF_SIZE_MB}MB limit")

    api_key = user.openrouter_api_key or OPENROUTER_API_KEY
    if not api_key:
        raise HTTPException(status_code=400, detail="Please set your OpenRouter API key first")

    # Save file
    filename = f"{user.username}_{uuid.uuid4().hex}.pdf"
    filepath = os.path.join(UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(contents)

    try:
        logger.info(f"Processing resume for user: {user.username}")
        # Generate portfolio data via LLM
        data = await process_resume(filepath, api_key, username=user.username)
        logger.info(f"Resume processing successful for user: {user.username}")
        logger.info(f"Generated data keys: {list(data.keys())}")
    except Exception as e:
        logger.error("Resume processing failed for user %s: %s", user.username, str(e))
        logger.error("Full traceback:", exc_info=True)
        
        # Create fallback portfolio data
        logger.info("Creating fallback portfolio for user: %s", user.username)
        data = {
            "name": user.username.title(),
            "role": "Professional",
            "tagline": "Building the future with AI",
            "bio": "This portfolio was generated from your resume. Please update with your specific details.",
            "skills": ["Python", "JavaScript", "AI", "Web Development"],
            "projects": [],
            "experience": [],
            "education": [],
            "achievements": [],
            "contact": {},
            "_raw_text": "Fallback portfolio created due to processing error"
        }
        logger.info("Fallback portfolio created successfully")
    finally:
        # Clean up uploaded file
        if os.path.exists(filepath):
            os.remove(filepath)

    raw_text = data.pop("_raw_text", "")
    slug = user.username

    # Upsert portfolio
    portfolio = db.query(Portfolio).filter(Portfolio.user_id == user.id).first()
    if portfolio:
        portfolio.name = data.get("name", "")
        portfolio.role = data.get("role", "")
        portfolio.tagline = data.get("tagline", "")
        portfolio.bio = data.get("bio", "")
        portfolio.skills = data.get("skills", [])
        portfolio.projects = data.get("projects", [])
        portfolio.experience = data.get("experience", [])
        portfolio.education = data.get("education", [])
        portfolio.achievements = data.get("achievements", [])
        portfolio.contact = data.get("contact", {})
        portfolio.resume_text = raw_text
        portfolio.profile_image_url = data.get("profile_image_url")
    else:
        portfolio = Portfolio(
            user_id=user.id,
            name=data.get("name", ""),
            role=data.get("role", ""),
            tagline=data.get("tagline", ""),
            bio=data.get("bio", ""),
            skills=data.get("skills", []),
            projects=data.get("projects", []),
            experience=data.get("experience", []),
            education=data.get("education", []),
            achievements=data.get("achievements", []),
            contact=data.get("contact", {}),
            slug=slug,
            resume_text=raw_text,
            profile_image_url=data.get("profile_image_url"),
        )
        db.add(portfolio)

    db.commit()
    db.refresh(portfolio)

    # Index for RAG
    index_resume(slug, raw_text, data)

    return {"message": "Portfolio generated", "slug": slug, "url": f"/p/{slug}"}


@app.delete("/api/portfolio")
async def delete_portfolio(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    portfolio = db.query(Portfolio).filter(Portfolio.user_id == user.id).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="No portfolio found")
    delete_index(portfolio.slug)
    db.delete(portfolio)
    db.commit()
    return {"message": "Portfolio deleted"}


@app.put("/api/settings/apikey")
@app.post("/api/settings/apikey")  # Also support POST for compatibility
async def update_api_key(
    payload: ApiKeyUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user.openrouter_api_key = payload.openrouter_api_key
    db.commit()
    return {"message": "API key updated"}

# Alternative endpoint that matches frontend expectation
@app.post("/api/user/api-key")
async def update_api_key_alt(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    import json
    body = await request.body()
    data = json.loads(body)
    user.openrouter_api_key = data.get("api_key") or data.get("openrouter_api_key")
    db.commit()
    return {"message": "API key updated"}


# ========================================================================
# Chat API route
# ========================================================================

@app.post("/api/chat/{slug}")
@limiter.limit(CHAT_RATE_LIMIT)
async def chat_endpoint(
    request: Request,
    slug: str,
    payload: ChatRequest,
    db: Session = Depends(get_db),
):
    portfolio = db.query(Portfolio).filter(Portfolio.slug == slug).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    owner = db.query(User).filter(User.id == portfolio.user_id).first()
    api_key = (owner.openrouter_api_key if owner else None) or OPENROUTER_API_KEY
    if not api_key:
        raise HTTPException(status_code=400, detail="Portfolio owner has no API key configured")

    try:
        answer = await rag_chat(
            slug=slug,
            user_message=payload.message,
            api_key=api_key,
            resume_text=portfolio.resume_text or "",
            portfolio_data={
                "name": portfolio.name,
                "role": portfolio.role,
                "bio": portfolio.bio,
                "skills": portfolio.skills,
                "projects": portfolio.projects,
                "experience": portfolio.experience,
                "education": portfolio.education,
                "achievements": portfolio.achievements,
                "contact": portfolio.contact,
            },
            conversation_history=payload.history,
        )
    except Exception as e:
        logger.error("Chat failed for slug=%s: %s", slug, e)
        raise HTTPException(status_code=500, detail="Chat service temporarily unavailable")

    return {"answer": answer}


@app.get("/api/portfolio/{slug}/export/ppt")
async def export_portfolio_ppt(
    slug: str,
    db: Session = Depends(get_db)
):
    portfolio = db.query(Portfolio).filter(Portfolio.slug == slug).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
        
    owner = db.query(User).filter(User.id == portfolio.user_id).first()
    
    try:
        ppt_path = generate_portfolio_ppt(portfolio, owner)
        if not ppt_path or not os.path.exists(ppt_path):
            raise HTTPException(status_code=500, detail="Failed to generate PPT")
            
        return FileResponse(
            path=ppt_path,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            headers={"Content-Disposition": f'attachment; filename="{owner.username}_portfolio.pptx"'}
        )
    except Exception as e:
        logger.error("Error generating PPT for slug=%s: %s", slug, e)
        raise HTTPException(status_code=500, detail="Internal error generating presentation")
