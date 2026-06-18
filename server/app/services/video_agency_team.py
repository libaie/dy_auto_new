"""Embedded expert team strategy for automated short-video production."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.services.agency_manifest import EXPERT_IDS, get_expert, load_manifest

VIDEO_AGENCY_TEAM_VERSION = "2026-06-14.1"


def _source_metadata(expert_id: str) -> dict[str, str]:
    manifest = load_manifest()
    expert = get_expert(expert_id)
    return {
        "source_path": expert.source_path,
        "source_commit": manifest.source_commit,
        "source_sha256": expert.sha256,
    }


def _phases(expert_id: str) -> list[str]:
    return list(get_expert(expert_id).phases)


_CORE_ROLES = [
    {
        "id": "story_generator",
        "name": "Story Generator",
        "source_role": "story-generator",
        **_source_metadata("story_generator"),
        "phase": _phases("story_generator"),
        "mission": "Generate whole-season story plans, episode cards, continuity handoffs, and foreshadowing ledgers.",
        "directives": [
            "Use locked character and scene IDs instead of inventing untracked assets.",
            "Create episode hooks, goals, conflicts, reversals, and cliffhangers that connect across the season.",
            "Stop at story planning; do not generate second-by-second storyboard shots.",
        ],
    },
    {
        "id": "narrative_designer",
        "name": "Narrative Designer",
        "source_role": "narrative-designer",
        **_source_metadata("narrative_designer"),
        "phase": _phases("narrative_designer"),
        "mission": "Build coherent story arcs, character motivation, scene beats, and long-form continuity.",
        "directives": [
            "Keep each shot tied to a clear narrative beat.",
            "Protect character motivation and episode continuity.",
            "Avoid ornamental scenes that do not advance story or emotion.",
        ],
    },
    {
        "id": "visual_storyteller",
        "name": "Visual Storyteller",
        "source_role": "design-visual-storyteller",
        **_source_metadata("visual_storyteller"),
        "phase": _phases("visual_storyteller"),
        "mission": "Translate story into visual language, style anchors, camera grammar, and emotional imagery.",
        "directives": [
            "Lock style through visible visual evidence, not abstract adjectives.",
            "Preserve scene mood, composition language, and visual story continuity.",
            "Use image and video outputs to tell the story without relying on explanation.",
        ],
    },
    {
        "id": "image_prompt_engineer",
        "name": "Image Prompt Engineer",
        "source_role": "design-image-prompt-engineer",
        **_source_metadata("image_prompt_engineer"),
        "phase": _phases("image_prompt_engineer"),
        "mission": "Protect character, costume, location, lighting, and composition continuity in generated images.",
        "directives": [
            "Anchor character identity and visual style through reference images.",
            "Translate camera, lighting, and composition into provider-ready image prompts.",
            "Keep image prompts precise enough to prevent identity drift.",
        ],
    },
    {
        "id": "prompt_engineer",
        "name": "Prompt Engineer",
        "source_role": "prompt-engineer",
        **_source_metadata("prompt_engineer"),
        "phase": _phases("prompt_engineer"),
        "mission": "Turn visual intent into stable, structured prompts for image and video models.",
        "directives": [
            "Separate subject identity, camera language, action, emotion, and style constraints.",
            "Use locked IDs and reference URLs instead of re-describing assets from scratch.",
            "Keep prompt structure robust across providers and regeneration attempts.",
        ],
    },
    {
        "id": "short_video_editing_coach",
        "name": "Short Video Editing Coach",
        "source_role": "marketing-short-video-editing-coach",
        **_source_metadata("short_video_editing_coach"),
        "phase": _phases("short_video_editing_coach"),
        "mission": "Control pacing, shot rhythm, transitions, captions, and final edit coherence.",
        "directives": [
            "Keep every frame useful for the final cut.",
            "Prefer clear continuity over decorative shots.",
            "Use subtitles, BGM, and transitions as packaging, not distractions.",
        ],
    },
    {
        "id": "douyin_strategist",
        "name": "Douyin Strategist",
        "source_role": "marketing-douyin-strategist",
        **_source_metadata("douyin_strategist"),
        "phase": _phases("douyin_strategist"),
        "mission": "Optimize the first seconds, retention beats, ending CTA, and Douyin-native packaging.",
        "directives": [
            "Open with a concrete conflict or curiosity hook.",
            "Avoid slow setup when the episode can start in motion.",
            "Keep the final output vertical, direct, and easy to understand without context.",
        ],
    },
]

_SUPPORT_ROLES = [
    {
        "id": "video_optimization_specialist",
        "name": "Video Optimization Specialist",
        "source_role": "marketing-video-optimization-specialist",
        **_source_metadata("video_optimization_specialist"),
        "phase": _phases("video_optimization_specialist"),
        "mission": "Improve retention, chapter rhythm, title/cover packaging, and cross-platform video readiness.",
    },
]

_QUALITY_ROLES = [
    {
        "id": "style_lock_quality_reviewer",
        "name": "Style Lock Quality Reviewer",
        "source_role": "style-lock-quality-reviewer",
        **_source_metadata("style_lock_quality_reviewer"),
        "phase": _phases("style_lock_quality_reviewer"),
        "mission": "Verify locked character, scene, visual, audio, subtitle, BGM, and packaging rules before batch production.",
        "directives": ["Block production when style anchors or required reference assets are incomplete."],
    },
    {
        "id": "storyboard_quality_reviewer",
        "name": "Storyboard Quality Reviewer",
        "source_role": "storyboard-quality-reviewer",
        **_source_metadata("storyboard_quality_reviewer"),
        "phase": _phases("storyboard_quality_reviewer"),
        "mission": "Verify storyboard frames are complete, executable, and inherit locked character and scene anchors.",
        "directives": ["Block storyboard handoff when frame fields or continuity notes are missing."],
    },
    {
        "id": "image_stage_quality_reviewer",
        "name": "Image Stage Quality Reviewer",
        "source_role": "image-stage-quality-reviewer",
        **_source_metadata("image_stage_quality_reviewer"),
        "phase": _phases("image_stage_quality_reviewer"),
        "mission": "Verify image generation requests carry reference images, identity anchors, camera, lighting, and provider settings.",
        "directives": ["Block image tasks that omit role anchors or reference-image usage instructions."],
    },
    {
        "id": "image_review_quality_reviewer",
        "name": "Image Review Quality Reviewer",
        "source_role": "image-review-quality-reviewer",
        **_source_metadata("image_review_quality_reviewer"),
        "phase": _phases("image_review_quality_reviewer"),
        "mission": "Verify generated images preserve identity, scene, style, and video-readiness before image-to-video work.",
        "directives": ["Block images with identity drift, scene drift, malformed anatomy, or unusable composition."],
    },
    {
        "id": "video_stage_quality_reviewer",
        "name": "Video Stage Quality Reviewer",
        "source_role": "video-stage-quality-reviewer",
        **_source_metadata("video_stage_quality_reviewer"),
        "phase": _phases("video_stage_quality_reviewer"),
        "mission": "Verify video generation requests include first frames, actions, emotions, duration, and continuity constraints.",
        "directives": ["Block video tasks that try to generate unstable long clips in one request."],
    },
    {
        "id": "video_review_quality_reviewer",
        "name": "Video Review Quality Reviewer",
        "source_role": "video-review-quality-reviewer",
        **_source_metadata("video_review_quality_reviewer"),
        "phase": _phases("video_review_quality_reviewer"),
        "mission": "Verify video clips preserve identity, motion, camera intent, and usable end-frame continuity.",
        "directives": ["Block clips with identity drift, malformed motion, or unusable segment endings."],
    },
    {
        "id": "compose_quality_reviewer",
        "name": "Compose Quality Reviewer",
        "source_role": "compose-quality-reviewer",
        **_source_metadata("compose_quality_reviewer"),
        "phase": _phases("compose_quality_reviewer"),
        "mission": "Verify final edit manifest, packaging, output video, duration, and writeback readiness.",
        "directives": ["Block asset writeback when final video, edit manifest, or review requirements are incomplete."],
    },
]

_QUALITY_GATES = {
    "story_planning": [
        "The season story plan has a clear mainline, promise, and target episode count.",
        "Every episode outline has hook, goal, conflict, reversal, cliffhanger, and previous/next handoff.",
        "Character and scene IDs come from locked assets or approved series links.",
    ],
    "style_lock": [
        "Locked character rules include stable identity, appearance, outfit, voice policy, and reference URLs.",
        "Locked scene rules include location identity, lighting, mood, and reference URLs.",
        "Missing assets are recorded as explicit blockers or warnings.",
    ],
    "storyboard": [
        "Every frame has character_ids, scene_id, reference_urls, image_prompt, narration, duration, audio_mode, and continuity_notes.",
        "The first frame contains a concrete short-video hook.",
        "Frames preserve locked character and scene continuity instead of inventing new assets.",
    ],
    "image_stage": [
        "Every image payload receives the frame reference_urls and locked style constraints.",
        "Image prompts stay aligned with frame narration and continuity notes.",
        "Provider-specific image payloads remain structured and resumable.",
    ],
    "image_review": [
        "Approved images preserve character identity, scene mood, and locked visual style.",
        "Rejected images include actionable redraw or edit directions.",
        "No image advances without evidence that references were respected.",
    ],
    "video_stage": [
        "Every video payload receives the approved image references and locked style constraints.",
        "Video prompts stay aligned with frame narration and continuity notes.",
        "Provider-specific video payloads remain structured and resumable.",
    ],
    "video_review": [
        "Approved clips preserve motion continuity, character identity, and camera intent.",
        "Rejected clips include actionable regeneration directions.",
        "No clip advances if visual drift or malformed motion breaks the sequence.",
    ],
    "compose_preflight": [
        "Approved video clips are complete and ordered for final composition.",
        "The edit manifest contains subtitles, BGM policy, intro/outro, watermark, and output specs needed for rendering.",
        "Composition can start without requiring a final video URL that does not exist yet.",
    ],
    "compose": [
        "Subtitles, BGM, intro/outro, watermark, and output specs are generated from the locked packaging policy.",
        "The edit keeps vertical short-video pacing and avoids dead time.",
        "Final video is written back to the episode and GeneratedVideo library.",
    ],
}


def build_video_agency_team() -> dict[str, Any]:
    return {
        "enabled": True,
        "version": VIDEO_AGENCY_TEAM_VERSION,
        "source": "jnMetaCode/agency-agents-zh role matching",
        "operating_model": "embedded_expert_team",
        "core_roles": deepcopy(_CORE_ROLES),
        "support_roles": deepcopy(_SUPPORT_ROLES),
        "quality_roles": deepcopy(_QUALITY_ROLES),
        "quality_gates": deepcopy(_QUALITY_GATES),
    }


def _team_role_ids(team: dict[str, Any]) -> list[str]:
    roles = (
        list(team.get("core_roles") or []) +
        list(team.get("support_roles") or []) +
        list(team.get("quality_roles") or [])
    )
    return [role.get("id") for role in roles if role.get("id")]


def _is_current_video_agency_team(team: dict[str, Any]) -> bool:
    quality_gates = team.get("quality_gates") or {}
    return (
        team.get("version") == VIDEO_AGENCY_TEAM_VERSION
        and _team_role_ids(team) == list(EXPERT_IDS)
        and set(quality_gates) == set(_QUALITY_GATES)
    )


def ensure_video_agency_team(style_lock: dict[str, Any] | None) -> dict[str, Any]:
    style_lock = style_lock or {}
    team = style_lock.get("agency_team")
    if isinstance(team, dict) and _is_current_video_agency_team(team):
        return team
    current_team = build_video_agency_team()
    if isinstance(style_lock, dict):
        style_lock["agency_team"] = current_team
    return current_team


def summarize_video_agency_team(team: dict[str, Any] | None) -> dict[str, Any]:
    team = team or {}
    core_roles = team.get("core_roles") or []
    support_roles = team.get("support_roles") or []
    quality_roles = team.get("quality_roles") or []
    quality_gates = team.get("quality_gates") or {}
    return {
        "enabled": bool(team.get("enabled")),
        "version": team.get("version", ""),
        "core_role_count": len(core_roles),
        "support_role_count": len(support_roles),
        "quality_role_count": len(quality_roles),
        "quality_gate_count": sum(len(items) for items in quality_gates.values() if isinstance(items, list)),
        "core_roles": [role.get("id") for role in core_roles if role.get("id")],
    }


def build_agency_context(story_bible_or_style_lock: dict[str, Any] | None) -> dict[str, Any]:
    source = story_bible_or_style_lock or {}
    style_lock = source.get("style_lock") if isinstance(source.get("style_lock"), dict) else source
    team = ensure_video_agency_team(style_lock)
    return {
        "enabled": bool(team.get("enabled")),
        "version": team.get("version", ""),
        "operating_model": team.get("operating_model", "embedded_expert_team"),
        "core_roles": [role["id"] for role in team.get("core_roles", []) if role.get("id")],
        "role_brief": [
            {
                "id": role.get("id"),
                "mission": role.get("mission"),
                "directives": role.get("directives", []),
            }
            for role in [
                *team.get("core_roles", []),
                *team.get("support_roles", []),
                *team.get("quality_roles", []),
            ]
            if role.get("id")
        ],
        "quality_gates": deepcopy(team.get("quality_gates", {})),
    }
