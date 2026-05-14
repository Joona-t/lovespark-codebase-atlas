#!/usr/bin/env python3
"""atlas-audit — audit one or more repos into JSON+HTML.

Reads repos.json (from atlas-discover.py). For each repo:
  1. Runs deterministic instruments (no LLM in Phase 0)
  2. Merges with audit-meta.yml at the repo root
  3. Picks Tier-based depth (deep / medium / card)
  4. Renders HTML using the Karpathy template
  5. Writes audit/<repo>.json + audit/<repo>.html under --output-dir

Modes are derived from tier:
  Tier 1 → deep
  Tier 2 → medium
  Tier 3 → card

Override per-repo via --mode or via audit-meta.yml `tier:` field.

Phase 0 omits LLM enrichment entirely. Phase 1 adds it via lib/llm_enrich.py.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))

from lib import data_inspector, instruments, llm_enrich, template  # noqa: E402

AUDIT_VERSION = "0.2.0"
DEFAULT_MANIFEST = THIS / "data" / "repos.json"
DEFAULT_OUTPUT = THIS / "data" / "audit"


def mode_for_tier(tier: int) -> str:
    return {1: "deep", 2: "medium", 3: "card"}.get(tier, "card")


def audit_one(repo_record: dict, mode: str | None = None,
              llm: bool = False, llm_sections: list[str] | None = None) -> dict | None:
    """Run instruments on one repo and return the merged audit dict.

    Returns None if the repo can't be audited (no local path).
    """
    local = repo_record.get("local_path")
    if not local:
        return None
    repo_path = Path(local)
    if not repo_path.is_dir():
        return None

    started = time.monotonic()
    data = instruments.collect_all(repo_path)

    # Merge gh-side metadata into the audit dict
    data["url"] = repo_record.get("url")
    data["visibility"] = repo_record.get("visibility")
    data["is_archived"] = repo_record.get("is_archived", False)
    data["stars"] = repo_record.get("stars", 0)
    data["description"] = repo_record.get("description") or ""
    data["pushed_at"] = repo_record.get("pushed_at")
    data["disk_usage_kb"] = repo_record.get("disk_usage_kb", 0)

    # Tier — audit-meta.yml wins, else repo record
    meta_tier = (data.get("audit_meta") or {}).get("tier")
    if isinstance(meta_tier, int) and meta_tier in (1, 2, 3):
        data["tier"] = meta_tier
        data["tier_reason"] = "from audit-meta.yml"
    else:
        data["tier"] = repo_record.get("tier", 3)
        data["tier_reason"] = repo_record.get("tier_reason", "default")

    data["audit_mode"] = mode or mode_for_tier(data["tier"])
    data["audit_version"] = AUDIT_VERSION

    # audit-meta.yml core_loop override beats auto-detection
    meta_cl = (data.get("audit_meta") or {}).get("core_loop")
    if isinstance(meta_cl, dict) and meta_cl.get("path"):
        data["core_loop"] = {
            "path": meta_cl["path"],
            "role": meta_cl.get("role", ""),
            "source": "audit-meta.yml override",
        }

    # Real data samples (deterministic)
    if data["audit_mode"] in ("deep", "medium"):
        data["data_samples"] = data_inspector.collect_samples(repo_path, data.get("kind", {}))

    # Core-loop preview (only for deep mode) so template can show it
    cl = data.get("core_loop")
    if cl and data["audit_mode"] == "deep":
        preview = instruments.read_first_lines(repo_path, cl["path"], max_lines=80)
        if preview:
            cl["preview"] = preview
            cl["truncated"] = preview.count("\n") >= 79

    # LLM enrichment (Tier 1 / deep mode only by default)
    if llm and data["audit_mode"] == "deep":
        # Choose which sections to enrich based on mode
        sections = llm_sections or llm_enrich.ENRICHABLE_SECTIONS
        # Skip core_loop_annotations if no preview
        if not (cl and cl.get("preview")):
            sections = [s for s in sections if s != "core_loop_annotations"]
        try:
            data["llm_enrich"] = llm_enrich.enrich_all(data, enable=True, sections=sections)
        except Exception as e:
            print(f"[atlas-audit] LLM enrichment failed for {data['name']}: {e}",
                  file=sys.stderr)
            data["llm_enrich"] = {}

    elapsed = time.monotonic() - started
    data["audit_elapsed_seconds"] = round(elapsed, 2)
    return data


def render_and_write(data: dict, output_dir: Path) -> tuple[Path, Path]:
    name = data["name"]
    output_dir.mkdir(parents=True, exist_ok=True)

    html_path = output_dir / f"{name}.html"
    json_path = output_dir / f"{name}.json"

    html_doc = template.render_audit_html(
        data,
        mode=data["audit_mode"],
        audit_version=AUDIT_VERSION,
    )

    # Strip preview from on-disk JSON to keep it tidy. default=str handles
    # date/datetime objects parsed out of YAML.
    save = json.loads(json.dumps(data, default=str))  # deep copy
    cl = save.get("core_loop")
    if isinstance(cl, dict):
        cl.pop("preview", None)
        cl.pop("truncated", None)

    json_path.write_text(json.dumps(save, indent=2, sort_keys=True, default=str), encoding="utf-8")
    html_path.write_text(html_doc, encoding="utf-8")
    return html_path, json_path


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit one or more repos into JSON+HTML.")
    ap.add_argument("--manifest", "-m", type=Path, default=DEFAULT_MANIFEST,
                    help=f"repos.json from atlas-discover.py (default: {DEFAULT_MANIFEST})")
    ap.add_argument("--output-dir", "-o", type=Path, default=DEFAULT_OUTPUT,
                    help=f"Where to write audit/<repo>.html/json (default: {DEFAULT_OUTPUT})")
    ap.add_argument("--repo", action="append", default=[],
                    help="Audit one specific repo by name (can be passed multiple times)")
    ap.add_argument("--tier", type=int, choices=[1, 2, 3], action="append", default=[],
                    help="Audit all repos at this tier (can be passed multiple times)")
    ap.add_argument("--all", action="store_true",
                    help="Audit every repo with a local clone")
    ap.add_argument("--mode", choices=["deep", "medium", "card"],
                    help="Force a specific render mode (overrides tier)")
    ap.add_argument("--limit", type=int, default=None,
                    help="Stop after N successful audits (for smoke tests)")
    ap.add_argument("--llm", action="store_true",
                    help="Enable LLM enrichment for narrative sections (Tier 1 only)")
    ap.add_argument("--no-llm", action="store_true",
                    help="Disable LLM enrichment even on Tier 1")
    args = ap.parse_args()

    if not args.manifest.exists():
        print(f"[atlas-audit] manifest not found: {args.manifest}", file=sys.stderr)
        print("[atlas-audit] run atlas-discover.py first.", file=sys.stderr)
        return 2

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    repos = manifest.get("repos", [])

    # Filter
    if args.repo:
        wanted = set(args.repo)
        repos = [r for r in repos if r["name"] in wanted]
        missing = wanted - {r["name"] for r in repos}
        if missing:
            print(f"[atlas-audit] warning: not in manifest: {sorted(missing)}", file=sys.stderr)
    elif args.tier:
        repos = [r for r in repos if r["tier"] in args.tier]
    elif args.all:
        pass  # use all
    else:
        ap.error("specify --repo NAME, --tier N, or --all")

    repos = [r for r in repos if r.get("local_path")]
    if not repos:
        print("[atlas-audit] nothing to audit (no repos with local clones matched)", file=sys.stderr)
        return 1

    print(f"[atlas-audit] auditing {len(repos)} repo(s) → {args.output_dir}")
    ok = 0
    failed: list[str] = []
    for r in repos:
        if args.limit is not None and ok >= args.limit:
            break
        name = r["name"]
        try:
            llm_on = args.llm and not args.no_llm
            data = audit_one(r, mode=args.mode, llm=llm_on)
        except Exception as e:
            print(f"[atlas-audit] FAIL {name}: {type(e).__name__}: {e}", file=sys.stderr)
            failed.append(name)
            continue
        if data is None:
            print(f"[atlas-audit] SKIP {name}: no usable local path")
            continue
        html_path, json_path = render_and_write(data, args.output_dir)
        ok += 1
        elapsed = data.get("audit_elapsed_seconds", 0)
        loc = data["files"]["loc_total"]
        print(f"[atlas-audit] OK   {name:35s}  mode={data['audit_mode']:6s}  loc={loc:>7,}  t={elapsed}s")

    print(f"[atlas-audit] done: {ok} ok, {len(failed)} failed, "
          f"{len(repos) - ok - len(failed)} skipped")
    if failed:
        print(f"[atlas-audit] failed: {failed}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
