import argparse
import json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--max-duration", type=int, default=5)
    parser.add_argument("--budget-limit", type=float, default=1.0)
    args = parser.parse_args()

    print(
        json.dumps(
            {
                "ok": True,
                "mode": "dry_report",
                "run_id": args.run_id,
                "max_duration": args.max_duration,
                "budget_limit": args.budget_limit,
                "provider_task_id": None,
                "asset_persistence": "not_run",
                "review_status": "not_run",
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
