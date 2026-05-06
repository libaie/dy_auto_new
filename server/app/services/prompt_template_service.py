"""Prompt template management service — backed by SQLAlchemy database."""
from typing import Optional

from sqlalchemy.orm import Session

from app.db_models import PromptTemplate


def _to_dict(tmpl: PromptTemplate) -> dict:
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
    """Device-facing dict — strips admin fields."""
    return {
        "id": tmpl.id,
        "name": tmpl.name,
        "industry": tmpl.industry,
        "content": tmpl.content,
    }


class PromptTemplateService:
    """Prompt template management — DB-backed."""

    def get_all_templates(self, db: Session) -> tuple[int, list[dict]]:
        """Returns (version, templates_list)."""
        templates = db.query(PromptTemplate).filter(PromptTemplate.enabled == True).all()
        if not templates:
            return 0, []
        version = max(t.version for t in templates)
        return version, [_to_device_dict(t) for t in templates]

    def get_version(self, db: Session) -> int:
        """Get current max version across all enabled templates."""
        templates = db.query(PromptTemplate).filter(PromptTemplate.enabled == True).all()
        if not templates:
            return 0
        return max(t.version for t in templates)

    def get_template(self, db: Session, name: str) -> Optional[dict]:
        """Get a single template by name."""
        t = db.query(PromptTemplate).filter(
            PromptTemplate.name == name,
            PromptTemplate.enabled == True,
        ).first()
        if not t:
            return None
        return _to_dict(t)

    @staticmethod
    def _validate_content(content: dict) -> None:
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

    def create_template(self, db: Session, name: str, industry: str,
                        content: dict, description: str = "") -> dict:
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
        db.commit()
        db.refresh(tmpl)
        return _to_dict(tmpl)

    def update_template(self, db: Session, name: str,
                        content: dict = None, industry: str = None,
                        description: str = None) -> dict:
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

        db.commit()
        db.refresh(tmpl)
        return _to_dict(tmpl)

    def delete_template(self, db: Session, name: str) -> bool:
        """Delete a template by name."""
        tmpl = db.query(PromptTemplate).filter(PromptTemplate.name == name).first()
        if not tmpl:
            return False
        db.delete(tmpl)
        db.commit()
        return True

    def toggle_template(self, db: Session, name: str, enabled: bool) -> dict:
        """Enable or disable a template."""
        tmpl = db.query(PromptTemplate).filter(PromptTemplate.name == name).first()
        if not tmpl:
            raise ValueError(f"Template '{name}' not found")

        tmpl.enabled = enabled
        db.commit()
        db.refresh(tmpl)
        return _to_dict(tmpl)

    def list_all_templates(self, db: Session, include_disabled: bool = False) -> list[dict]:
        """List all templates (optionally including disabled ones)."""
        query = db.query(PromptTemplate)
        if not include_disabled:
            query = query.filter(PromptTemplate.enabled == True)
        templates = query.order_by(PromptTemplate.name).all()
        return [_to_dict(t) for t in templates]


# Module-level singleton
prompt_template_service = PromptTemplateService()
