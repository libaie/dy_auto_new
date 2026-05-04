"""Seed database from YAML config files. Idempotent — safe to run multiple times."""
from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from app.database import SessionLocal, init_db
from app.db_models import Account, SensitiveWord, UISelector
from app.config import load_accounts_config, load_selectors_config


def seed_accounts(db: Session) -> int:
    """Import accounts from accounts.yaml. Skips existing (by id)."""
    accounts = load_accounts_config()
    added = 0
    for acc in accounts:
        existing = db.query(Account).filter(Account.id == acc["id"]).first()
        if existing:
            continue
        db.add(Account(
            id=acc["id"],
            nickname=acc.get("nickname", ""),
            douyin_id=acc.get("douyin_id", ""),
            group=acc.get("group", "default"),
            status=acc.get("status", "active"),
            daily_limits=acc.get("daily_limits", {
                "likes": 50, "comments": 20, "follows": 20, "dms": 10, "replies": 15,
            }),
        ))
        added += 1
    db.commit()
    return added


def seed_selectors(db: Session) -> tuple[int, int]:
    """Import selectors from selectors.yaml. Returns (added, updated) counts.

    Only updates strategies if YAML version is higher than the existing version.
    This prevents seed from overwriting manual edits made via the API.
    """
    version, selectors = load_selectors_config()
    added = 0
    updated = 0
    for sel in selectors:
        existing = db.query(UISelector).filter(
            UISelector.action_name == sel["action_name"],
            UISelector.platform_version == sel.get("platform_version", "default"),
        ).first()
        if existing:
            # Only update if YAML version is higher (prevents overwriting manual edits)
            if version > existing.version:
                existing.strategies = sel["strategies"]
                existing.version = version
                updated += 1
            continue
        db.add(UISelector(
            action_name=sel["action_name"],
            platform_version=sel.get("platform_version", "default"),
            strategies=sel["strategies"],
            version=version,
        ))
        added += 1
    db.commit()
    return added, updated


def seed_sensitive_words(db: Session) -> int:
    """Load default sensitive words from YAML config."""
    words_path = Path(__file__).parent.parent / "config" / "sensitive_words.yaml"
    if not words_path.exists():
        return 0
    with open(words_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    words = data.get("words", [])
    added = 0
    for word in words:
        existing = db.query(SensitiveWord).filter(SensitiveWord.word == word).first()
        if not existing:
            db.add(SensitiveWord(word=word))
            added += 1
    db.commit()
    return added


def seed_all():
    """Run all seed operations. Call at startup."""
    init_db()
    db = SessionLocal()
    try:
        acc_count = seed_accounts(db)
        sel_added, sel_updated = seed_selectors(db)
        words_added = seed_sensitive_words(db)
        print(f"Seed complete: {acc_count} accounts added, {sel_added} selectors added, {sel_updated} selectors updated, {words_added} sensitive words added")
    finally:
        db.close()


if __name__ == "__main__":
    seed_all()
