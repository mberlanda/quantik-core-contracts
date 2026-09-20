#!/usr/bin/env python3
"""Fail before a release tag is cut, not after.

Three assertions, each reported with the offending value:

1. the tag does not already exist (locally or on the remote) -- exact tags
   never move, so an existing tag is a stop;
2. ``VERSION`` at the ref being tagged equals the tag without its ``v``;
3. every action path downstream repositories reference resolves at that ref.

Standard library only, like the other scripts here.  Exit status is 1 when any
assertion fails; every failure is printed, numbered by assertion.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REQUIRED_ACTION_PATHS = (
    "actions/cross-language-smoke/action.yml",
    "actions/opening-book-consistency/action.yml",
)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=False
    )


def check_tag_absent(repo: Path, tag: str, remote: str | None) -> list[str]:
    failures = []
    local = _git(repo, "rev-parse", "-q", "--verify", f"refs/tags/{tag}")
    if local.returncode == 0:
        failures.append(
            f"[1/3 tag-absent] tag {tag!r} already exists locally at "
            f"{local.stdout.strip()}; exact tags never move"
        )
    if remote:
        listing = _git(repo, "ls-remote", "--tags", remote, f"refs/tags/{tag}")
        if listing.returncode != 0:
            failures.append(
                f"[1/3 tag-absent] could not query remote {remote!r} for tag "
                f"{tag!r}: {listing.stderr.strip()!r}"
            )
        elif listing.stdout.strip():
            failures.append(
                f"[1/3 tag-absent] tag {tag!r} already exists on remote "
                f"{remote!r}: {listing.stdout.split()[0]}; exact tags never move"
            )
    return failures


def check_version(repo: Path, tag: str, ref: str) -> list[str]:
    expected = tag[1:] if tag.startswith("v") else tag
    shown = _git(repo, "show", f"{ref}:VERSION")
    if shown.returncode != 0:
        return [f"[2/3 version] cannot read VERSION at ref {ref!r}: {shown.stderr.strip()!r}"]
    actual = shown.stdout.strip()
    if not tag.startswith("v"):
        return [f"[2/3 version] tag {tag!r} does not start with 'v'"]
    if actual != expected:
        return [
            f"[2/3 version] VERSION at {ref!r} is {actual!r} but tag {tag!r} "
            f"requires {expected!r}"
        ]
    return []


def check_action_paths(repo: Path, ref: str) -> list[str]:
    failures = []
    for path in REQUIRED_ACTION_PATHS:
        if _git(repo, "cat-file", "-e", f"{ref}:{path}").returncode != 0:
            failures.append(
                f"[3/3 action-paths] {path!r} does not exist at ref {ref!r}"
            )
    return failures


def run_preflight(
    repo: Path, tag: str, ref: str = "HEAD", remote: str | None = "origin",
    tag_already_cut: bool = False,
) -> list[str]:
    failures = [] if tag_already_cut else check_tag_absent(repo, tag, remote)
    failures += check_version(repo, tag, ref)
    failures += check_action_paths(repo, ref)
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", required=True, help="tag about to be cut, e.g. v1.4.0")
    parser.add_argument("--ref", default="HEAD", help="commit that would be tagged")
    parser.add_argument("--repo", default=".", type=Path)
    parser.add_argument("--remote", default="origin", help="remote to check for the tag")
    parser.add_argument(
        "--tag-already-cut",
        action="store_true",
        help="skip assertion 1; used when the run was triggered by the tag push itself",
    )
    args = parser.parse_args(argv)
    failures = run_preflight(
        args.repo, args.tag, args.ref, args.remote or None, args.tag_already_cut
    )
    for failure in failures:
        print(f"preflight FAILED {failure}", file=sys.stderr)
    if failures:
        return 1
    print(f"preflight ok: {args.tag} at {args.ref}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
