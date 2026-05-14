#!/usr/bin/env python3
"""atlas-audit-single — audit a single repo by path (no manifest required).

This is the CI-friendly entry point invoked from `atlas-update.yml`. It bypasses
repos.json and operates directly on a repo checkout. Used by the per-repo GH
Action so it doesn't have to fetch the manifest first.

Usage:
    python3 atlas-audit-single.py \
        --name lovespark-focus \
        --repo-path /github/workspace \
        --visibility public \
        --output-dir /tmp/atlas-out
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))

from lib import data_inspector, instruments, template  # noqa: E402

AUDIT_VERSION = "0.2.0"


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit one repo by direct path (CI entry).")
    ap.add_argument("--name", required=True, help="Repo name")
    ap.add_argument("--repo-path", required=True, type=Path, help="Path to repo checkout")
    ap.add_argument("--visibility", choices=["public", "private"], default="private")
    ap.add_argument("--tier", type=int, choices=[1, 2, 3], default=3,
                    help="Tier (default 3 — CI runs use card mode for speed)")
    ap.add_argument("--mode", choices=["deep", "medium", "card"], default="card",
                    help="Render mode (default card for CI). Use medium for richer output.")
    ap.add_argument("--output-dir", required=True, type=Path)
    ap.add_argument("--url", default=None, help="GitHub URL (best-effort)")
    args = ap.parse_args()

    repo = args.repo_path
    if not repo.is_dir():
        print(f"[atlas-audit-single] not a directory: {repo}", file=sys.stderr)
        return 2

    started = time.monotonic()
    data = instruments.collect_all(repo)
    data["name"] = args.name
    data["url"] = args.url
    data["visibility"] = args.visibility
    data["tier"] = args.tier
    data["audit_mode"] = args.mode
    data["audit_version"] = AUDIT_VERSION

    # Honor audit-meta.yml core_loop override
    meta_cl = (data.get("audit_meta") or {}).get("core_loop")
    if isinstance(meta_cl, dict) and meta_cl.get("path"):
        data["core_loop"] = {
            "path": meta_cl["path"],
            "role": meta_cl.get("role", ""),
            "source": "audit-meta.yml override",
        }

    # Real data samples
    data["data_samples"] = data_inspector.collect_samples(repo, data.get("kind", {}))

    # Core-loop preview for deep mode only
    cl = data.get("core_loop")
    if cl and args.mode == "deep":
        preview = instruments.read_first_lines(repo, cl["path"], max_lines=80)
        if preview:
            cl["preview"] = preview
            cl["truncated"] = preview.count("\n") >= 79

    # No LLM enrichment in CI (slow + needs CLI subscription). Cron path runs LLM.
    data["llm_enrich"] = {}

    elapsed = time.monotonic() - started
    data["audit_elapsed_seconds"] = round(elapsed, 2)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    audit_dir = args.output_dir / "audit"
    audit_dir.mkdir(exist_ok=True)

    html = template.render_audit_html(data, mode=args.mode, audit_version=AUDIT_VERSION)
    (audit_dir / f"{args.name}.html").write_text(html, encoding="utf-8")

    save = json.loads(json.dumps(data, default=str))
    save.get("core_loop", {}).pop("preview", None) if isinstance(save.get("core_loop"), dict) else None
    (audit_dir / f"{args.name}.json").write_text(
        json.dumps(save, indent=2, sort_keys=True, default=str), encoding="utf-8"
    )

    print(f"[atlas-audit-single] ok {args.name} mode={args.mode} loc={data['files']['loc_total']:,} t={elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
