"""提示词管理业务域模块。

提示词管理业务域，负责提示词模板、改写和版本化配置。本文件负责 prompt_template_service 相关业务规则、状态转换和外部系统边界。
"""

import json
from typing import Optional

from sqlalchemy.orm import Session

from app.db.models.prompt_management import PromptTemplate
from app.db.models.system_configuration import SystemSetting

_TEMPLATES_REVISION_KEY = "prompt_templates_revision"


def _get_tmpl_revision(db: Session) -> int:
    """业务函数：处理 _get_tmpl_revision 对应的业务流程、校验或数据转换。"""
    row = db.query(SystemSetting).filter(SystemSetting.key == _TEMPLATES_REVISION_KEY).first()
    if row and row.value:
        try:
            return int(row.value)
        except ValueError:
            pass
    templates = db.query(PromptTemplate).filter(PromptTemplate.enabled == True).all()
    if not templates:
        return 0
    rev = int(max(t.updated_at for t in templates).timestamp())
    _set_tmpl_revision(db, rev)
    return rev


def _set_tmpl_revision(db: Session, rev: int) -> None:
    """业务函数：处理 _set_tmpl_revision 对应的业务流程、校验或数据转换。"""
    row = db.query(SystemSetting).filter(SystemSetting.key == _TEMPLATES_REVISION_KEY).first()
    if row:
        row.value = str(rev)
    else:
        db.add(SystemSetting(key=_TEMPLATES_REVISION_KEY, value=str(rev)))
    db.flush()


def _bump_tmpl_revision(db: Session) -> int:
    """业务函数：处理 _bump_tmpl_revision 对应的业务流程、校验或数据转换。"""
    rev = _get_tmpl_revision(db) + 1
    _set_tmpl_revision(db, rev)
    return rev


def _to_dict(tmpl: PromptTemplate) -> dict:
    """业务函数：处理 _to_dict 对应的业务流程、校验或数据转换。"""
    return {
        "id": tmpl.id,
        "name": tmpl.name,
        "industry": tmpl.industry,
        "description": tmpl.description or "",
        "content": tmpl.content,
        "version": tmpl.version,
        "enabled": tmpl.enabled,
        "created_at": tmpl.created_at.isoformat() if tmpl.created_at else None,
        "updated_at": tmpl.updated_at.isoformat() if tmpl.updated_at else None,
    }


def _to_device_dict(tmpl: PromptTemplate) -> dict:
    """业务函数：处理 _to_device_dict 对应的业务流程、校验或数据转换。"""
    """Device-facing dict — strips admin fields."""
    return {
        "id": tmpl.id,
        "name": tmpl.name,
        "industry": tmpl.industry,
        "content": tmpl.content,
    }


PROMPT_TEMPLATE_REWRITE_MAX_INSTRUCTION_CHARS = 2000
PROMPT_TEMPLATE_REWRITE_MAX_CONTENT_BYTES = 50 * 1024


class PromptTemplateService:
    """业务类：承载 PromptTemplateService 相关的数据结构、状态或业务协作。"""
    """Prompt template management — DB-backed."""

    def get_all_templates(self, db: Session) -> tuple[int, list[dict]]:
        """业务函数：处理 get_all_templates 对应的业务流程、校验或数据转换。"""
        """Returns (version, templates_list)."""
        templates = db.query(PromptTemplate).filter(PromptTemplate.enabled == True).all()
        if not templates:
            return 0, []
        version = _get_tmpl_revision(db)
        return version, [_to_device_dict(t) for t in templates]

    def get_version(self, db: Session) -> int:
        """业务函数：处理 get_version 对应的业务流程、校验或数据转换。"""
        """Get current prompt templates revision — guaranteed monotonic across all CRUD."""
        return _get_tmpl_revision(db)

    def get_template(self, db: Session, name: str) -> Optional[dict]:
        """业务函数：处理 get_template 对应的业务流程、校验或数据转换。"""
        """Get a single template by name."""
        t = db.query(PromptTemplate).filter(
            PromptTemplate.name == name,
            PromptTemplate.enabled == True,
        ).first()
        if not t:
            return None
        return _to_dict(t)

    # replyExample 中不允许出现的元格式模式
    # 这些模式用于检测"评论'xxx' → 回复：'yyy'"类的元格式
    _REPLY_EXAMPLE_FORBIDDEN = [
        ("→ 回复", "replyExample 中不应包含「→ 回复」元格式，只需写回复正文，不需要标注原文"),
        ("→ 私信", "replyExample 中不应包含「→」箭头标注原文，只需写回复正文"),
        ("评论'", "replyExample 中不应包含「评论'...'」引用原文的写法，只需写回复正文"),
        ('评论"', 'replyExample 中不应包含「评论"..."」引用原文的写法，只需写回复正文'),
    ]

    @classmethod
    def _validate_reply_example(cls, content: dict) -> None:
        """校验 replyExample 不含元格式（评论xxx→回复：xxx 等）。"""
        an = content.get("analysis", {})
        re_example = an.get("replyExample", {})
        if not re_example:
            return
        for key in ("good", "bad"):
            text = re_example.get(key, "")
            if not isinstance(text, str) or not text.strip():
                continue
            for pattern, tip in cls._REPLY_EXAMPLE_FORBIDDEN:
                if pattern in text:
                    raise ValueError(f"replyExample.{key} 格式错误: {tip}。当前值: {text[:80]}")

    @classmethod
    def _validate_content(cls, content: dict) -> None:
        """业务函数：处理 _validate_content 对应的业务流程、校验或数据转换。"""
        """Validate required template content fields. Raises ValueError on mismatch."""
        required = ["identity", "disabledWords", "semanticGuide", "analysis", "localFilter"]
        for field in required:
            if field not in content or not content[field]:
                raise ValueError(f"Missing required field: '{field}'")
        an = content.get("analysis", {})
        if not an.get("intents") or not an.get("scoringRules") or not an.get("replyRules"):
            raise ValueError("analysis must contain intents, scoringRules, replyRules")
        sg = content.get("semanticGuide", {})
        if not sg.get("highValueSignals") or not sg.get("lowValueSignals") or not sg.get("keyExamples"):
            raise ValueError("semanticGuide must contain highValueSignals, lowValueSignals, keyExamples")
        cls._validate_reply_example(content)

    @classmethod
    def _validate_complete_content(cls, content: dict) -> None:
        """业务函数：处理 _validate_complete_content 对应的业务流程、校验或数据转换。"""
        """Validate fields required for a complete generated prompt template."""
        cls._validate_content(content)

        analysis = content.get("analysis", {})
        if not analysis.get("sentiments") or not analysis.get("replyExample") or not analysis.get("tiers"):
            raise ValueError("analysis must contain sentiments, replyExample, tiers")

        video_comment = content.get("videoComment")
        if not video_comment:
            raise ValueError("Missing required field: 'videoComment'")
        if not video_comment.get("context") or not video_comment.get("goal") or not video_comment.get("rules"):
            raise ValueError("videoComment must contain context, goal, rules")

        dm_opener = content.get("dmOpener")
        if not dm_opener:
            raise ValueError("Missing required field: 'dmOpener'")
        if (
            not dm_opener.get("context")
            or not dm_opener.get("identity")
            or not dm_opener.get("goal")
            or not dm_opener.get("style")
            or not dm_opener.get("tierTones")
        ):
            raise ValueError("dmOpener must contain context, identity, goal, style, tierTones")

        dm_stages = content.get("dmStages")
        if not dm_stages:
            raise ValueError("Missing required field: 'dmStages'")
        required_stages = ["qualifying", "nurturing", "converting", "follow_up"]
        for stage in required_stages:
            if not dm_stages.get(stage):
                raise ValueError(f"dmStages must contain {', '.join(required_stages)}")
            stage_config = dm_stages[stage]
            if (
                not stage_config.get("name")
                or not stage_config.get("goal")
                or not stage_config.get("style")
                or not stage_config.get("maxTokens")
            ):
                raise ValueError(f"dmStages.{stage} must contain name, goal, style, maxTokens")

    @classmethod
    def _serialized_content_size(cls, content: dict) -> int:
        """业务函数：处理 _serialized_content_size 对应的业务流程、校验或数据转换。"""
        return len(json.dumps(content, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

    @classmethod
    def validate_rewrite_request(
        cls,
        content,
        instruction,
        max_instruction_chars: int = PROMPT_TEMPLATE_REWRITE_MAX_INSTRUCTION_CHARS,
        max_content_bytes: int = PROMPT_TEMPLATE_REWRITE_MAX_CONTENT_BYTES,
    ) -> str:
        """业务函数：处理 validate_rewrite_request 对应的业务流程、校验或数据转换。"""
        """Validate rewrite input without reading or writing template rows."""
        if not isinstance(instruction, str) or not instruction.strip():
            raise ValueError("instruction is required")
        trimmed_instruction = instruction.strip()
        if len(trimmed_instruction) > max_instruction_chars:
            raise ValueError(f"instruction is too long; max {max_instruction_chars} characters")
        if not isinstance(content, dict):
            raise ValueError("content must be an object")
        if cls._serialized_content_size(content) > max_content_bytes:
            raise ValueError(f"content is too large; max {max_content_bytes} bytes")
        cls._validate_content(content)
        return trimmed_instruction

    @classmethod
    def validate_rewrite_output(cls, content):
        """业务函数：处理 validate_rewrite_output 对应的业务流程、校验或数据转换。"""
        """Validate AI rewritten output before emitting SSE done."""
        if not isinstance(content, dict):
            raise ValueError("rewritten content must be an object")
        cls._validate_complete_content(content)
        return content

    @staticmethod
    def build_rewrite_prompt(industry: str, content: dict, instruction: str) -> str:
        """业务函数：处理 build_rewrite_prompt 对应的业务流程、校验或数据转换。"""
        current_json = json.dumps(content, ensure_ascii=False, indent=2)
        return (
            f"Industry: {industry or 'health'}\n"
            f"User rewrite instruction:\n{instruction}\n\n"
            "Current prompt template JSON:\n"
            f"{current_json}\n\n"
            "Rewrite rules:\n"
            "1. Return the complete rewritten JSON object only.\n"
            "2. Preserve the existing schema and all required fields.\n"
            "3. Apply only the requested change.\n"
            "4. Keep unrelated fields stable where possible.\n"
            "5. Do not return a no-op rewrite. If the current template already "
            "covers the instruction, make a concrete improvement in the directly "
            "related fields while preserving unrelated fields.\n"
            "6. Make changed content operational and specific enough that a "
            "reviewer can identify what changed.\n"
            "7. Do not wrap the JSON in markdown fences.\n"
        )

    def create_template(self, db: Session, name: str, industry: str,
                        content: dict, description: str = "") -> dict:
        """业务函数：处理 create_template 对应的业务流程、校验或数据转换。"""
        """Create a new prompt template."""
        self._validate_content(content)
        existing = db.query(PromptTemplate).filter(PromptTemplate.name == name).first()
        if existing:
            raise ValueError(f"Template '{name}' already exists")

        tmpl = PromptTemplate(
            name=name,
            industry=industry,
            description=description,
            content=content,
            version=1,
        )
        db.add(tmpl)
        _bump_tmpl_revision(db)
        db.commit()
        db.refresh(tmpl)
        return _to_dict(tmpl)

    def update_template(self, db: Session, name: str,
                        content: dict = None, industry: str = None,
                        description: str = None) -> dict:
        """业务函数：处理 update_template 对应的业务流程、校验或数据转换。"""
        """Update an existing template. Auto-bumps version on any change."""
        if content is not None:
            self._validate_content(content)
        tmpl = db.query(PromptTemplate).filter(PromptTemplate.name == name).first()
        if not tmpl:
            raise ValueError(f"Template '{name}' not found")

        if content is not None:
            tmpl.content = content
        if industry is not None:
            tmpl.industry = industry
        if description is not None:
            tmpl.description = description
        tmpl.version = (tmpl.version or 1) + 1

        _bump_tmpl_revision(db)
        db.commit()
        db.refresh(tmpl)
        return _to_dict(tmpl)

    def delete_template(self, db: Session, name: str) -> bool:
        """业务函数：处理 delete_template 对应的业务流程、校验或数据转换。"""
        """Delete a template by name."""
        tmpl = db.query(PromptTemplate).filter(PromptTemplate.name == name).first()
        if not tmpl:
            return False
        db.delete(tmpl)
        _bump_tmpl_revision(db)
        db.commit()
        return True

    def toggle_template(self, db: Session, name: str, enabled: bool) -> dict:
        """业务函数：处理 toggle_template 对应的业务流程、校验或数据转换。"""
        """Enable or disable a template."""
        tmpl = db.query(PromptTemplate).filter(PromptTemplate.name == name).first()
        if not tmpl:
            raise ValueError(f"Template '{name}' not found")

        tmpl.enabled = enabled
        _bump_tmpl_revision(db)
        db.commit()
        db.refresh(tmpl)
        return _to_dict(tmpl)

    def list_all_templates(self, db: Session, include_disabled: bool = False) -> list[dict]:
        """业务函数：处理 list_all_templates 对应的业务流程、校验或数据转换。"""
        """List all templates (optionally including disabled ones)."""
        query = db.query(PromptTemplate)
        if not include_disabled:
            query = query.filter(PromptTemplate.enabled == True)
        templates = query.order_by(PromptTemplate.name).all()
        return [_to_dict(t) for t in templates]


# Module-level singleton
prompt_template_service = PromptTemplateService()
