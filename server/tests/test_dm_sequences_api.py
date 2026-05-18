"""DM Sequence template CRUD API tests."""
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
