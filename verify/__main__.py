"""Entry point for the verification tool — run with: python verify/"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from .candidates import (
    CHAPTERS_TO_VERIFY_FILE,
    REPOSITORY_FILE,
    load_verification_candidates,
    select_chapters,
)
from .server import DEFAULT_PORT, run_verification
from .session import VerificationSession


def _offer_pr(session: VerificationSession) -> None:
    """Offer to commit repository.json and open a PR via gh."""
    titles = sorted({ch.get("title", "") for ch in session.chapters if ch.get("title")})
    title_str = ", ".join(titles[:3])
    if len(titles) > 3:
        title_str += f" and {len(titles) - 3} more"

    commit_msg = f"Add {session.approved} verified chapters from {title_str}"
    pr_title = f"Add {session.approved} verified LibriVox chapters"
    pr_body = (
        "## Summary\n\n"
        f"- Verified {session.approved} chapters from {len(session.chapters)} new entries\n"
        f"- Books: {title_str}\n\n"
        "## Verification\n\n"
        "All entries manually confirmed correct via `verify`."
    )

    answer = input("\nCreate PR now? (y/n): ").strip().lower()
    if answer == "y":
        try:
            subprocess.run(["git", "add", "data/repository.json"], check=True)
            subprocess.run(["git", "commit", "-m", commit_msg], check=True)
            subprocess.run(
                ["gh", "pr", "create", "--title", pr_title, "--body", pr_body],
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            print(f"Error creating PR: {exc}")
            sys.exit(1)
    else:
        print("\nRun these commands to submit manually:")
        print("  git add data/repository.json")
        print(f"  git commit -m {json.dumps(commit_msg)}")
        print(f"  gh pr create --title {json.dumps(pr_title)} --body '...'")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify pipeline output before submitting a PR."
    )
    parser.add_argument(
        "--override",
        action="store_true",
        help="Allow PR creation with fewer than 10 verified chapters (but >= 1).",
    )
    parser.add_argument("--repo-path", type=Path, default=REPOSITORY_FILE)
    parser.add_argument("--verify-file", type=Path, default=CHAPTERS_TO_VERIFY_FILE)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    candidates = select_chapters(load_verification_candidates(args.repo_path, args.verify_file))
    session = run_verification(candidates, args.repo_path, args.verify_file, args.override, args.port)

    if session.status == "denied":
        print(f"\n{session.message}")
        sys.exit(1)

    if session.status == "not_enough":
        print(f"\n{session.message}")
        sys.exit(0)

    if session.status == "complete":
        print(f"\n{session.message}")
        _offer_pr(session)


if __name__ == "__main__":
    main()
