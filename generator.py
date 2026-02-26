"""Resume PDF extraction and LLM-powered portfolio generation."""

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional

import httpx
from PyPDF2 import PdfReader

from config import OPENROUTER_BASE_URL, DEFAULT_LLM_MODEL, LLM_TEMPERATURE, LLM_MAX_TOKENS

logger = logging.getLogger(__name__)

# Ordered list of fallback models to try if the primary fails
FALLBACK_MODELS: List[str] = [
    "google/gemma-3-12b-it:free",
    "google/gemma-3-4b-it:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "meta-llama/llama-3.2-3b-instruct:free",
    "mistralai/mistral-small-3.1-24b-instruct:free",
    "deepseek/deepseek-r1-0528:free",
    "qwen/qwen3-4b:free",
]


# ---------- PDF text extraction ----------

def extract_text_from_pdf(pdf_path: str) -> str:
    """Read all pages of a PDF and return concatenated text."""
    reader = PdfReader(pdf_path)
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    full_text = "\n".join(pages)
    logger.info("Extracted %d characters from %s", len(full_text), pdf_path)
    return full_text


# ---------- LLM call via OpenRouter ----------

PORTFOLIO_EXTRACTION_PROMPT = """\
You are a professional resume parser. Extract structured information from the resume below and return ONLY valid JSON with exactly these keys.

IMPORTANT: Return ONLY the raw JSON object. No markdown code blocks. No extra text. No explanation before or after.

Required JSON structure:
{
  "name": "Full Name from resume",
  "role": "Current or most recent job title",
  "tagline": "One compelling professional tagline based on their background",
  "bio": "2-3 sentence professional biography written in third person, based strictly on the resume",
  "skills": ["skill1", "skill2", "skill3"],
  "projects": [
    {
      "title": "Project Name",
      "description": "What the project does and your contribution",
      "technologies": ["tech1", "tech2"]
    }
  ],
  "experience": [
    {
      "company": "Company Name",
      "role": "Job Title",
      "duration": "Month Year - Month Year (or Present)",
      "description": "Key responsibilities and achievements in 1-2 sentences"
    }
  ],
  "education": [
    {
      "institution": "University or School Name",
      "degree": "Degree and Field of Study",
      "year": "Graduation year or year range"
    }
  ],
  "achievements": ["Notable achievement or award 1", "Notable achievement 2"],
  "contact": {
    "email": "email@example.com or empty string",
    "phone": "phone number or empty string",
    "linkedin": "full linkedin URL or empty string",
    "github": "full github URL or empty string",
    "website": "personal website URL or empty string"
  }
}

Rules:
- Extract ONLY information explicitly present in the resume. Do NOT invent or assume anything.
- Use empty string "" for missing text fields and empty array [] for missing list fields.
- Skills must be a flat list of individual skill strings.
- If no projects are listed, use an empty array [].

Resume text:
"""


def _fix_json_string(text: str) -> str:
    """Try several strategies to get valid JSON from LLM output."""
    text = text.strip()

    # Strategy 1: Strip markdown code fences (```json ... ``` or ``` ... ```)
    # Handle multi-line fence blocks
    text = re.sub(r"^```(?:json)?\s*\n?", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n?```\s*$", "", text, flags=re.MULTILINE)
    text = text.strip()

    # Strategy 2: Direct JSON parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strategy 3: Find the outermost { ... } block
    match = re.search(r"\{[\s\S]+\}", text)
    if match:
        candidate = match.group()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    # Strategy 4: Try to fix common LLM JSON quirks (trailing commas, unquoted keys)
    # Remove trailing commas before } or ]
    cleaned = re.sub(r",\s*([}\]])", r"\1", text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Strategy 5: Last resort — find JSON inside the text again with cleaned version
    match2 = re.search(r"\{[\s\S]+\}", cleaned)
    if match2:
        try:
            return json.loads(match2.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Cannot extract valid JSON from LLM response. Raw (first 300 chars): {text[:300]}")


def _validate_and_normalise(data: Any, username: str = "") -> Dict[str, Any]:
    """Ensure all required keys are present and have correct types."""
    if not isinstance(data, dict):
        raise ValueError(f"LLM returned non-dict JSON: {type(data)}")

    defaults: Dict[str, Any] = {
        "name": username.title() if username else "Unknown",
        "role": "",
        "tagline": "",
        "bio": "",
        "skills": [],
        "projects": [],
        "experience": [],
        "education": [],
        "achievements": [],
        "contact": {},
    }

    result = {}
    for key, default in defaults.items():
        val = data.get(key, default)
        # Type coercion
        if isinstance(default, list) and not isinstance(val, list):
            val = default
        if isinstance(default, dict) and not isinstance(val, dict):
            val = default
        if isinstance(default, str) and not isinstance(val, str):
            val = str(val) if val else default
        result[key] = val

    return result


async def _call_llm(
    client: httpx.AsyncClient,
    model: str,
    api_key: str,
    prompt: str,
) -> str:
    """Make one LLM API call. Returns raw content string. Raises on failure."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://portfoli-ai.app",
        "X-Title": "Portfoli-AI",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": LLM_TEMPERATURE,
        "max_tokens": LLM_MAX_TOKENS,
    }

    logger.info("Calling LLM model: %s", model)
    resp = await client.post(
        f"{OPENROUTER_BASE_URL}/chat/completions",
        headers=headers,
        json=payload,
        timeout=120.0,
    )

    if resp.status_code == 429:
        raise httpx.HTTPStatusError("Rate limited (429)", request=resp.request, response=resp)

    if resp.status_code != 200:
        body = resp.text[:300]
        logger.error("LLM API error %d for model %s: %s", resp.status_code, model, body)
        raise httpx.HTTPStatusError(
            f"API error {resp.status_code}: {body}",
            request=resp.request,
            response=resp,
        )

    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    logger.info("LLM model %s returned %d chars", model, len(content))
    logger.debug("Raw LLM response: %s", content[:500])
    return content


async def generate_portfolio_data(
    resume_text: str,
    api_key: str,
    model: Optional[str] = None,
    username: str = "",
) -> Dict[str, Any]:
    """Call the LLM (with fallback models) to structure resume text into portfolio JSON."""
    prompt = PORTFOLIO_EXTRACTION_PROMPT + resume_text

    # Build the model list: preferred model first, then fallbacks
    preferred = model or DEFAULT_LLM_MODEL
    models_to_try = [preferred] + [m for m in FALLBACK_MODELS if m != preferred]

    last_error: Optional[Exception] = None

    async with httpx.AsyncClient(timeout=120.0) as client:
        for attempt_model in models_to_try:
            try:
                raw_content = await _call_llm(client, attempt_model, api_key, prompt)

                # Try to parse the response
                parsed = _fix_json_string(raw_content)
                result = _validate_and_normalise(parsed, username)
                logger.info(
                    "Portfolio data extracted successfully with model %s: name=%r, role=%r, skills=%d",
                    attempt_model, result.get("name"), result.get("role"), len(result.get("skills", []))
                )
                return result

            except (httpx.HTTPStatusError, httpx.TimeoutException) as e:
                logger.warning("Model %s failed with HTTP/timeout error: %s — trying next model", attempt_model, e)
                last_error = e
                await asyncio.sleep(1)  # small backoff between model attempts
                continue

            except (ValueError, KeyError) as e:
                logger.warning("Model %s returned unparseable response: %s — trying next model", attempt_model, e)
                last_error = e
                continue

    # All models failed
    raise RuntimeError(
        f"All {len(models_to_try)} LLM models failed. Last error: {last_error}"
    )


import fitz
import os
import uuid
from config import UPLOAD_DIR

def extract_profile_image_from_pdf(pdf_path: str, username: str) -> Optional[str]:
    """Extract the largest image from the first page of the PDF to use as a profile picture."""
    try:
        doc = fitz.open(pdf_path)
        if len(doc) == 0:
            return None
            
        page = doc[0]
        image_list = page.get_images(full=True)
        
        if not image_list:
            return None
            
        # Find the largest image by area (width * height)
        largest_img = None
        max_area = 0
        img_index = 0
        
        for i, img in enumerate(image_list):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            width = base_image["width"]
            height = base_image["height"]
            area = width * height
            
            if area > max_area:
                max_area = area
                largest_img = base_image
                img_index = i
                
        if not largest_img:
            return None
            
        image_bytes = largest_img["image"]
        image_ext = largest_img["ext"]
        
        # Save the image
        filename = f"{username}_profile_{uuid.uuid4().hex[:8]}.{image_ext}"
        filepath = os.path.join(UPLOAD_DIR, filename)
        
        with open(filepath, "wb") as f:
            f.write(image_bytes)
            
        logger.info(f"Extracted profile image saved to {filepath}")
        return f"/uploads/{filename}"
        
    except Exception as e:
        logger.error(f"Failed to extract image from PDF: {e}")
        return None

# ---------- Convenience ----------

async def process_resume(pdf_path: str, api_key: str, model: Optional[str] = None, username: str = "") -> Dict[str, Any]:
    """End-to-end: extract PDF text -> generate structured portfolio data."""
    text = extract_text_from_pdf(pdf_path)
    if not text.strip():
        raise ValueError("No text could be extracted from the uploaded PDF. Please ensure it is a text-based PDF (not a scanned image).")

    logger.info("Extracted %d characters from PDF — sending to LLM", len(text))
    portfolio = await generate_portfolio_data(text, api_key, model, username=username)
    portfolio["_raw_text"] = text
    
    # Extract profile image
    profile_image_url = extract_profile_image_from_pdf(pdf_path, username)
    if profile_image_url:
        portfolio["profile_image_url"] = profile_image_url
        
    return portfolio
