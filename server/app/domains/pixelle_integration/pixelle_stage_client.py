"""Pixelle 集成业务域模块。

Pixelle 集成业务域，负责 Pixelle provider 配置、代理、阶段任务和客户端调用。本文件负责 pixelle_stage_client 相关业务规则、状态转换和外部系统边界。
"""

import json
import os
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.config import PIXELLE_CONFIG_PATH, SERVER_DIR
from app.domains.pixelle_integration.pixelle_client import _pixelle_request, pixelle_provider_request

_DIRECT_STAGE_RESULTS: dict[str, dict] = {}
_DASHSCOPE_TASK_CONTEXTS: dict[str, dict] = {}


def _model_config_body(model_config: dict | None) -> dict:
    if not isinstance(model_config, dict):
        return {}
    body = dict(model_config.get("config_json") or {})
    body.update(model_config.get("config") or {})
    for key in ("protocol", "task_path", "task_submit_path", "task_query_path", "default_size", "default_resolution"):
        if key in model_config and key not in body:
            body[key] = model_config[key]
    return body


def _model_name(model_config: dict | None) -> str:
    if not isinstance(model_config, dict):
        return ""
    return str(model_config.get("model") or model_config.get("model_name") or "")


def _provider_model_protocol(model_config: dict | None) -> str:
    return str(_model_config_body(model_config).get("protocol") or "").strip()


def _base_url(model_config: dict | None) -> str:
    if not isinstance(model_config, dict):
        return "https://dashscope.aliyuncs.com/api/v1"
    return str(model_config.get("base_url") or "https://dashscope.aliyuncs.com/api/v1")


def _api_key(model_config: dict | None) -> str:
    if not isinstance(model_config, dict):
        return ""
    return str(model_config.get("api_key") or "")


async def _dashscope_request(
    method: str,
    base_url: str,
    path: str,
    api_key: str,
    request_kwargs: dict,
) -> dict:
    kwargs = dict(request_kwargs or {})
    headers = dict(kwargs.pop("headers", {}) or {})
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return await pixelle_provider_request.ainvoke({
        "method": method,
        "base_url": base_url,
        "path": path,
        "api_key": "",
        "request_kwargs": {**kwargs, "headers": headers},
    })


def _first_frame(frames: list[dict]) -> dict:
    return frames[0] if frames else {}


def _frame_id(frame: dict) -> str:
    return str(frame.get("production_segment_id") or frame.get("frame_id") or "")


def _frame_prompt(frame: dict, *keys: str) -> str:
    for key in keys:
        value = frame.get(key)
        if value:
            return str(value)
    return ""


def _stage_task_id(metadata: dict, fallback: str) -> str:
    return str(
        metadata.get("provider_stage_task_id")
        or metadata.get("external_task_id")
        or metadata.get("provider_idempotency_key")
        or fallback
    )


def _safe_filename(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value)[:120] or "compose"


def _local_compose_output_path(stage_task_id: str) -> Path:
    output_root = Path(PIXELLE_CONFIG_PATH).resolve().parent / "output" / "local-compose"
    output_root.mkdir(parents=True, exist_ok=True)
    return output_root / f"{_safe_filename(stage_task_id)}.mp4"


def _is_relative_to(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _local_compose_allowed_roots() -> tuple[Path, ...]:
    return (
        (SERVER_DIR / "output" / "video-production").resolve(),
        (Path(PIXELLE_CONFIG_PATH).resolve().parent / "output").resolve(),
    )


def _assert_local_compose_source_allowed(path: Path) -> None:
    if not any(_is_relative_to(path, root) for root in _local_compose_allowed_roots()):
        raise RuntimeError("Local compose segment path is outside allowed output roots.")


def _segment_video_path(segment: dict) -> Path:
    raw = str(segment.get("video_url") or segment.get("local_path") or segment.get("url") or "").strip()
    if not raw:
        raise RuntimeError("Local compose segment is missing a video path.")
    if len(raw) > 2 and raw[1] == ":" and raw[2] in {"\\", "/"}:
        path = Path(raw)
    else:
        parsed = urlparse(raw)
        if parsed.scheme in {"http", "https"}:
            raise RuntimeError("Local compose requires persisted local video paths.")
        path = Path(parsed.path if parsed.scheme == "file" else raw)
    path = path.resolve()
    if not path.exists() or not path.is_file():
        raise RuntimeError(f"Local compose segment file does not exist: {path}")
    _assert_local_compose_source_allowed(path)
    return path


def _ffmpeg_binary() -> str:
    configured = os.getenv("DY_AUTO_FFMPEG_BINARY")
    if configured and Path(configured).exists():
        return configured
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg

        return str(imageio_ffmpeg.get_ffmpeg_exe())
    except Exception:
        return ""


def _run_ffmpeg(command: list[str]) -> None:
    completed = subprocess.run(command, capture_output=True, text=True, timeout=900)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "ffmpeg failed").strip()[-800:]
        raise RuntimeError(f"ffmpeg compose failed: {detail}")


def _concat_file_line(path: Path) -> str:
    escaped = str(path).replace("\\", "/").replace("'", "'\\''")
    return f"file '{escaped}'\n"


def _compose_segments_with_ffmpeg(segments: list[dict], output_path: Path) -> Path:
    sources = [_segment_video_path(segment) for segment in segments]
    if not sources:
        raise RuntimeError("Local compose requires at least one video segment.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if len(sources) == 1:
        shutil.copyfile(sources[0], output_path)
        return output_path
    ffmpeg = _ffmpeg_binary()
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required for local_ffmpeg_compose.")
    concat_list = output_path.with_suffix(".concat.txt")
    concat_list.write_text("".join(_concat_file_line(path) for path in sources), encoding="utf-8")
    try:
        try:
            _run_ffmpeg([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(output_path)])
        except RuntimeError:
            _run_ffmpeg([
                ffmpeg,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_list),
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-c:a",
                "aac",
                "-movflags",
                "+faststart",
                str(output_path),
            ])
    finally:
        concat_list.unlink(missing_ok=True)
    return output_path


def _asset_base(
    frame: dict,
    provider_task_id: str,
    url: str,
    raw_response: dict,
    *,
    provider_stage_task_id: str | None = None,
) -> dict:
    segment_id = frame.get("production_segment_id") or frame.get("target_id")
    return {
        "frame_id": _frame_id(frame),
        "production_segment_id": segment_id,
        "target_type": "production_segment" if segment_id else None,
        "target_id": segment_id,
        "url": url,
        "source_url": url,
        "provider_task_id": provider_task_id,
        "provider_stage_task_id": provider_stage_task_id or provider_task_id,
        "metadata": {
            "duration": frame.get("duration"),
            "raw_response": raw_response,
        },
    }


def _dashscope_image_urls(response: dict) -> list[str]:
    urls: list[str] = []
    output = response.get("output") if isinstance(response.get("output"), dict) else {}
    choices = output.get("choices") if isinstance(output.get("choices"), list) else []
    for choice in choices:
        message = choice.get("message") if isinstance(choice, dict) else {}
        content = message.get("content") if isinstance(message, dict) else []
        if not isinstance(content, list):
            continue
        for item in content:
            if isinstance(item, dict) and item.get("image"):
                urls.append(str(item["image"]))
    results = output.get("results") if isinstance(output.get("results"), list) else []
    for item in results:
        if isinstance(item, dict):
            url = item.get("url") or item.get("image") or item.get("image_url")
            if url:
                urls.append(str(url))
    return urls


def _dashscope_status(value: str | None) -> str:
    status = str(value or "").lower()
    if status in {"succeeded", "success", "completed", "done"}:
        return "succeeded"
    if status in {"failed", "error"}:
        return "failed"
    if status in {"canceled", "cancelled"}:
        return "cancelled"
    return "running"


def _provider_stage_metadata(
    template_config: dict | None,
    *,
    external_task_id: str | None,
    provider_stage_task_id: str | None,
    provider_idempotency_key: str | None,
) -> dict:
    """业务函数：处理 _provider_stage_metadata 对应的业务流程、校验或数据转换。

    入参：template_config、external_task_id、provider_stage_task_id、provider_idempotency_key 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    template = template_config if isinstance(template_config, dict) else {}
    return {
        "external_task_id": external_task_id or template.get("external_task_id"),
        "provider_stage_task_id": provider_stage_task_id or template.get("provider_stage_task_id"),
        "provider_idempotency_key": provider_idempotency_key or template.get("provider_idempotency_key"),
    }


def _add_provider_stage_metadata(payload: dict, metadata: dict) -> None:
    """业务函数：处理 _add_provider_stage_metadata 对应的业务流程、校验或数据转换。

    入参：payload、metadata 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    for key, value in metadata.items():
        if value:
            payload[key] = value


async def submit_image_batch(
    db: Session | None,
    run_id: str,
    episode_id: str,
    frames: list[dict],
    model_config: dict,
    template_config: dict | None = None,
    external_task_id: str | None = None,
    provider_stage_task_id: str | None = None,
    provider_idempotency_key: str | None = None,
) -> dict:
    """业务函数：处理 submit_image_batch 对应的业务流程、校验或数据转换。

    入参：db、run_id、episode_id、frames、model_config、template_config、external_task_id、provider_stage_task_id、provider_idempotency_key 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    payload = {
        "external_run_id": run_id,
        "episode_id": episode_id,
        "frames": frames,
        "model_config": model_config,
        "template_config": template_config or {},
    }
    _add_provider_stage_metadata(
        payload,
        _provider_stage_metadata(
            template_config,
            external_task_id=external_task_id,
            provider_stage_task_id=provider_stage_task_id,
            provider_idempotency_key=provider_idempotency_key,
        ),
    )
    if _provider_model_protocol(model_config) == "dashscope_multimodal_generation":
        return await _submit_dashscope_image_batch(model_config, frames, payload)
    return await _pixelle_request("POST", "/api/stages/images/batch", db, json=payload)


async def _submit_dashscope_image_batch(model_config: dict, frames: list[dict], payload: dict) -> dict:
    frame = _first_frame(frames)
    config = _model_config_body(model_config)
    if config.get("task_submit_path"):
        return await _submit_dashscope_async_image_batch(model_config, frame, payload, config)
    metadata = _provider_stage_metadata(
        payload.get("template_config"),
        external_task_id=payload.get("external_task_id"),
        provider_stage_task_id=payload.get("provider_stage_task_id"),
        provider_idempotency_key=payload.get("provider_idempotency_key"),
    )
    task_id = _stage_task_id(metadata, f"dashscope-image:{_frame_id(frame)}")
    request_json = {
        "model": _model_name(model_config),
        "input": {
            "messages": [{
                "role": "user",
                "content": [{"text": _frame_prompt(frame, "image_prompt", "prompt")}],
            }],
        },
        "parameters": {
            "size": config.get("default_size") or config.get("size") or "1024*1024",
            "n": 1,
        },
    }
    response = await _dashscope_request(
        "POST",
        _base_url(model_config),
        str(config.get("task_path") or "/services/aigc/multimodal-generation/generation"),
        _api_key(model_config),
        {"json": request_json},
    )
    assets = [
        _asset_base(frame, task_id, url, response)
        for url in _dashscope_image_urls(response)
    ]
    result = {
        "stage_task_id": task_id,
        "provider_task_id": task_id,
        "status": "succeeded" if assets else "failed",
        "assets": assets,
        "usage": response.get("usage") or {},
        "raw_response": response,
    }
    _DIRECT_STAGE_RESULTS[task_id] = result
    return result


async def _submit_dashscope_async_image_batch(
    model_config: dict,
    frame: dict,
    payload: dict,
    config: dict,
) -> dict:
    request_json = {
        "model": _model_name(model_config),
        "input": {
            "messages": [{
                "role": "user",
                "content": [{"text": _frame_prompt(frame, "image_prompt", "prompt")}],
            }],
        },
        "parameters": {
            "size": config.get("default_size") or config.get("size") or "1280*1280",
            "enable_interleave": bool(config.get("enable_interleave", True)),
            "max_images": int(config.get("max_images") or 1),
        },
    }
    response = await _dashscope_request(
        "POST",
        _base_url(model_config),
        str(config.get("task_submit_path")),
        _api_key(model_config),
        {"json": request_json, "headers": {"X-DashScope-Async": "enable"}},
    )
    output = response.get("output") if isinstance(response.get("output"), dict) else {}
    task_id = str(output.get("task_id") or payload.get("provider_stage_task_id") or payload.get("external_task_id") or "")
    if not task_id:
        raise RuntimeError("DashScope image submit response did not include output.task_id")
    _DASHSCOPE_TASK_CONTEXTS[task_id] = {
        "kind": "image",
        "model_config": model_config,
        "frame": frame,
        "provider_stage_task_id": payload.get("provider_stage_task_id"),
        "submit_response": response,
    }
    return {
        "stage_task_id": task_id,
        "provider_task_id": task_id,
        "status": _dashscope_status(output.get("task_status")),
        "raw_response": response,
    }


async def submit_image_create(
    db: Session | None,
    external_task_id: str,
    mode: str,
    capability_key: str,
    output_mode: str = "single",
    prompt: str = "",
    negative_prompt: str = "",
    source_image_url: str = "",
    reference_images: list[dict] | None = None,
    count: int = 1,
    size: str = "",
    output_format: str = "",
    response_format: str = "",
    provider_options: dict | None = None,
    model_config: dict | None = None,
    context: dict | None = None,
) -> dict:
    """业务函数：处理 submit_image_create 对应的业务流程、校验或数据转换。

    入参：db、external_task_id、mode、capability_key、output_mode、prompt、negative_prompt、source_image_url、reference_images、count、size、output_format、response_format、provider_options、model_config、context 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    if not model_config:
        raise ValueError("submit_image_create requires a non-empty model_config")

    payload = {
        "external_task_id": external_task_id,
        "mode": mode,
        "capability_key": capability_key,
        "output_mode": output_mode,
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "source_image_url": source_image_url,
        "reference_images": reference_images or [],
        "count": count,
        "size": size,
        "output_format": output_format,
        "response_format": response_format,
        "provider_options": provider_options or {},
        "model_config": model_config,
        "context": context or {},
    }
    return await _pixelle_request("POST", "/api/stages/images/create", db, json=payload)


async def get_stage_task(db: Session | None, stage_task_id: str) -> dict:
    """业务函数：处理 get_stage_task 对应的业务流程、校验或数据转换。

    入参：db、stage_task_id 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    if stage_task_id in _DIRECT_STAGE_RESULTS:
        return _DIRECT_STAGE_RESULTS[stage_task_id]
    if stage_task_id in _DASHSCOPE_TASK_CONTEXTS:
        return await _get_dashscope_stage_task(stage_task_id)
    stored = _stored_provider_stage_result(db, stage_task_id)
    if stored is not None:
        return stored
    return await _pixelle_request("GET", f"/api/stages/tasks/{stage_task_id}", db)


def _stored_provider_stage_result(db: Session | None, stage_task_id: str) -> dict | None:
    if db is None:
        return None
    from app.db.models.video_production import ProviderStageTask

    task = (
        db.query(ProviderStageTask)
        .filter(
            (ProviderStageTask.provider_task_id == stage_task_id)
            | (ProviderStageTask.id == stage_task_id)
        )
        .order_by(ProviderStageTask.updated_at.desc())
        .first()
    )
    if not task:
        return None
    summary = task.response_summary_json or {}
    if isinstance(summary, str):
        try:
            summary = json.loads(summary)
        except json.JSONDecodeError:
            return None
    status = str(summary.get("status") or "").lower() if isinstance(summary, dict) else ""
    if status not in {"succeeded", "completed", "done", "success", "failed", "error", "cancelled", "canceled"}:
        return None
    result = dict(summary)
    result["provider_task_id"] = result.get("provider_task_id") or task.provider_task_id or task.id
    result["stage_task_id"] = result.get("stage_task_id") or task.provider_task_id or task.id
    assets = []
    for asset in result.get("assets") or []:
        if not isinstance(asset, dict):
            continue
        assets.append({
            **asset,
            "provider_task_id": asset.get("provider_task_id") or task.provider_task_id or task.id,
            "provider_stage_task_id": task.id,
        })
    result["assets"] = assets
    return result


async def submit_video_batch(
    db: Session | None,
    run_id: str,
    frames: list[dict],
    model_config: dict,
    template_config: dict | None = None,
    external_task_id: str | None = None,
    provider_stage_task_id: str | None = None,
    provider_idempotency_key: str | None = None,
) -> dict:
    """业务函数：处理 submit_video_batch 对应的业务流程、校验或数据转换。

    入参：db、run_id、frames、model_config、template_config、external_task_id、provider_stage_task_id、provider_idempotency_key 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    payload = {
        "external_run_id": run_id,
        "frames": frames,
        "model_config": model_config,
        "template_config": template_config or {},
    }
    _add_provider_stage_metadata(
        payload,
        _provider_stage_metadata(
            template_config,
            external_task_id=external_task_id,
            provider_stage_task_id=provider_stage_task_id,
            provider_idempotency_key=provider_idempotency_key,
        ),
    )
    if _provider_model_protocol(model_config) == "dashscope_async":
        return await _submit_dashscope_video_batch(model_config, frames, payload)
    return await _pixelle_request("POST", "/api/stages/videos/batch", db, json=payload)


async def _submit_dashscope_video_batch(model_config: dict, frames: list[dict], payload: dict) -> dict:
    frame = _first_frame(frames)
    config = _model_config_body(model_config)
    first_frame_url = (
        frame.get("input_image_url")
        or frame.get("approved_image_url")
        or frame.get("source_url")
        or frame.get("url")
        or frame.get("local_path")
    )
    request_json = {
        "model": _model_name(model_config),
        "input": {
            "prompt": _frame_prompt(frame, "video_prompt", "prompt", "image_prompt"),
            "media": [{"type": "first_frame", "url": first_frame_url}],
        },
        "parameters": {
            "resolution": config.get("default_resolution") or config.get("resolution") or "720P",
            "duration": int(float(frame.get("duration") or config.get("default_duration") or 5)),
            "prompt_extend": bool(config.get("prompt_extend", True)),
        },
    }
    response = await _dashscope_request(
        "POST",
        _base_url(model_config),
        str(config.get("task_submit_path") or "/services/aigc/video-generation/video-synthesis"),
        _api_key(model_config),
        {"json": request_json, "headers": {"X-DashScope-Async": "enable"}},
    )
    output = response.get("output") if isinstance(response.get("output"), dict) else {}
    task_id = str(output.get("task_id") or payload.get("provider_stage_task_id") or payload.get("external_task_id") or "")
    if not task_id:
        raise RuntimeError("DashScope video submit response did not include output.task_id")
    _DASHSCOPE_TASK_CONTEXTS[task_id] = {
        "kind": "video",
        "model_config": model_config,
        "frame": frame,
        "provider_stage_task_id": payload.get("provider_stage_task_id"),
        "submit_response": response,
    }
    return {
        "stage_task_id": task_id,
        "provider_task_id": task_id,
        "status": _dashscope_status(output.get("task_status")),
        "raw_response": response,
    }


async def _get_dashscope_stage_task(stage_task_id: str) -> dict:
    context = _DASHSCOPE_TASK_CONTEXTS[stage_task_id]
    model_config = context["model_config"]
    config = _model_config_body(model_config)
    path_template = str(config.get("task_query_path") or "/tasks/{task_id}")
    response = await _dashscope_request(
        "GET",
        _base_url(model_config),
        path_template.replace("{task_id}", stage_task_id),
        _api_key(model_config),
        {},
    )
    output = response.get("output") if isinstance(response.get("output"), dict) else {}
    status = _dashscope_status(output.get("task_status") or response.get("status"))
    video_url = output.get("video_url") or response.get("video_url")
    assets = []
    if video_url:
        assets.append(
            _asset_base(
                context["frame"],
                stage_task_id,
                str(video_url),
                response,
                provider_stage_task_id=context.get("provider_stage_task_id"),
            )
        )
    elif context.get("kind") == "image":
        assets.extend(
            _asset_base(
                context["frame"],
                stage_task_id,
                url,
                response,
                provider_stage_task_id=context.get("provider_stage_task_id"),
            )
            for url in _dashscope_image_urls(response)
        )
    result = {
        "stage_task_id": stage_task_id,
        "provider_task_id": stage_task_id,
        "status": status,
        "assets": assets,
        "usage": response.get("usage") or {},
        "raw_submit_response": context.get("submit_response"),
        "raw_response": response,
    }
    if status == "failed":
        result["error"] = output.get("message") or output.get("error_message") or response.get("message")
        result["retryable"] = True
    return result


async def submit_compose(
    db: Session | None,
    run_id: str,
    segments: list[dict],
    edit_manifest: dict,
    model_config: dict | None = None,
    external_task_id: str | None = None,
    provider_stage_task_id: str | None = None,
    provider_idempotency_key: str | None = None,
) -> dict:
    """业务函数：处理 submit_compose 对应的业务流程、校验或数据转换。

    入参：db、run_id、segments、edit_manifest、model_config、external_task_id、provider_stage_task_id、provider_idempotency_key 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    if not model_config:
        raise ValueError("submit_compose requires a non-empty model_config")

    payload = {
        "external_run_id": run_id,
        "segments": segments,
        "edit_manifest": edit_manifest,
        "model_config": model_config,
    }
    if external_task_id:
        payload["external_task_id"] = external_task_id
    if provider_stage_task_id:
        payload["provider_stage_task_id"] = provider_stage_task_id
    if provider_idempotency_key:
        payload["provider_idempotency_key"] = provider_idempotency_key
    if _provider_model_protocol(model_config) == "local_ffmpeg_compose":
        return await _submit_local_ffmpeg_compose(run_id, segments, edit_manifest, payload)
    return await _pixelle_request("POST", "/api/stages/compose", db, json=payload)


async def _submit_local_ffmpeg_compose(
    run_id: str,
    segments: list[dict],
    edit_manifest: dict,
    payload: dict,
) -> dict:
    stage_task_id = _stage_task_id(payload, f"{run_id}:local-compose")
    output_path = _compose_segments_with_ffmpeg(segments, _local_compose_output_path(stage_task_id))
    duration = sum(float(segment.get("duration") or 0) for segment in segments)
    asset = {
        "asset_type": "final_video",
        "frame_id": "final",
        "url": str(output_path),
        "source_url": str(output_path),
        "local_path": str(output_path),
        "provider_task_id": stage_task_id,
        "provider_stage_task_id": payload.get("provider_stage_task_id"),
        "metadata": {
            "duration": duration,
            "segment_count": len(segments),
            "edit_manifest": edit_manifest,
        },
    }
    result = {
        "stage_task_id": stage_task_id,
        "provider_task_id": stage_task_id,
        "status": "succeeded",
        "assets": [asset],
        "usage": {"units": {"segments": len(segments)}, "duration": duration},
    }
    _DIRECT_STAGE_RESULTS[stage_task_id] = result
    return result
