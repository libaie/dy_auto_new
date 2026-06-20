import argparse
import asyncio
import os
import sys
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from app.database import SessionLocal
from app.domains.video_production.one_sentence_video_service import create_one_sentence_video
from app.domains.video_production.video_production_run_types import REAL_SHORT_E2E

ALLOW_ENV = "DY_AUTO_ALLOW_REAL_PROVIDER_E2E"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Opt-in real-provider smoke for the one-sentence real short video path."
    )
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--title", default=None)
    parser.add_argument("--budget", required=True, type=float)
    parser.add_argument("--duration", default=60, type=int)
    return parser.parse_args()


async def _main() -> None:
    if os.getenv(ALLOW_ENV) != "1":
        raise SystemExit(
            f"Refusing to call real providers. Set {ALLOW_ENV}=1 to opt in; this consumes provider budget."
        )

    args = _parse_args()
    db = SessionLocal()
    try:
        result = await create_one_sentence_video(
            db,
            prompt=args.prompt,
            title=args.title,
            budget_limit=args.budget,
            target_duration_seconds=args.duration,
            run_type=REAL_SHORT_E2E,
            autostart_images=True,
        )
        run = result["run"]
        print(f"run_id={run.id}")
        print(f"route=/video-production/{run.id}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(_main())
