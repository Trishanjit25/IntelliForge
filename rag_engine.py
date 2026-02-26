"""RAG engine for Portfoli-AI — answers chat queries using resume context."""

import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx

from config import (
    OPENROUTER_BASE_URL,
    DEFAULT_LLM_MODEL,
    LLM_TEMPERATURE,
    LLM_MAX_TOKENS,
)

logger = logging.getLogger(__name__)


# ---------- Public API ----------

async def chat(
    slug: str,
    user_message: str,
    api_key: str,
    resume_text: str,
    portfolio_data: Dict[str, Any],
    conversation_history: Optional[List[Dict]] = None,
) -> str:
    """Answer a question about a portfolio using context provided from the database."""
    
    # Build a rich context from the structured portfolio data
    context_parts = []
    if portfolio_data.get("name"):
        context_parts.append(f"Name: {portfolio_data['name']}")
    if portfolio_data.get("role"):
        context_parts.append(f"Role: {portfolio_data['role']}")
    if portfolio_data.get("bio"):
        context_parts.append(f"Bio: {portfolio_data['bio']}")
    
    # Skills - handle None and non-list
    skills = portfolio_data.get("skills")
    if skills and isinstance(skills, list):
        context_parts.append(f"Skills: {', '.join(skills)}")
    
    # Experience - handle None and non-list
    experience = portfolio_data.get("experience")
    if experience and isinstance(experience, list):
        exp_lines = []
        for e in experience:
            if isinstance(e, dict):
                exp_lines.append(
                    f"  - {e.get('role', '')} at {e.get('company', '')} ({e.get('duration', '')}): {e.get('description', '')}"
                )
        if exp_lines:
            context_parts.append("Experience:\n" + "\n".join(exp_lines))
        
    # Projects - handle None and non-list
    projects = portfolio_data.get("projects")
    if projects and isinstance(projects, list):
        proj_lines = []
        for p in projects:
            if isinstance(p, dict):
                techs = ", ".join(p.get("technologies", [])) if isinstance(p.get("technologies"), list) else ""
                proj_lines.append(
                    f"  - {p.get('title', '')}: {p.get('description', '')} [Technologies: {techs}]"
                )
        if proj_lines:
            context_parts.append("Projects:\n" + "\n".join(proj_lines))
        
    # Education - handle None and non-list
    education = portfolio_data.get("education")
    if education and isinstance(education, list):
        edu_lines = []
        for ed in education:
            if isinstance(ed, dict):
                edu_lines.append(
                    f"  - {ed.get('degree', '')} from {ed.get('institution', '')} ({ed.get('year', '')})"
                )
        if edu_lines:
            context_parts.append("Education:\n" + "\n".join(edu_lines))
        
    # Achievements - handle None and non-list
    achievements = portfolio_data.get("achievements")
    if achievements and isinstance(achievements, list):
        context_parts.append("Achievements:\n" + "\n".join(f"  - {a}" for a in achievements if a))
        
    # Contact - handle None and non-dict
    contact = portfolio_data.get("contact")
    if contact and isinstance(contact, dict):
        contact_str = ", ".join(f"{k}: {v}" for k, v in contact.items() if v)
        if contact_str:
            context_parts.append(f"Contact Info: {contact_str}")

    # Final context fallback to raw text if structured data is sparse
    if len(context_parts) < 3:
        context = (resume_text or "")[:4000]
    else:
        context = "\n\n".join(context_parts)

    # Build system prompt
    system_prompt = (
        "You are an AI assistant representing a professional's portfolio. "
        "Answer questions about the candidate based on their resume information provided below. "
        "Be concise, professional, and helpful. If information is not available, say so politely.\n\n"
        f"=== CANDIDATE PORTFOLIO INFO ===\n{context}\n=== END INFO ==="
    )

    # Build a consolidated prompt to ensure compatibility with all models
    consolidated_prompt = (
        f"{system_prompt}\n\n"
        "--- Conversation History ---\n"
    )
    
    if conversation_history:
        for turn in conversation_history[-6:]:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            if content:
                consolidated_prompt += f"{role.upper()}: {content}\n"
    
    consolidated_prompt += f"\nUSER: {user_message}\nASSISTANT:"

    # Hardcode the Gemini API key as requested by the user
    
    payload = {
        "contents": [{
            "parts": [{"text": consolidated_prompt}]
        }]
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                gemini_url,
                headers={"Content-Type": "application/json"},
                json=payload,
            )
            resp.raise_for_status()
        answer = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        logger.info("Chat response for slug '%s': %d chars", slug, len(answer))
        return answer
    except Exception as e:
        logger.error("Chat LLM call failed for slug '%s': %s", slug, e)
        return (
            "I'm sorry, I'm having trouble connecting to my brain right now. "
            "Please try again in a few seconds."
        )

# Kept for compatibility but now no-ops as we are stateless
def index_resume(slug: str, raw_text: str, data: Dict[str, Any]) -> bool:
    return True

def delete_index(slug: str) -> bool:
    return True
