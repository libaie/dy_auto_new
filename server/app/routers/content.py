"""Content management API — templates, sensitive words, AI generation."""
import logging
from fastapi import APIRouter, HTTPException, Query, Depends

logger = logging.getLogger(__name__)
from typing import Optional
from sqlalchemy.orm import Session

from app.models import (
    ContentTemplateCreate, ContentTemplateUpdate, ContentTemplateResponse,
    SensitiveWordCreate, SensitiveWordResponse,
    GenerateRequest, GenerateResponse,
)
from app.database import get_db
from app.deps import verify_admin_token
from app.services.content_service import content_service
from app.services.ai_generator import ai_generator

router = APIRouter(prefix="/api/content", tags=["content"])


# --- Template CRUD ---

@router.post("/templates", response_model=ContentTemplateResponse)
def create_template(
    request: ContentTemplateCreate,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    return content_service.create_template(
        db, name=request.name, category=request.category,
        body=request.body, variables=request.variables,
    )


@router.get("/templates")
def list_templates(
    category: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    limit = min(limit, 100)
    templates, total = content_service.list_templates(db, category=category, skip=skip, limit=limit)
    return {"templates": templates, "total": total}


@router.get("/templates/{template_id}", response_model=ContentTemplateResponse)
def get_template(
    template_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    tpl = content_service.get_template(db, template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    return tpl


@router.put("/templates/{template_id}", response_model=ContentTemplateResponse)
def update_template(
    template_id: str,
    request: ContentTemplateUpdate,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    updates = request.model_dump(exclude_none=True)
    tpl = content_service.update_template(db, template_id, **updates)
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    return tpl


@router.delete("/templates/{template_id}")
def delete_template(
    template_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    if not content_service.delete_template(db, template_id):
        raise HTTPException(status_code=404, detail="Template not found")
    return {"ok": True}


# --- Sensitive Word CRUD ---

@router.post("/sensitive-words", response_model=SensitiveWordResponse)
def add_sensitive_word(
    request: SensitiveWordCreate,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    try:
        return content_service.add_sensitive_word(db, request.word)
    except ValueError:
        raise HTTPException(status_code=409, detail="Word already exists")


@router.get("/sensitive-words")
def list_sensitive_words(
    skip: int = 0,
    limit: int = 200,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    words, total = content_service.list_sensitive_words(db, skip=skip, limit=limit)
    return {"words": words, "total": total}


@router.delete("/sensitive-words/{word_id}")
def delete_sensitive_word(
    word_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    if not content_service.delete_sensitive_word(db, word_id):
        raise HTTPException(status_code=404, detail="Word not found")
    return {"ok": True}


# --- AI Generation ---

@router.post("/generate", response_model=GenerateResponse)
async def generate_content(
    request: GenerateRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    tpl = content_service.get_template(db, request.template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")

    # Warn if context keys don't match template variables
    if tpl.variables:
        extra_keys = set(request.context.keys()) - set(tpl.variables)
        if extra_keys:
            logger.warning("Generate request has extra context keys not in template %s: %s", tpl.id, extra_keys)

    # Substitute variables first
    substituted = content_service.substitute_variables(tpl.body, request.context)

    try:
        content = await ai_generator.generate(db, substituted, request.context)
    except RuntimeError as e:
        if "not configured" in str(e):
            raise HTTPException(status_code=503, detail="AI service not configured. Set AI_API_KEY environment variable.")
        raise HTTPException(status_code=502, detail=f"AI service error: {e}")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return GenerateResponse(content=content, template_id=request.template_id)
