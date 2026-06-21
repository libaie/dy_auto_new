from pathlib import Path


def test_pipeline_router_does_not_call_pixelle_video_endpoints_directly():
    router = Path("server/app/domains/script_pipeline/pipeline_router.py").read_text()

    assert "/api/video/generate/async" not in router
    assert "/api/video/task/" not in router
