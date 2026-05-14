#!/usr/bin/env python3
"""atlas-discover — enumerate every repo + assign a tier.

Sources:
  1. `gh repo list Joona-t` (the canonical source — all known repos)
  2. Local filesystem scan (catches WIP repos not pushed yet)

Output: repos.json — list of repo records consumed by atlas-audit.py.

A repo record looks like:
{
  "name": "sparky",
  "url": "https://github.com/Joona-t/sparky",
  "visibility": "private",
  "is_archived": false,
  "stars": 1,
  "primary_language": "Swift",
  "pushed_at": "2026-05-14T...",
  "disk_usage_kb": 2900,
  "tier": 1,
  "tier_reason": "explicit allowlist",
  "local_path": "/Users/darkfire/sparky",
  "missing_local": false
}
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

GH_OWNER = "Joona-t"
DEFAULT_OUTPUT = Path(__file__).parent / "data" / "repos.json"

# Explicit tier allowlists. Anything not listed defaults to Tier 3.
TIER_1 = {
    "glyph-grid-studio",
    "sparky",
    "lovespark-cards-mac",
    "glyph-grid",
    "codex-tui",
    "lovespark-mission-control",
    "primordial",
    "lovespark-ios",
    "tongue-mac",
    "lovespark-reads",
}

TIER_2 = {
    # iOS apps
    "lovespark-rewire-ios",
    "lovespark-focus-blossom-ios",
    "lovespark-cozy-sleep",
    "lovespark-steps-ios",
    "lovespark-mood-ios",
    "lovespark-sensory-shield-ios",
    "lovespark-transition-support",
    # web / portfolio
    "Joona-t.github.io",
    "Learning",
    "lovespark-games",
    "darkfire-null",
    "zarathustra",
    "forging",
    # infrastructure
    "lovespark-suite",
    "lovespark-os",
    "lovespark-brain",
    "lsmemory-hive",
    # research
    "situational-awareness-research",
    "research",
    "axion-physics",
    "blitz-swarm",
    "research-swarm",
    # extras pulled from active development
    "lovespark-a11y-toolkit",
    "lovespark-tracker",
    "lovespark-senate",
    "lovespark-med-tracker-app",
    "lovespark-focus-pro",
    "claudetui",
}

# Where to look for local clones — covers Joona's known workspace layout.
LOCAL_SCAN_ROOTS = [
    "/Users/darkfire",
    "/Users/darkfire/Claude x LoveSpark",
    "/Users/darkfire/Claude x LoveSpark/Extensions",
    "/Users/darkfire/Claude x LoveSpark/Apps & Tools",
    "/Users/darkfire/Claude x LoveSpark/iOS Apps",
    "/Users/darkfire/Claude x LoveSpark/Web Projects",
    "/Users/darkfire/Claude x LoveSpark/Games",
    "/Users/darkfire/forge",
]


def gh_repo_list() -> list[dict]:
    """Pull every repo under GH_OWNER via the gh CLI."""
    fields = "name,description,visibility,isPrivate,isArchived,primaryLanguage,pushedAt,diskUsage,stargazerCount,url"
    cmd = ["gh", "repo", "list", GH_OWNER, "--limit", "500", "--json", fields]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=120)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print(f"[atlas-discover] gh repo list failed: {e}", file=sys.stderr)
        return []
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError as e:
        print(f"[atlas-discover] gh returned non-JSON: {e}", file=sys.stderr)
        return []
    return data


def find_local_path(name: str) -> Path | None:
    """Best-effort lookup: does a clone of `name` exist on disk under known roots?"""
    candidates: list[Path] = []
    for root in LOCAL_SCAN_ROOTS:
        rp = Path(root)
        if not rp.is_dir():
            continue
        # Direct child match
        direct = rp / name
        if direct.is_dir() and (direct / ".git").exists():
            candidates.append(direct)
        # Maxdepth-3 search within roots (skip obvious caches)
        try:
            for d in rp.iterdir():
                if not d.is_dir() or d.name.startswith("."):
                    continue
                if d.name in {"node_modules", "venv", ".venv", "DerivedData", "Pods"}:
                    continue
                # Look at one more level
                for d2 in d.iterdir():
                    if d2.is_dir() and d2.name == name and (d2 / ".git").exists():
                        candidates.append(d2)
        except (OSError, PermissionError):
            continue
    return candidates[0] if candidates else None


def assign_tier(repo: dict) -> tuple[int, str]:
    name = repo.get("name", "")
    if name in TIER_1:
        return 1, "explicit allowlist (Tier 1)"
    if name in TIER_2:
        return 2, "explicit allowlist (Tier 2)"
    return 3, "default tier"


def normalize(record: dict) -> dict:
    """Convert raw gh repo-list output into our atlas record schema."""
    lang = record.get("primaryLanguage") or {}
    visibility = "public" if not record.get("isPrivate") else "private"
    name = record["name"]
    out = {
        "name": name,
        "url": record.get("url", f"https://github.com/{GH_OWNER}/{name}"),
        "description": record.get("description") or "",
        "visibility": visibility,
        "is_archived": bool(record.get("isArchived")),
        "stars": int(record.get("stargazerCount") or 0),
        "primary_language": lang.get("name") if isinstance(lang, dict) else None,
        "pushed_at": record.get("pushedAt"),
        "disk_usage_kb": int(record.get("diskUsage") or 0),
    }
    tier, why = assign_tier(out)
    out["tier"] = tier
    out["tier_reason"] = why
    local = find_local_path(name)
    out["local_path"] = str(local) if local else None
    out["missing_local"] = local is None
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Enumerate repos and assign atlas tiers.")
    ap.add_argument("--output", "-o", type=Path, default=DEFAULT_OUTPUT,
                    help=f"Output JSON path (default: {DEFAULT_OUTPUT})")
    ap.add_argument("--owner", default=GH_OWNER, help="GitHub owner (default: Joona-t)")
    args = ap.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)

    print(f"[atlas-discover] gh repo list {args.owner}…")
    raw = gh_repo_list()
    print(f"[atlas-discover] gh returned {len(raw)} repos")

    repos = [normalize(r) for r in raw]
    repos.sort(key=lambda r: (r["tier"], -(r["disk_usage_kb"] or 0), r["name"].lower()))

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "owner": args.owner,
        "repo_count": len(repos),
        "by_visibility": {
            "public": sum(1 for r in repos if r["visibility"] == "public"),
            "private": sum(1 for r in repos if r["visibility"] == "private"),
        },
        "by_tier": {
            "1": sum(1 for r in repos if r["tier"] == 1),
            "2": sum(1 for r in repos if r["tier"] == 2),
            "3": sum(1 for r in repos if r["tier"] == 3),
        },
        "archived_count": sum(1 for r in repos if r["is_archived"]),
        "missing_local_count": sum(1 for r in repos if r["missing_local"]),
        "repos": repos,
    }

    args.output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"[atlas-discover] wrote {args.output}")
    print(f"  Tier 1: {manifest['by_tier']['1']}  Tier 2: {manifest['by_tier']['2']}  Tier 3: {manifest['by_tier']['3']}")
    print(f"  public: {manifest['by_visibility']['public']}  private: {manifest['by_visibility']['private']}  archived: {manifest['archived_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
