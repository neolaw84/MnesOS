#!/usr/bin/env python3
"""Configure GitHub branch protections and labels for a new repository.

Usage:
    python scripts/setup_github_rules.py --repo owner/name
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Any

import requests


@dataclass(frozen=True)
class LabelConfig:
    """Repository label configuration."""

    name: str
    color: str
    description: str


LABELS: tuple[LabelConfig, ...] = (
    LabelConfig(
        name="bump:major",
        color="E11D48",
        description="Breaking change — bump major version",
    ),
    LabelConfig(
        name="bump:minor",
        color="0EA5E9",
        description="New feature — bump minor version (default)",
    ),
    LabelConfig(
        name="bump:patch",
        color="22C55E",
        description="Bug fix — bump patch version",
    ),
)


def get_inferred_repo() -> str | None:
    """Infer the owner/repo from git remote origin."""
    try:
        output = subprocess.check_output(
            ["git", "config", "--get", "remote.origin.url"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except subprocess.CalledProcessError:
        return None
        
    match = re.search(r"github\.com[:/](.+?)(?:\.git)?$", output)
    if match:
        return match.group(1)
    return None


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Set branch protection rules and labels using the GitHub API.",
    )
    parser.add_argument(
        "--repo",
        help="GitHub repository in owner/name format (defaults to inferred current remote).",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("GITHUB_TOKEN", ""),
        help="GitHub personal access token (defaults to GITHUB_TOKEN env var).",
    )
    parser.add_argument(
        "--main-approval-count",
        type=int,
        default=1,
        help="Required approvals for pull requests targeting main (default: 1).",
    )
    parser.add_argument(
        "--dev-approval-count",
        type=int,
        default=1,
        help="Required approvals for pull requests targeting dev (default: 1).",
    )
    return parser.parse_args()


def github_request(
    session: requests.Session,
    method: str,
    url: str,
    *,
    expected_status: tuple[int, ...] = (200,),
    **kwargs: Any,
) -> requests.Response:
    """Make a GitHub API request and validate the response status."""
    response = session.request(method=method, url=url, timeout=30, **kwargs)
    if response.status_code not in expected_status:
        details = response.text.strip()
        raise RuntimeError(
            f"GitHub API error {response.status_code} for {method} {url}: {details}"
        )
    return response


def ensure_dev_branch(session: requests.Session, owner: str, repo: str) -> None:
    """Create dev branch from main if it does not exist."""
    base_url = f"https://api.github.com/repos/{owner}/{repo}"
    dev_ref_url = f"{base_url}/git/ref/heads/dev"

    dev_ref_response = session.get(dev_ref_url, timeout=30)
    if dev_ref_response.status_code == 200:
        print("✓ Branch 'dev' already exists")
        return
    if dev_ref_response.status_code != 404:
        raise RuntimeError(
            f"Failed checking dev branch: {dev_ref_response.status_code} {dev_ref_response.text}"
        )

    main_ref = github_request(
        session,
        "GET",
        f"{base_url}/git/ref/heads/main",
        expected_status=(200,),
    ).json()
    main_sha = main_ref["object"]["sha"]

    github_request(
        session,
        "POST",
        f"{base_url}/git/refs",
        expected_status=(201,),
        json={"ref": "refs/heads/dev", "sha": main_sha},
    )
    print("✓ Created branch 'dev' from 'main'")


def apply_branch_protection(
    session: requests.Session,
    owner: str,
    repo: str,
    branch: str,
    *,
    required_check: str,
    approvals: int,
) -> None:
    """Apply branch protection settings for one branch."""
    url = f"https://api.github.com/repos/{owner}/{repo}/branches/{branch}/protection"
    payload = {
        "required_status_checks": {
            "strict": True,
            "checks": [{"context": required_check}],
        },
        "enforce_admins": True,
        "required_pull_request_reviews": {
            "dismiss_stale_reviews": True,
            "require_code_owner_reviews": False,
            "required_approving_review_count": approvals,
        },
        "restrictions": None,
        "required_linear_history": False,
        "allow_force_pushes": False,
        "allow_deletions": False,
        "block_creations": False,
        "required_conversation_resolution": False,
        "lock_branch": False,
        "allow_fork_syncing": False,
    }
    github_request(
        session,
        "PUT",
        url,
        expected_status=(200,),
        json=payload,
    )
    print(f"✓ Applied branch protection for '{branch}'")


def ensure_labels(session: requests.Session, owner: str, repo: str) -> None:
    """Create or update required labels used by version-bump workflow."""
    base_url = f"https://api.github.com/repos/{owner}/{repo}/labels"
    for label in LABELS:
        get_response = session.get(f"{base_url}/{label.name}", timeout=30)
        payload = {
            "name": label.name,
            "color": label.color,
            "description": label.description,
        }
        if get_response.status_code == 404:
            github_request(
                session,
                "POST",
                base_url,
                expected_status=(201,),
                json=payload,
            )
            print(f"✓ Created label '{label.name}'")
            continue
        if get_response.status_code != 200:
            raise RuntimeError(
                f"Failed checking label '{label.name}': {get_response.status_code} {get_response.text}"
            )

        github_request(
            session,
            "PATCH",
            f"{base_url}/{label.name}",
            expected_status=(200,),
            json=payload,
        )
        print(f"✓ Updated label '{label.name}'")


def set_workflow_permissions(session: requests.Session, owner: str, repo: str) -> None:
    """Set default GITHUB_TOKEN workflow permissions to read/write."""
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/permissions/workflow"
    payload = {
        "default_workflow_permissions": "write",
        "can_approve_pull_request_reviews": False,
    }
    github_request(
        session,
        "PUT",
        url,
        expected_status=(204,),
        json=payload,
    )
    print("✓ Set Actions workflow permissions to read/write")


def parse_repo_slug(repo_slug: str) -> tuple[str, str]:
    """Split owner/repo and validate shape."""
    if "/" not in repo_slug:
        raise ValueError("Expected --repo in owner/name format")
    owner, repo = repo_slug.split("/", 1)
    owner = owner.strip()
    repo = repo.strip()
    if not owner or not repo:
        raise ValueError("Expected --repo in owner/name format")
    return owner, repo


def main() -> int:
    """Entrypoint."""
    args = parse_args()
    if not args.token:
        print("ERROR: Missing token. Pass --token or set GITHUB_TOKEN.", file=sys.stderr)
        return 1

    if args.main_approval_count < 0 or args.dev_approval_count < 0:
        print("ERROR: Approval counts must be non-negative integers.", file=sys.stderr)
        return 1

    repo_slug = args.repo or get_inferred_repo()
    if not repo_slug:
        print("ERROR: Could not infer repository from git. Pass --repo owner/name.", file=sys.stderr)
        return 1

    try:
        owner, repo = parse_repo_slug(repo_slug)
    except ValueError as err:
        print(f"ERROR: {err}", file=sys.stderr)
        return 1

    session = requests.Session()
    session.headers.update(
        {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {args.token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
    )

    try:
        ensure_dev_branch(session, owner, repo)
        apply_branch_protection(
            session,
            owner,
            repo,
            "main",
            required_check="Enforce source branch is dev",
            approvals=args.main_approval_count,
        )
        apply_branch_protection(
            session,
            owner,
            repo,
            "dev",
            required_check="Tests & Coverage",
            approvals=args.dev_approval_count,
        )
        ensure_labels(session, owner, repo)
        set_workflow_permissions(session, owner, repo)
    except RuntimeError as err:
        print(f"ERROR: {err}", file=sys.stderr)
        return 1
    finally:
        session.close()

    print("Done: repository rules and labels have been configured.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
