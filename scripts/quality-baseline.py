"""Quality baseline: compare video generation before/after refactoring."""
import asyncio
import time
import json
import sys
from pathlib import Path

# Add server to path
sys.path.insert(0, str(Path(__file__).parent.parent / "server"))

TOPICS = [
    "如何提高学习效率",
    "早起习惯的科学依据",
    "人工智能的未来发展趋势",
]


async def run_single(topic: str, label: str) -> dict:
    """Run a single video generation and measure metrics."""
    start = time.monotonic()
    # Replace with actual pipeline call after integration is complete
    elapsed = time.monotonic() - start
    return {
        "topic": topic,
        "label": label,
        "elapsed_s": round(elapsed, 1),
    }


async def main():
    results = []
    for topic in TOPICS:
        print(f"Running: {topic}")
        result = await run_single(topic, "baseline")
        results.append(result)
        print(f"  {result['elapsed_s']}s")

    output = Path(__file__).parent.parent / "quality-baseline.json"
    output.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"Baseline saved to {output}")


if __name__ == "__main__":
    asyncio.run(main())
