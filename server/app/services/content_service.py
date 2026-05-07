"""Content template and sensitive word service -- DB-backed."""
import json
import re
from typing import Optional

from sqlalchemy.orm import Session

from app.db_models import ContentTemplate as DBTemplate, SensitiveWord as DBWord
from app.models import ContentTemplateResponse, SensitiveWordResponse


def _db_template_to_response(tpl: DBTemplate) -> ContentTemplateResponse:
    return ContentTemplateResponse(
        id=tpl.id,
        name=tpl.name,
        category=tpl.category,
        body=tpl.body,
        variables=tpl.variables or [],
        is_active=tpl.is_active,
        created_at=tpl.created_at,
        updated_at=tpl.updated_at,
    )


def _db_word_to_response(word: DBWord) -> SensitiveWordResponse:
    return SensitiveWordResponse(
        id=word.id,
        word=word.word,
        created_at=word.created_at,
    )


class ContentService:
    """Content template and sensitive word management."""

    # --- Template CRUD ---

    def create_template(
        self, db: Session, name: str, category: str = "comment",
        body: str = "", variables: list[str] | None = None,
    ) -> ContentTemplateResponse:
        tpl = DBTemplate(
            name=name,
            category=category,
            body=body,
            variables=variables or [],
        )
        db.add(tpl)
        db.commit()
        db.refresh(tpl)
        return _db_template_to_response(tpl)

    def get_template(
        self, db: Session, template_id: str, check_active: bool = False,
    ) -> Optional[ContentTemplateResponse]:
        q = db.query(DBTemplate).filter(DBTemplate.id == template_id)
        if check_active:
            q = q.filter(DBTemplate.is_active == True)
        tpl = q.first()
        if not tpl:
            return None
        return _db_template_to_response(tpl)

    def list_templates(
        self, db: Session, category: Optional[str] = None,
        skip: int = 0, limit: int = 50,
    ) -> tuple[list[ContentTemplateResponse], int]:
        q = db.query(DBTemplate)
        if category:
            q = q.filter(DBTemplate.category == category)
        total = q.count()
        templates = q.order_by(DBTemplate.created_at.desc()).offset(skip).limit(limit).all()
        return [_db_template_to_response(t) for t in templates], total

    def update_template(
        self, db: Session, template_id: str, **kwargs
    ) -> Optional[ContentTemplateResponse]:
        """Update template fields. Uses **kwargs for flexibility -- caller (router) passes
        validated data from ContentTemplateUpdate via model_dump(exclude_none=True)."""
        tpl = db.query(DBTemplate).filter(DBTemplate.id == template_id).first()
        if not tpl:
            return None
        for key, value in kwargs.items():
            if value is not None and hasattr(tpl, key):
                setattr(tpl, key, value)
        db.commit()
        db.refresh(tpl)
        return _db_template_to_response(tpl)

    def delete_template(self, db: Session, template_id: str) -> bool:
        tpl = db.query(DBTemplate).filter(DBTemplate.id == template_id).first()
        if not tpl:
            return False
        db.delete(tpl)
        db.commit()
        return True

    # --- Sensitive Word CRUD ---

    def add_sensitive_word(self, db: Session, word: str) -> SensitiveWordResponse:
        existing = db.query(DBWord).filter(DBWord.word == word).first()
        if existing:
            raise ValueError(f"Word '{word}' already exists")
        db_word = DBWord(word=word)
        db.add(db_word)
        db.commit()
        db.refresh(db_word)
        return _db_word_to_response(db_word)

    def list_sensitive_words(
        self, db: Session, skip: int = 0, limit: int = 200,
    ) -> tuple[list[SensitiveWordResponse], int]:
        total = db.query(DBWord).count()
        words = db.query(DBWord).order_by(DBWord.created_at.desc()).offset(skip).limit(limit).all()
        return [_db_word_to_response(w) for w in words], total

    def delete_sensitive_word(self, db: Session, word_id: str) -> bool:
        word = db.query(DBWord).filter(DBWord.id == word_id).first()
        if not word:
            return False
        db.delete(word)
        db.commit()
        return True

    def contains_sensitive(self, db: Session, text: str) -> bool:
        """Check if text contains any sensitive word.

        Loads all words from DB on each call (no cache) to ensure freshness.
        Uses substring match (not word-boundary) -- intentional for Douyin's
        aggressive content policy. False positives trigger a retry, which is
        acceptable since the AI prompt already avoids sensitive content.
        """
        words = [w for (w,) in db.query(DBWord.word).all()]
        return any(word in text for word in words)

    # --- Variable Substitution ---

    @staticmethod
    def substitute_variables(body: str, context: dict[str, str]) -> str:
        """Replace {variable} placeholders in body with context values.
        Missing variables are left unchanged."""
        def replacer(match):
            key = match.group(1)
            return context.get(key, match.group(0))
        return re.sub(r"\{(\w+)\}", replacer, body)

    # --- Content Generation ---

    async def generate_from_template(
        self, db: Session, template_id: str, context: dict[str, str],
    ) -> str:
        """Generate content from a template. Shared by admin, device, and poll resolution.

        Args:
            db: Database session
            template_id: Content template ID
            context: Variable values for substitution (e.g., {"keyword": "美食"})

        Returns:
            Generated content string

        Raises:
            ValueError: If template not found
            RuntimeError: If AI API not configured or all retries fail
        """
        tpl = self.get_template(db, template_id, check_active=True)
        if not tpl:
            raise ValueError(f"Template not found: {template_id}")

        substituted = self.substitute_variables(tpl.body, context)

        return await self._generate_content(db, substituted, context)

    async def _generate_content(
        self, db: Session, template_body: str, context: dict[str, str],
    ) -> str:
        """Delegate to the AI generator service."""
        from app.services.ai_generator import ai_generator
        return await ai_generator.generate(db, template_body, context)

    # --- Keyword Matrix Generation ---

    async def generate_keyword_matrix(self, keyword: str, count: int = 10, db=None) -> list[str]:
        """Generate expanded keyword matrix from a seed keyword using AI."""
        prompt = f"""基于关键词「{keyword}」，生成 {count} 个相关的抖音搜索关键词。
要求：
1. 包含同义词、长尾词、热门话题标签
2. 适合抖音搜索场景
3. 每个关键词 2-8 个字
4. 只返回 JSON 数组格式，不要其他内容
示例：["关键词1", "关键词2", "关键词3"]"""

        from app.services.ai_generator import ai_generator
        response = await ai_generator.generate(db, prompt, {})
        try:
            keywords = json.loads(response)
            if isinstance(keywords, list):
                return [str(k) for k in keywords][:count]
        except (json.JSONDecodeError, TypeError):
            pass
        return [keyword]

    # --- Regex Generation ---

    async def generate_regex(self, db: Session, description: str) -> str:
        """Generate a regex pattern from natural language description."""
        from app.services.ai_generator import ai_generator
        system_prompt = (
            "你是一个正则表达式专家。用户用大白话描述需求，你只返回对应的正则表达式，"
            "不要加引号、不要解释、不要 markdown 代码块。"
        )
        return await ai_generator.generate_custom(
            db, system_prompt,
            f"请生成一个正则表达式：{description}",
            max_tokens=256, temperature=0.2,
            thinking_enabled=False,
        )

    # --- Clean Prompt Generation ---

    async def generate_clean_prompt(self, db: Session, description: str) -> str:
        """Generate an AI cleaning prompt from natural language description."""
        from app.services.ai_generator import ai_generator
        system_prompt = (
            "你是一个数据清洗专家。用户描述需要从一段文本中提取或清洗什么信息，"
            "你返回一个清晰的清洗提示词，这个提示词会被用于 AI 清洗从抖音控件中提取的原始数据。"
            "只返回提示词本身，不要加引号、不要解释、不要 markdown 代码块。"
        )
        return await ai_generator.generate_custom(
            db, system_prompt,
            f"请生成一个清洗提示词：{description}",
            max_tokens=512, temperature=0.3,
            thinking_enabled=False,
        )


content_service = ContentService()
