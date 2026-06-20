import io
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app.db_models import CollectedComment, CollectedUser, Conversation
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_data_center_tables(db):
    for model in (CollectedComment, CollectedUser, Conversation):
        db.query(model).delete()
    db.commit()
    yield
    for model in (CollectedComment, CollectedUser, Conversation):
        db.query(model).delete()
    db.commit()


def _xlsx_data_rows(response):
    workbook = load_workbook(io.BytesIO(response.content), read_only=True)
    sheet = workbook.active
    return list(sheet.iter_rows(values_only=True))[1:]


def _xlsx_rows(response):
    workbook = load_workbook(io.BytesIO(response.content), read_only=True)
    sheet = workbook.active
    return list(sheet.iter_rows(values_only=True))


def test_export_users_applies_privacy_filter(db):
    db.add_all([
        CollectedUser(
            id="user-private-hz",
            nickname="私密杭州",
            douyin_id="private-hz",
            keyword="旅游",
            ip_location="杭州",
            is_private="是",
            created_at=datetime(2026, 5, 1, 9, 0, 0),
        ),
        CollectedUser(
            id="user-public-hz",
            nickname="公开杭州",
            douyin_id="public-hz",
            keyword="旅游",
            ip_location="杭州",
            is_private="否",
            created_at=datetime(2026, 5, 1, 10, 0, 0),
        ),
        CollectedUser(
            id="user-private-bj",
            nickname="私密北京",
            douyin_id="private-bj",
            keyword="旅游",
            ip_location="北京",
            is_private="是",
            created_at=datetime(2026, 5, 1, 11, 0, 0),
        ),
    ])
    db.commit()

    response = client.get("/api/data/export/users?search=杭州&is_private=yes")

    assert response.status_code == 200
    rows = _xlsx_data_rows(response)
    assert [row[0] for row in rows] == ["私密杭州"]


def test_export_users_searches_ip_location(db):
    db.add_all([
        CollectedUser(
            id="user-ip-hz",
            nickname="用户甲",
            douyin_id="ip-hz",
            ip_location="杭州",
            created_at=datetime(2026, 5, 1, 9, 0, 0),
        ),
        CollectedUser(
            id="user-ip-bj",
            nickname="用户乙",
            douyin_id="ip-bj",
            ip_location="北京",
            created_at=datetime(2026, 5, 1, 10, 0, 0),
        ),
    ])
    db.commit()

    response = client.get("/api/data/export/users?search=杭州")

    assert response.status_code == 200
    rows = _xlsx_data_rows(response)
    assert [row[0] for row in rows] == ["用户甲"]


def test_list_users_searches_source_comment_content(db):
    db.add_all([
        CollectedUser(
            id="user-comment-hz",
            nickname="评论用户甲",
            douyin_id="comment-hz",
            source_comment_content="刚从西湖回来，想找本地向导",
            created_at=datetime(2026, 5, 1, 9, 0, 0),
        ),
        CollectedUser(
            id="user-comment-bj",
            nickname="评论用户乙",
            douyin_id="comment-bj",
            source_comment_content="北京周末看展",
            created_at=datetime(2026, 5, 1, 10, 0, 0),
        ),
    ])
    db.commit()

    response = client.get("/api/data/users?search=西湖")

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["douyin_id"] for item in items] == ["comment-hz"]
    assert items[0]["source_comment_content"] == "刚从西湖回来，想找本地向导"


def test_export_users_includes_source_comment_content(db):
    db.add(
        CollectedUser(
            id="user-export-entry-comment",
            nickname="导出评论用户",
            douyin_id="export-entry-comment",
            source_comment_content="刚从西湖回来，想找本地向导",
            created_at=datetime(2026, 5, 1, 9, 0, 0),
        )
    )
    db.commit()

    response = client.get("/api/data/export/users?search=西湖回来")

    assert response.status_code == 200
    rows = _xlsx_rows(response)
    assert "入口评论" in rows[0]
    comment_index = rows[0].index("入口评论")
    assert rows[1][0] == "导出评论用户"
    assert rows[1][comment_index] == "刚从西湖回来，想找本地向导"


def test_export_users_respects_frontend_sort_for_current_page(db):
    db.add_all([
        CollectedUser(
            id="user-high-fans",
            nickname="高粉",
            douyin_id="high-fans",
            fans_count="1000",
            created_at=datetime(2026, 5, 2, 12, 0, 0),
        ),
        CollectedUser(
            id="user-low-fans",
            nickname="低粉",
            douyin_id="low-fans",
            fans_count="10",
            created_at=datetime(2026, 5, 1, 12, 0, 0),
        ),
    ])
    db.commit()

    response = client.get("/api/data/export/users?sort_by=fans_count&sort_order=asc&skip=0&limit=1")

    assert response.status_code == 200
    rows = _xlsx_data_rows(response)
    assert [row[0] for row in rows] == ["低粉"]


def test_export_users_uses_stable_tiebreaker_for_current_page(db):
    db.add_all([
        CollectedUser(
            id="user-z-same-fans",
            nickname="同粉Z",
            douyin_id="same-fans-z",
            fans_count="100",
            created_at=datetime(2026, 5, 1, 12, 0, 0),
        ),
        CollectedUser(
            id="user-a-same-fans",
            nickname="同粉A",
            douyin_id="same-fans-a",
            fans_count="100",
            created_at=datetime(2026, 5, 1, 12, 0, 0),
        ),
    ])
    db.commit()

    response = client.get("/api/data/export/users?sort_by=fans_count&sort_order=asc&skip=0&limit=1")

    assert response.status_code == 200
    rows = _xlsx_data_rows(response)
    assert [row[0] for row in rows] == ["同粉A"]


def test_export_conversations_uses_list_order_for_current_page(db):
    db.add_all([
        Conversation(
            id="conv-new-updated",
            account_id="acc-1",
            recipient_nickname="最近更新",
            recipient_douyin_id="new-updated",
            current_stage="qualifying",
            status="active",
            last_dm_content="old dm",
            last_dm_at=datetime(2026, 5, 1, 9, 0, 0),
            updated_at=datetime(2026, 5, 2, 9, 0, 0),
        ),
        Conversation(
            id="conv-new-dm",
            account_id="acc-1",
            recipient_nickname="最近私信",
            recipient_douyin_id="new-dm",
            current_stage="qualifying",
            status="active",
            last_dm_content="new dm",
            last_dm_at=datetime(2026, 5, 3, 9, 0, 0),
            updated_at=datetime(2026, 5, 1, 9, 0, 0),
        ),
    ])
    db.commit()

    response = client.get("/api/data/export/conversations?skip=0&limit=1")

    assert response.status_code == 200
    rows = _xlsx_data_rows(response)
    assert [row[0] for row in rows] == ["最近更新"]


def test_export_conversations_uses_stable_tiebreaker_for_current_page(db):
    db.add_all([
        Conversation(
            id="conv-z-same-updated",
            account_id="acc-1",
            recipient_nickname="同更新时间Z",
            recipient_douyin_id="same-updated-z",
            current_stage="qualifying",
            status="active",
            updated_at=datetime(2026, 5, 2, 9, 0, 0),
        ),
        Conversation(
            id="conv-a-same-updated",
            account_id="acc-1",
            recipient_nickname="同更新时间A",
            recipient_douyin_id="same-updated-a",
            current_stage="qualifying",
            status="active",
            updated_at=datetime(2026, 5, 2, 9, 0, 0),
        ),
    ])
    db.commit()

    response = client.get("/api/data/export/conversations?skip=0&limit=1")

    assert response.status_code == 200
    rows = _xlsx_data_rows(response)
    assert [row[0] for row in rows] == ["同更新时间A"]


def test_conversation_list_search_treats_like_wildcards_as_literal_text(db):
    db.add_all([
        Conversation(
            id="conv-literal-percent",
            account_id="acc-1",
            recipient_nickname="百分号%用户",
            recipient_douyin_id="literal-percent",
            current_stage="qualifying",
            status="active",
            updated_at=datetime(2026, 5, 2, 9, 0, 0),
        ),
        Conversation(
            id="conv-without-percent",
            account_id="acc-1",
            recipient_nickname="普通用户",
            recipient_douyin_id="without-percent",
            current_stage="qualifying",
            status="active",
            updated_at=datetime(2026, 5, 1, 9, 0, 0),
        ),
    ])
    db.commit()

    response = client.get("/api/data/conversations?search=%")

    assert response.status_code == 200
    assert [item["recipient_nickname"] for item in response.json()["items"]] == ["百分号%用户"]


def test_export_conversations_search_treats_like_wildcards_as_literal_text(db):
    db.add_all([
        Conversation(
            id="conv-literal-underscore",
            account_id="acc-1",
            recipient_nickname="下划线_用户",
            recipient_douyin_id="literal-underscore",
            current_stage="qualifying",
            status="active",
            updated_at=datetime(2026, 5, 2, 9, 0, 0),
        ),
        Conversation(
            id="conv-without-underscore",
            account_id="acc-1",
            recipient_nickname="普通用户",
            recipient_douyin_id="without-underscore",
            current_stage="qualifying",
            status="active",
            updated_at=datetime(2026, 5, 1, 9, 0, 0),
        ),
    ])
    db.commit()

    response = client.get("/api/data/export/conversations?search=_")

    assert response.status_code == 200
    rows = _xlsx_data_rows(response)
    assert [row[0] for row in rows] == ["下划线_用户"]
