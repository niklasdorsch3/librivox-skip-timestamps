"""Validate a contribution's repository.json diff against the base branch."""

import argparse
import json
import sys
from pathlib import Path


def load_json(path: str) -> dict:
    """Load JSON from file. Returns empty dict if file is missing or empty."""
    p = Path(path)
    if not p.exists():
        return {}
    text = p.read_text().strip()
    if not text:
        return {}
    return json.loads(text)


def find_new_chapters(pr_repo: dict, base_repo: dict) -> list:
    """Return chapters in pr_repo whose listen_url is absent from base_repo."""
    base_urls = {
        ch["listen_url"]
        for book in base_repo.values()
        for ch in book.get("chapters", [])
    }
    return [
        ch
        for book in pr_repo.values()
        for ch in book.get("chapters", [])
        if ch["listen_url"] not in base_urls
    ]


def count_verified(chapters: list) -> int:
    """Count chapters with verified=True."""
    return sum(1 for ch in chapters if ch.get("verified", False))


def build_comment(total_new: int, verified: int) -> str:
    """Build the PR comment body."""
    lines = ["## Contribution Validation", ""]

    if total_new == 0:
        lines.append("No new entries in this PR.")
        return "\n".join(lines)

    lines.append(f"New entries: **{total_new}** | Verified: **{verified}**")
    lines.append("")

    warnings = []
    if total_new > 100:
        warnings.append(
            f"⚠️ More than 100 entries ({total_new} found)"
            " — consider splitting into smaller PRs"
        )
    if verified < 10:
        warnings.append(
            f"⚠️ Fewer than 10 verified entries ({verified} found)"
            " — run more books or use `--override`"
        )

    if warnings:
        lines.extend(warnings)
    else:
        lines.append("✓ All checks passed")

    return "\n".join(lines)


def main(pr_repo_path: str = "repository.json", base_repo_path: str | None = None) -> int:
    pr_repo = load_json(pr_repo_path)
    base_repo = load_json(base_repo_path) if base_repo_path else {}

    new_chapters = find_new_chapters(pr_repo, base_repo)
    verified = count_verified(new_chapters)

    print(build_comment(len(new_chapters), verified))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate a repository.json contribution.")
    parser.add_argument("--pr-repo", default="repository.json", help="Path to PR's repository.json")
    parser.add_argument("--base-repo", default=None, help="Path to base branch repository.json")
    args = parser.parse_args()
    sys.exit(main(args.pr_repo, args.base_repo))
