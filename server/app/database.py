"""Database engine, session factory, and FastAPI dependency."""
import os
import logging
from pathlib import Path

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import sessionmaker, Session

from app.db_models import Base

logger = logging.getLogger(__name__)

SERVER_DIR = Path(__file__).parent.parent
DEFAULT_DB_PATH = SERVER_DIR / "app" / "data" / "dy_auto.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")

# SQLite needs check_same_thread=False for FastAPI's multi-threaded request handling
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, echo=False, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def _set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.close()


def configure_engine(target_engine):
    """Install SQLite-only connection settings, also reusable by test engines."""
    if target_engine.dialect.name == "sqlite":
        if not event.contains(target_engine, "connect", _set_sqlite_pragma):
            event.listen(target_engine, "connect", _set_sqlite_pragma)


configure_engine(engine)


def _migrate_add_columns():
    """Add missing columns to existing SQLite tables (safe to call repeatedly)."""
    if not DATABASE_URL.startswith("sqlite"):
        return
    insp = inspect(engine)
    with engine.begin() as conn:
        for table_name, table in Base.metadata.tables.items():
            if table_name not in insp.get_table_names():
                continue
            existing = {col["name"] for col in insp.get_columns(table_name)}
            for col in table.columns:
                if col.name not in existing:
                    col_type = col.type.compile(engine.dialect)
                    nullable = "NULL" if col.nullable else "NOT NULL"
                    default = ""
                    if col.default is not None:
                        default_sql = col.default.arg
                        if isinstance(default_sql, bool):
                            default = f" DEFAULT {1 if default_sql else 0}"
                        elif isinstance(default_sql, str):
                            default = f" DEFAULT '{default_sql}'"
                        elif isinstance(default_sql, (int, float)):
                            default = f" DEFAULT {default_sql}"
                        elif isinstance(default_sql, (list, dict)):
                            import json as _json
                            default = f" DEFAULT '{_json.dumps(default_sql)}'"
                    sql = f"ALTER TABLE {table_name} ADD COLUMN {col.name} {col_type} {nullable}{default}"
                    logger.info(f"Migration: {sql}")
                    conn.execute(text(sql))


def _seed_admin_user():
    """Create default admin user from env vars if users table is empty (idempotent)."""
    import os as _os
    import bcrypt as _bcrypt
    from app.db_models import User

    with SessionLocal() as db:
        if db.query(User).count() == 0:
            username = _os.getenv("ADMIN_USERNAME", "admin")
            password = _os.getenv("ADMIN_PASSWORD", "admin123")
            pw_hash = _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()
            db.add(User(username=username, password_hash=pw_hash, role="admin", nickname="管理员"))
            db.commit()
            logger.info("Seeded default admin user: %s", username)


def _seed_selector_descriptions():
    """Populate empty description fields for known action names (idempotent)."""
    from app.db_models import UISelector

    descriptions = {
        "back_btn": "返回按钮",
        "open_app": "打开抖音 App",
        "video_comment_btn": "视频评论入口按钮（点击打开评论面板）",
        "video_comment_input": "视频评论输入框（需先点击弹出键盘）",
        "search_tab": "搜索标签页入口",
        "search_input": "搜索输入框",
        "search_button": "搜索按钮",
        "search_suggestion": "搜索建议词",
        "search_suggestion_list": "搜索联想词列表容器",
        "search_video_tab": "搜索结果-视频标签页",
        "search_video_list": "搜索结果-视频列表容器",
        "video_tab": "视频标签页",
        "video_author_avatar": "视频作者头像（点击进入主页）",
        "sort_button": "排序按钮",
        "sort_latest": "最新排序选项",
        "sort_most_liked": "最多点赞排序选项",
        "sort_default": "默认排序选项",
        "like_button": "点赞按钮",
        "follow_button": "关注按钮",
        "comment_input": "评论输入框",
        "comment_submit": "评论提交按钮",
        "comment_reply_button": "评论回复按钮",
        "comment_reply_input": "评论回复输入框",
        "comment_reply_submit": "评论回复提交按钮",
        "comment_list": "评论列表容器",
        "comment_text": "评论内容文本",
        "comment_author": "评论作者昵称",
        "comment_time": "评论发布时间",
        "comment_like_count": "评论点赞数",
        "comment_author_avatar": "评论作者头像",
        "message_button": "私信按钮",
        "dm_input": "私信输入框",
        "dm_send": "私信发送按钮",
        "profile_more": "个人主页更多菜单",
    }

    with SessionLocal() as db:
        updated = 0
        for sel in db.query(UISelector).filter(
            (UISelector.description == "") | (UISelector.description.is_(None))
        ).all():
            desc = descriptions.get(sel.action_name, "")
            if desc:
                sel.description = desc
                updated += 1
        if updated:
            db.commit()
            logger.info(f"Seeded {updated} selector descriptions")


def init_db():
    """Apply required migrations and initialize the remaining legacy tables.

    Migration errors deliberately stop startup. The legacy table/column safety
    net may run only after a successful, versioned upgrade.
    """
    # Ensure data directory exists for SQLite
    if DATABASE_URL.startswith("sqlite"):
        Path(DATABASE_URL.replace("sqlite:///", "")).parent.mkdir(parents=True, exist_ok=True)

    from alembic.config import Config
    from alembic import command

    alembic_ini = SERVER_DIR / "alembic.ini"
    if not alembic_ini.is_file():
        raise RuntimeError(f"Required Alembic configuration is missing: {alembic_ini}")
    alembic_cfg = Config(str(alembic_ini))
    command.upgrade(alembic_cfg, "head")
    logger.info("Alembic migrations applied")

    # Safety net: create_all for any tables not in migrations
    Base.metadata.create_all(bind=engine)
    _migrate_add_columns()
    _seed_admin_user()
    _seed_selector_descriptions()


def get_db():
    """FastAPI dependency — yields a DB session per request, auto-closes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
