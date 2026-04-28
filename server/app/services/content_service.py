"""Content template and sensitive word service -- DB-backed."""
import re
import time
from typing import Optional

from sqlalchemy.orm import Session

from app.db_models import ContentTemplate as DBTemplate, SensitiveWord as DBWord
from app.models import ContentTemplateResponse, SensitiveWordResponse

# Sensitive word cache TTL in seconds
_SENSITIVE_WORD_CACHE_TTL = 300  # 5 minutes


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

    def __init__(self):
        self._sensitive_words_cache: list[str] | None = None
        self._sensitive_words_cache_time: float = 0

    def _get_sensitive_words(self, db: Session) -> list[str]:
        """Get sensitive words with in-memory cache (5 min TTL)."""
        now = time.monotonic()
        if self._sensitive_words_cache is not None and (now - self._sensitive_words_cache_time) < _SENSITIVE_WORD_CACHE_TTL:
            return self._sensitive_words_cache
        words = [w for (w,) in db.query(DBWord.word).all()]
        self._sensitive_words_cache = words
        self._sensitive_words_cache_time = now
        return words

    def invalidate_sensitive_word_cache(self):
        """Call after adding/removing sensitive words to force refresh."""
        self._sensitive_words_cache = None

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

    def get_template(self, db: Session, template_id: str) -> Optional[ContentTemplateResponse]:
        tpl = db.query(DBTemplate).filter(DBTemplate.id == template_id).first()
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
        self.invalidate_sensitive_word_cache()
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
        self.invalidate_sensitive_word_cache()
        return True

    def contains_sensitive(self, db: Session, text: str) -> bool:
        """Check if text contains any sensitive word (uses cached word list)."""
        words = self._get_sensitive_words(db)
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


content_service = ContentService()
