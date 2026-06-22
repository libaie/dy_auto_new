"""内容采集业务域模块。

内容采集业务域，负责采集数据、私信序列、内容生成和实时事件。本文件负责 dm_sequences_router 相关业务规则、状态转换和外部系统边界。
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_role, verify_admin_token, verify_device_secret
from app.domains.content_collection import mutations


router = APIRouter(prefix="/api/dm-sequences", tags=["dm-sequences"])
random = mutations.random
_ORIGINAL_VARIANT_DELAY_MS = mutations._variant_delay_ms


def _variant_delay_ms() -> int:
    """业务函数：处理 _variant_delay_ms 对应的业务流程、校验或数据转换。

    入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return _ORIGINAL_VARIANT_DELAY_MS()


def _sync_legacy_monkeypatch_hooks():
    """业务函数：处理 _sync_legacy_monkeypatch_hooks 对应的业务流程、校验或数据转换。

    入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    mutations.random = random
    mutations._variant_delay_ms = _variant_delay_ms


class SequenceMessage(BaseModel):
    """业务类：承载 SequenceMessage 相关的数据结构、状态或业务协作。

    类参数：content、delay_ms、order 承载该类的业务配置、状态或数据字段。
    """
    order: int
    content: str = Field(..., min_length=1, max_length=500)
    delay_ms: int = Field(default=0, ge=0, le=60000)


class SequenceCreate(BaseModel):
    """业务类：承载 SequenceCreate 相关的数据结构、状态或业务协作。

    类参数：industry、messages、name 承载该类的业务配置、状态或数据字段。
    """
    name: str = Field(..., min_length=1, max_length=100)
    messages: list[SequenceMessage] = Field(..., min_length=1)
    industry: Optional[str] = None


class SequenceUpdate(BaseModel):
    """业务类：承载 SequenceUpdate 相关的数据结构、状态或业务协作。

    类参数：industry、messages、name、variants 承载该类的业务配置、状态或数据字段。
    """
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    messages: Optional[list[SequenceMessage]] = Field(default=None, min_length=1)
    industry: Optional[str] = None
    variants: Optional[list] = None


class DMSequenceGenerateRequest(BaseModel):
    """业务类：承载 DMSequenceGenerateRequest 相关的数据结构、状态或业务协作。

    类参数：description、industry、link_url 承载该类的业务配置、状态或数据字段。
    """
    industry: str = Field(default="general", description="行业key: health/beauty/education/travel/secondhand/general")
    description: str = Field(..., min_length=5, max_length=500, description="大白话描述")
    link_url: str = Field(..., min_length=5, max_length=500, description="消息2的短链URL")


class VariantsGenerateRequest(BaseModel):
    """业务类：承载 VariantsGenerateRequest 相关的数据结构、状态或业务协作。

    类参数：count 承载该类的业务配置、状态或数据字段。
    """
    count: int = Field(default=3, ge=1, le=20, description="生成变体套数")


@router.get("")
def list_sequences(
    industry: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: tuple = Depends(verify_admin_token),
):
    """业务函数：处理 list_sequences 对应的业务流程、校验或数据转换。

    入参：industry、db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return mutations.list_dm_sequences(db, user, industry=industry)


@router.post("")
def create_sequence(
    body: SequenceCreate,
    db: Session = Depends(get_db),
    user: tuple = Depends(require_role("admin")),
):
    """业务函数：处理 create_sequence 对应的业务流程、校验或数据转换。

    入参：body、db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return mutations.create_dm_sequence(db, user, body)


@router.get("/{sequence_id}")
def get_sequence(
    sequence_id: str,
    db: Session = Depends(get_db),
    user: tuple = Depends(verify_admin_token),
):
    """业务函数：处理 get_sequence 对应的业务流程、校验或数据转换。

    入参：sequence_id、db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return mutations.get_dm_sequence(db, user, sequence_id)


@router.put("/{sequence_id}")
def update_sequence(
    sequence_id: str,
    body: SequenceUpdate,
    db: Session = Depends(get_db),
    user: tuple = Depends(require_role("admin")),
):
    """业务函数：处理 update_sequence 对应的业务流程、校验或数据转换。

    入参：sequence_id、body、db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return mutations.update_dm_sequence(db, user, sequence_id, body)


@router.delete("/{sequence_id}")
def delete_sequence(
    sequence_id: str,
    db: Session = Depends(get_db),
    user: tuple = Depends(require_role("admin")),
):
    """业务函数：处理 delete_sequence 对应的业务流程、校验或数据转换。

    入参：sequence_id、db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return mutations.delete_dm_sequence(db, user, sequence_id)


@router.post("/generate")
async def generate_dm_sequence(
    body: DMSequenceGenerateRequest,
    db: Session = Depends(get_db),
    current_user: tuple = Depends(require_role("admin")),
):
    """业务函数：处理 generate_dm_sequence 对应的业务流程、校验或数据转换。

    入参：body、db、current_user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return StreamingResponse(
        await mutations.generate_dm_sequence_events(db, body),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{seq_id}/variants")
async def generate_variants(
    seq_id: str,
    body: VariantsGenerateRequest,
    db: Session = Depends(get_db),
    current_user: tuple = Depends(require_role("admin")),
):
    """业务函数：处理 generate_variants 对应的业务流程、校验或数据转换。

    入参：seq_id、body、db、current_user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    _sync_legacy_monkeypatch_hooks()
    return await mutations.generate_dm_variants(db, seq_id, body)


@router.get("/device/sync")
def device_sync(
    db: Session = Depends(get_db),
    device_id: Optional[str] = Depends(verify_device_secret),
):
    """业务函数：处理 device_sync 对应的业务流程、校验或数据转换。

    入参：db、device_id 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    _sync_legacy_monkeypatch_hooks()
    return mutations.device_sync_dm_sequences(db, device_id)
