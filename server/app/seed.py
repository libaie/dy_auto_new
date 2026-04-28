"""Seed database from YAML config files. Idempotent — safe to run multiple times."""
from sqlalchemy.orm import Session

from app.database import SessionLocal, init_db
from app.db_models import Account, UISelector
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


def seed_selectors(db: Session) -> int:
    """Import selectors from selectors.yaml. Skips existing (by action_name + platform_version)."""
    version, selectors = load_selectors_config()
    added = 0
    for sel in selectors:
        existing = db.query(UISelector).filter(
            UISelector.action_name == sel["action_name"],
            UISelector.platform_version == sel.get("platform_version", "default"),
        ).first()
        if existing:
            # Update strategies and version if changed
            existing.strategies = sel["strategies"]
            existing.version = version
            continue
        db.add(UISelector(
            action_name=sel["action_name"],
            platform_version=sel.get("platform_version", "default"),
            strategies=sel["strategies"],
            version=version,
        ))
        added += 1
    db.commit()
    return added


def seed_all():
    """Run all seed operations. Call at startup."""
    init_db()
    db = SessionLocal()
    try:
        acc_count = seed_accounts(db)
        sel_count = seed_selectors(db)
        print(f"Seed complete: {acc_count} accounts added, {sel_count} selectors added")
    finally:
        db.close()


if __name__ == "__main__":
    seed_all()
