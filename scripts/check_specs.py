from __future__ import annotations

from pathlib import Path


REQUIRED_FILES = [
    "specs/README.md",
    "specs/agents/README.md",
    "specs/agents/planner.md",
    "specs/agents/backend.md",
    "specs/agents/qa.md",
    "specs/agents/ops.md",
]


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    missing = [path for path in REQUIRED_FILES if not (root / path).exists()]
    intents = list((root / "specs" / "intents").glob("*.md"))
    work_items = list((root / "specs" / "work-items").glob("*.md"))
    if missing:
        raise SystemExit(f"Missing spec files: {missing}")
    if not intents:
        raise SystemExit("No intents found")
    if not work_items:
        raise SystemExit("No work items found")
    print("specsmd validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
