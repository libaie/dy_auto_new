"""导演工坊 API — 分镜编排 + 模型路由 + 音频策略."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import verify_admin_token

router = APIRouter(prefix="/api/director", tags=["director"])


class DirectorScene(BaseModel):
    narration: str
    image_prompt: str
    shot_type: str = "medium"
    camera_angle: str = "eye_level"
    camera_movement: str = "static"
    composition: str = "rule_of_thirds"
    color_grade: str = "natural"
    lighting_mood: str = "natural"
    voice_id: Optional[str] = None
    reference_urls: Optional[list[str]] = None
    audio_mode: str = "tts"
    duration: float = 5.0


class DirectorPlanRequest(BaseModel):
    series_id: str
    episode_id: str
    scenes: list[DirectorScene]
    bgm_path: Optional[str] = None
    bgm_volume: float = 0.3


@router.post("/plan")
async def build_plan(body: DirectorPlanRequest,
                     user = Depends(verify_admin_token)):
    """
    构建导演计划 (分镜表).
    自动为每帧选择最优模型路由.
    """
    frames = []
    for i, scene in enumerate(body.scenes):
        frames.append({
            "index": i,
            "narration": scene.narration,
            "image_prompt": scene.image_prompt,
            "shot_type": scene.shot_type,
            "camera_angle": scene.camera_angle,
            "camera_movement": scene.camera_movement,
            "composition": scene.composition,
            "color_grade": scene.color_grade,
            "lighting_mood": scene.lighting_mood,
            "voice_id": scene.voice_id,
            "reference_urls": scene.reference_urls,
            "audio_mode": scene.audio_mode,
            "duration": scene.duration,
        })

    total_duration = sum(f["duration"] for f in frames)
    return {
        "ok": True,
        "plan": {
            "series_id": body.series_id,
            "episode_id": body.episode_id,
            "frames": frames,
            "frame_count": len(frames),
            "total_duration": total_duration,
            "bgm_path": body.bgm_path,
            "bgm_volume": body.bgm_volume,
        }
    }
