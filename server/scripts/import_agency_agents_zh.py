from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from urllib.request import urlopen
from pathlib import Path


SOURCE_REPO = "https://github.com/jnMetaCode/agency-agents-zh"
SOURCE_COMMIT = "13b8800f6f666e8e10ac64f67f1194d2baeefbe0"
TEAM_VERSION = "agency-agents-zh-video-production-v2"

SERVER_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = SERVER_ROOT / "app" / "data" / "agency_agents_zh"
TARGET_ROOT = DATA_ROOT.resolve()

EXPERTS = [
    {
        "expert_id": "narrative_designer",
        "name_zh": "叙事设计师",
        "role_type": "core",
        "source_path": "game-development/narrative-designer.md",
        "phases": ["storyboard"],
    },
    {
        "expert_id": "visual_storyteller",
        "name_zh": "视觉叙事师",
        "role_type": "core",
        "source_path": "design/design-visual-storyteller.md",
        "phases": ["style_lock", "storyboard", "image_stage", "image_review", "video_stage"],
    },
    {
        "expert_id": "image_prompt_engineer",
        "name_zh": "图像提示词工程师",
        "role_type": "core",
        "source_path": "design/design-image-prompt-engineer.md",
        "phases": ["style_lock", "image_stage", "image_review"],
    },
    {
        "expert_id": "prompt_engineer",
        "name_zh": "提示词工程师",
        "role_type": "core",
        "source_path": "specialized/prompt-engineer.md",
        "phases": ["image_stage", "video_stage"],
    },
    {
        "expert_id": "short_video_editing_coach",
        "name_zh": "短视频剪辑指导师",
        "role_type": "core",
        "source_path": "marketing/marketing-short-video-editing-coach.md",
        "phases": ["style_lock", "storyboard", "video_stage", "video_review", "compose"],
    },
    {
        "expert_id": "douyin_strategist",
        "name_zh": "抖音策略师",
        "role_type": "core",
        "source_path": "marketing/marketing-douyin-strategist.md",
        "phases": ["storyboard", "compose"],
    },
    {
        "expert_id": "video_optimization_specialist",
        "name_zh": "视频优化专家",
        "role_type": "support",
        "source_path": "marketing/marketing-video-optimization-specialist.md",
        "phases": ["video_review", "compose"],
    },
    {
        "expert_id": "reality_checker",
        "name_zh": "现实检验者",
        "role_type": "support",
        "source_path": "testing/testing-reality-checker.md",
        "phases": ["style_lock", "storyboard", "image_stage", "image_review", "video_stage", "video_review", "compose"],
    },
]


def _run_git(args: list[str], cwd: Path | None = None) -> None:
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _raw_url(source_path: str) -> str:
    return (
        "https://raw.githubusercontent.com/jnMetaCode/agency-agents-zh/"
        f"{SOURCE_COMMIT}/{source_path}"
    )


def _safe_data_path(source_path: str) -> Path:
    if Path(source_path).is_absolute():
        raise ValueError(f"source path must be relative: {source_path}")

    target_file = (TARGET_ROOT / source_path).resolve()
    if TARGET_ROOT not in target_file.parents:
        raise ValueError(f"source path escapes data root: {source_path}")
    return target_file


def _copy_from_checkout(checkout: Path, expert: dict) -> Path:
    source_path = expert["source_path"]
    source_file = checkout / source_path
    target_file = _safe_data_path(source_path)
    target_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_file, target_file)
    return target_file


def _download_raw_file(expert: dict) -> Path:
    source_path = expert["source_path"]
    target_file = _safe_data_path(source_path)
    target_file.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(_raw_url(source_path), timeout=60) as response:
        target_file.write_bytes(response.read())
    return target_file


def _remove_obsolete_markdown() -> None:
    expected_files = {_safe_data_path(expert["source_path"]) for expert in EXPERTS}
    for path in DATA_ROOT.rglob("*.md"):
        resolved = path.resolve()
        if resolved not in expected_files:
            resolved.unlink()

    for directory in sorted(
        (path for path in DATA_ROOT.rglob("*") if path.is_dir()),
        key=lambda path: len(path.parts),
        reverse=True,
    ):
        if directory != DATA_ROOT and not any(directory.iterdir()):
            directory.rmdir()


def main() -> None:
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    checkout: Path | None = None
    with tempfile.TemporaryDirectory(prefix="agency-agents-zh-") as checkout_dir:
        try:
            checkout = Path(checkout_dir)
            _run_git(["clone", "--quiet", SOURCE_REPO, str(checkout)])
            _run_git(["checkout", "--quiet", SOURCE_COMMIT], cwd=checkout)
        except (subprocess.CalledProcessError, FileNotFoundError):
            checkout = None

        manifest_experts = []
        for expert in EXPERTS:
            target_file = (
                _copy_from_checkout(checkout, expert)
                if checkout is not None
                else _download_raw_file(expert)
            )

            manifest_experts.append(
                {
                    **expert,
                    "sha256": _sha256(target_file),
                }
            )

        manifest = {
            "source_repo": SOURCE_REPO,
            "source_commit": SOURCE_COMMIT,
            "team_version": TEAM_VERSION,
            "experts": manifest_experts,
        }
        (DATA_ROOT / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        _remove_obsolete_markdown()
        print(f"Wrote {len(manifest_experts)} experts to {DATA_ROOT}")


if __name__ == "__main__":
    main()
