"""DM Sequence template CRUD API tests."""
import json

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db_models import DMSequence
from app.database import get_db


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    gen = app.dependency_overrides[get_db]()
    session = next(gen)
    yield session
    gen.close()


def _clean(db):
    db.query(DMSequence).delete()
    db.commit()


def _create_one(client, **kw):
    resp = client.post("/api/dm-sequences", json={
        "name": kw.get("name", "测试序列"),
        "messages": kw.get("messages", [
            {"order": 1, "content": "你好", "delay_ms": 2000},
            {"order": 2, "content": "在吗", "delay_ms": 3000},
        ]),
        "industry": kw.get("industry", "测试"),
    })
    return resp


# ======== LIST ========


def test_list_empty(db):
    _clean(db)
    with TestClient(app) as c:
        resp = c.get("/api/dm-sequences")
        assert resp.status_code == 200
        assert resp.json()["sequences"] == []


def test_list_with_data(client, db):
    _clean(db)
    _create_one(client, name="序列A")
    _create_one(client, name="序列B")

    resp = client.get("/api/dm-sequences")
    assert resp.status_code == 200
    data = resp.json()["sequences"]
    assert len(data) >= 2


def test_list_filter_by_industry(client, db):
    _clean(db)
    _create_one(client, name="健康话术", industry="健康")
    _create_one(client, name="旅游话术", industry="旅游")

    resp = client.get("/api/dm-sequences?industry=健康")
    assert resp.status_code == 200
    data = resp.json()["sequences"]
    assert all(s["industry"] == "健康" for s in data)


# ======== CREATE ========


def test_create_valid(client, db):
    _clean(db)
    resp = _create_one(client, name="新建序列")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "新建序列"
    assert data["message_count"] == 2
    assert "id" in data


def test_create_empty_messages(client):
    resp = client.post("/api/dm-sequences", json={
        "name": "空序列", "messages": [],
    })
    assert resp.status_code == 422


def test_create_empty_content(client):
    resp = client.post("/api/dm-sequences", json={
        "name": "空内容",
        "messages": [{"order": 1, "content": "", "delay_ms": 1000}],
    })
    assert resp.status_code == 422


def test_create_auto_renumber(client, db):
    _clean(db)
    resp = client.post("/api/dm-sequences", json={
        "name": "乱序",
        "messages": [
            {"order": 5, "content": "第三", "delay_ms": 1000},
            {"order": 1, "content": "第一", "delay_ms": 2000},
            {"order": 99, "content": "第二", "delay_ms": 0},
        ],
    })
    assert resp.status_code == 200
    msgs = resp.json()["messages"]
    assert msgs[0]["order"] == 1
    assert msgs[0]["content"] == "第一"
    assert msgs[1]["order"] == 2
    assert msgs[2]["order"] == 3


def test_auth_required(client):
    from app.deps import verify_admin_token
    app.dependency_overrides.pop(verify_admin_token, None)
    try:
        resp = client.get("/api/dm-sequences")
        assert resp.status_code == 401
    finally:
        app.dependency_overrides[verify_admin_token] = lambda: ("test-user-id", "admin")


# ======== GET detail ========


def test_get_detail(client, db):
    _clean(db)
    create_resp = _create_one(client, name="详情测试")
    seq_id = create_resp.json()["id"]

    resp = client.get(f"/api/dm-sequences/{seq_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "详情测试"
    assert len(resp.json()["messages"]) == 2


def test_get_not_found(client):
    resp = client.get("/api/dm-sequences/nonexistent-id")
    assert resp.status_code == 404


# ======== UPDATE ========


def test_update(client, db):
    _clean(db)
    create_resp = _create_one(client, name="改名前")
    seq_id = create_resp.json()["id"]

    resp = client.put(f"/api/dm-sequences/{seq_id}", json={
        "name": "改名后",
        "messages": [{"order": 1, "content": "新内容", "delay_ms": 5000}],
    })
    assert resp.status_code == 200
    assert resp.json()["name"] == "改名后"
    assert resp.json()["message_count"] == 1


def test_update_not_found(client):
    resp = client.put("/api/dm-sequences/nonexistent-id", json={
        "name": "X", "messages": [{"order": 1, "content": "Y", "delay_ms": 0}],
    })
    assert resp.status_code == 404


# ======== DELETE ========


def test_delete(client, db):
    _clean(db)
    create_resp = _create_one(client, name="待删除")
    seq_id = create_resp.json()["id"]

    resp = client.delete(f"/api/dm-sequences/{seq_id}")
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True

    # Verify gone
    resp2 = client.get(f"/api/dm-sequences/{seq_id}")
    assert resp2.status_code == 404


def test_delete_not_found(client):
    resp = client.delete("/api/dm-sequences/nonexistent-id")
    assert resp.status_code == 404


# ======== Device sync ========


def test_device_poll_includes_dm_sequences(db):
    """Poll response should include dm_sequences for sequence templates."""
    from app.db_models import DMSequence as DS, Device as DBDevice
    from app.config import bj_now

    _clean(db)
    # Create a sequence
    seq = DS(
        name="设备同步测试",
        messages=[{"order": 1, "content": "测试{{keyword}}", "delay_ms": 1000}],
        industry="测试",
    )
    db.add(seq)
    # Create a device for auth
    dev = DBDevice(id="dev-dmseq-test", name="test", device_secret="dmseq-secret",
                   last_seen_at=bj_now())
    db.add(dev)
    db.commit()

    with TestClient(app) as c:
        resp = c.get("/api/device/poll?device_id=dev-dmseq-test",
                     headers={"X-Device-Secret": "dmseq-secret"})
        assert resp.status_code == 200
        data = resp.json()
        assert "dm_sequences" in data
        seqs = data["dm_sequences"]
        assert len(seqs) >= 1
        assert "messages" in seqs[0]


def test_device_sync_keeps_variant_delay_ms_between_1500_and_3000(db, monkeypatch):
    from app.config import DEVICE_SECRET
    from app.db_models import DMSequence as DS

    _clean(db)
    db.add(DS(
        id="seq-variant-delay-sync",
        name="Variant Delay Sync",
        messages=[{"order": 1, "content": "base", "delay_ms": 2000}],
        variants=[[{"order": 1, "content": "variant", "delay_ms": 1500}]],
        industry="general",
    ))
    db.commit()
    monkeypatch.setattr(
        "app.routers.dm_sequences.random.randint",
        lambda low, _high: low,
    )

    with TestClient(app) as c:
        resp = c.get(
            "/api/dm-sequences/device/sync",
            headers={"X-Device-Secret": DEVICE_SECRET},
        )

    assert resp.status_code == 200
    seq = [
        item for item in resp.json()["dm_sequences"]
        if item["id"] == "seq-variant-delay-sync"
    ][0]
    assert 1500 <= seq["variants"][0][0]["delay_ms"] <= 3000


def test_device_sync_randomizes_each_variant_group_delay_ms(db, monkeypatch):
    from app.config import DEVICE_SECRET
    from app.db_models import DMSequence as DS

    _clean(db)
    db.add(DS(
        id="seq-variant-group-random-delay",
        name="Variant Group Random Delay",
        messages=[{"order": 1, "content": "base", "delay_ms": 2000}],
        variants=[
            [
                {"order": 1, "content": "variant 1-1", "delay_ms": 100},
                {"order": 2, "content": "variant 1-2", "delay_ms": 100},
            ],
            [
                {"order": 1, "content": "variant 2-1", "delay_ms": 100},
                {"order": 2, "content": "variant 2-2", "delay_ms": 100},
            ],
        ],
        industry="general",
    ))
    db.commit()
    delays = iter([1500, 1600, 1700, 1800])
    monkeypatch.setattr(
        "app.routers.dm_sequences._variant_delay_ms",
        lambda: next(delays),
    )

    with TestClient(app) as c:
        resp = c.get(
            "/api/dm-sequences/device/sync",
            headers={"X-Device-Secret": DEVICE_SECRET},
        )

    assert resp.status_code == 200
    seq = [
        item for item in resp.json()["dm_sequences"]
        if item["id"] == "seq-variant-group-random-delay"
    ][0]
    synced_delays = [
        message["delay_ms"]
        for variant in seq["variants"]
        for message in variant
    ]
    assert synced_delays == [1500, 1600, 1700, 1800]


# ======== AI generate ========


def _sse_events(response):
    events = []
    for frame in response.text.split("\n\n"):
        frame = frame.strip()
        if not frame.startswith("data: "):
            continue
        events.append(json.loads(frame[6:]))
    return events


def test_generate_normalizes_common_ai_message_fields(client, monkeypatch):
    async def fake_stream(_db, _system_prompt, _user_prompt, **_kwargs):
        yield json.dumps([
            {"order": 1, "message": "开场自然内容", "delay_ms": 2000},
            {"order": 2, "text": "https://t.cn/test", "delay_ms": 1500},
            {"order": 3, "msg": "收尾自然内容", "delay_ms": 2000},
        ], ensure_ascii=False)

    monkeypatch.setattr(
        "app.services.ai_generator.ai_generator.generate_custom_stream",
        fake_stream,
    )

    response = client.post("/api/dm-sequences/generate", json={
        "industry": "general",
        "description": "帮我生成自然的三段私信",
        "link_url": "https://t.cn/test",
    })

    assert response.status_code == 200
    done = [event for event in _sse_events(response) if event["type"] == "done"][0]
    assert [message["content"] for message in done["messages"]] == [
        "开场自然内容",
        "https://t.cn/test",
        "收尾自然内容",
    ]


def test_generate_variants_randomizes_delay_ms_between_1500_and_3000(client, db, monkeypatch):
    _clean(db)
    create_resp = _create_one(client, messages=[
        {"order": 1, "content": "开场原始内容", "delay_ms": 100},
        {"order": 2, "content": "https://t.cn/test", "delay_ms": 100},
        {"order": 3, "content": "收尾原始内容", "delay_ms": 100},
    ])
    seq_id = create_resp.json()["id"]

    async def fake_generate_custom(_db, _system_prompt, _user_prompt, **_kwargs):
        return json.dumps({
            "msg1": "开场变体内容",
            "msg3": "收尾变体内容",
        }, ensure_ascii=False)

    monkeypatch.setattr(
        "app.services.ai_generator.ai_generator.generate_custom",
        fake_generate_custom,
    )

    response = client.post(f"/api/dm-sequences/{seq_id}/variants", json={"count": 1})

    assert response.status_code == 200
    variant = response.json()["variants"][-1]
    assert [message["order"] for message in variant] == [1, 2, 3]
    assert all(1500 <= message["delay_ms"] <= 3000 for message in variant)
    assert any(message["delay_ms"] != 100 for message in variant)


def test_generate_variants_accepts_count_20(client, db, monkeypatch):
    _clean(db)
    create_resp = _create_one(client, messages=[
        {"order": 1, "content": "开场原始内容", "delay_ms": 100},
        {"order": 2, "content": "https://t.cn/test", "delay_ms": 100},
        {"order": 3, "content": "收尾原始内容", "delay_ms": 100},
    ])
    seq_id = create_resp.json()["id"]

    async def fake_generate_custom(_db, _system_prompt, _user_prompt, **_kwargs):
        return json.dumps({
            "msg1": "开场变体内容",
            "msg3": "收尾变体内容",
        }, ensure_ascii=False)

    monkeypatch.setattr(
        "app.services.ai_generator.ai_generator.generate_custom",
        fake_generate_custom,
    )

    response = client.post(f"/api/dm-sequences/{seq_id}/variants", json={"count": 20})

    assert response.status_code == 200
    assert response.json()["variants_count"] == 20
    assert response.json()["total_variants"] == 20
