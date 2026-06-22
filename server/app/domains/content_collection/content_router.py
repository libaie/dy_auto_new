"""内容采集业务域模块。

内容采集业务域，负责采集数据、私信序列、内容生成和实时事件。本文件负责 content_router 相关业务规则、状态转换和外部系统边界。
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional
from sqlalchemy.orm import Session

from app.models import (
    ContentTemplateCreate, ContentTemplateUpdate, ContentTemplateResponse,
    SensitiveWordCreate, SensitiveWordResponse,
    GenerateRequest, GenerateResponse,
    KeywordMatrixRequest,
    GenerateRegexRequest, GenerateCleanPromptRequest,
)
from app.database import get_db
from app.deps import verify_admin_token
from app.domains.content_collection import content_generation, mutations, realtime_events

router = APIRouter(prefix="/api/content", tags=["content"])


# --- Template CRUD ---

@router.post("/templates", response_model=ContentTemplateResponse)
async def create_template(
    request: ContentTemplateCreate,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """业务函数：处理 create_template 对应的业务流程、校验或数据转换。

    入参：request、db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    result = mutations.create_template(db, request)
    await realtime_events.broadcast_content_changed()
    return result


@router.get("/templates")
def list_templates(
    category: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """业务函数：处理 list_templates 对应的业务流程、校验或数据转换。

    入参：category、skip、limit、db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return mutations.list_templates(db, category=category, skip=skip, limit=limit)


@router.get("/templates/{template_id}", response_model=ContentTemplateResponse)
def get_template(
    template_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """业务函数：处理 get_template 对应的业务流程、校验或数据转换。

    入参：template_id、db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    tpl = mutations.get_template(db, template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    return tpl


@router.put("/templates/{template_id}", response_model=ContentTemplateResponse)
async def update_template(
    template_id: str,
    request: ContentTemplateUpdate,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """业务函数：处理 update_template 对应的业务流程、校验或数据转换。

    入参：template_id、request、db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    tpl = mutations.update_template(db, template_id, request)
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    await realtime_events.broadcast_content_changed()
    return tpl


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """业务函数：处理 delete_template 对应的业务流程、校验或数据转换。

    入参：template_id、db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    if not mutations.delete_template(db, template_id):
        raise HTTPException(status_code=404, detail="Template not found")
    await realtime_events.broadcast_content_changed()
    return {"ok": True}


# --- Sensitive Word CRUD ---

@router.post("/sensitive-words", response_model=SensitiveWordResponse)
async def add_sensitive_word(
    request: SensitiveWordCreate,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """业务函数：处理 add_sensitive_word 对应的业务流程、校验或数据转换。

    入参：request、db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    try:
        result = mutations.add_sensitive_word(db, request)
        await realtime_events.broadcast_content_changed()
        return result
    except ValueError:
        raise HTTPException(status_code=409, detail="Word already exists")


@router.get("/sensitive-words")
def list_sensitive_words(
    skip: int = 0,
    limit: int = 200,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """业务函数：处理 list_sensitive_words 对应的业务流程、校验或数据转换。

    入参：skip、limit、db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return mutations.list_sensitive_words(db, skip=skip, limit=limit)


@router.delete("/sensitive-words/{word_id}")
async def delete_sensitive_word(
    word_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """业务函数：处理 delete_sensitive_word 对应的业务流程、校验或数据转换。

    入参：word_id、db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    if not mutations.delete_sensitive_word(db, word_id):
        raise HTTPException(status_code=404, detail="Word not found")
    await realtime_events.broadcast_content_changed()
    return {"ok": True}


# --- AI Generation ---

@router.post("/generate", response_model=GenerateResponse)
async def generate_content(
    request: GenerateRequest,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """业务函数：处理 generate_content 对应的业务流程、校验或数据转换。

    入参：request、db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    try:
        content = await content_generation.generate_from_template(db, request)
    except ValueError as e:
        if "not found" in str(e):
            raise HTTPException(status_code=404, detail="Template not found")
        raise HTTPException(status_code=422, detail=str(e))
    except RuntimeError as e:
        if "not configured" in str(e):
            raise HTTPException(status_code=503, detail="AI service not configured. Set AI_API_KEY environment variable.")
        raise HTTPException(status_code=502, detail=f"AI service error: {e}")

    return GenerateResponse(content=content, template_id=request.template_id)


@router.post("/generate-keywords")
async def generate_keywords(
    request: KeywordMatrixRequest,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """业务函数：处理 generate_keywords 对应的业务流程、校验或数据转换。

    入参：request、db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    try:
        keywords = await content_generation.generate_keywords(db, request)
    except RuntimeError as e:
        if "not configured" in str(e):
            raise HTTPException(status_code=503, detail="AI service not configured.")
        raise HTTPException(status_code=502, detail=f"AI service error: {e}")
    return {"keywords": keywords, "seed": request.keyword}

# --- AI Regex & Clean Prompt Generation ---

@router.post("/generate-regex")
async def generate_regex(
    request: GenerateRegexRequest,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """业务函数：处理 generate_regex 对应的业务流程、校验或数据转换。

    入参：request、db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    try:
        regex = await content_generation.generate_regex(db, request)
    except RuntimeError as e:
        if "not configured" in str(e):
            raise HTTPException(status_code=503, detail="AI service not configured.")
        raise HTTPException(status_code=502, detail=f"AI service error: {e}")
    return {"regex": regex}


@router.post("/generate-clean-prompt")
async def generate_clean_prompt(
    request: GenerateCleanPromptRequest,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """业务函数：处理 generate_clean_prompt 对应的业务流程、校验或数据转换。

    入参：request、db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    try:
        prompt = await content_generation.generate_clean_prompt(db, request)
    except RuntimeError as e:
        if "not configured" in str(e):
            raise HTTPException(status_code=503, detail="AI service not configured.")
        raise HTTPException(status_code=502, detail=f"AI service error: {e}")
    return {"prompt": prompt}
