"""LLM enrichment — Karpathy-voiced prose for audit sections via `claude -p` subprocess.

Why this exists: deterministic instruments give us facts (LOC, deps, core-loop
file). They don't give us "what's the silent failure mode" or "what would a
naive version of this look like" — those are judgment calls Karpathy makes in
his blog/critique style.

Design constraints:
  1. NO paid API (CLAUDE.md rule #10). Only the user's local CLI subscription:
     `claude -p` (default), `codex` or `gemini` if explicitly chosen.
  2. In-context examples per section from karpathy_examples.py — biases output
     away from SaaS-marketing voice toward his actual rhetorical patterns.
  3. Banned-phrase post-filter. If output contains "exciting"/"powerful"/etc.,
     retry once with stronger anti-marketing instructions. If still bad, drop.
  4. Cache by content-hash so re-audits don't burn tokens unnecessarily.
  5. Hard timeout per call (90s) — Tier-1 only.

Usage:
    from lib import llm_enrich
    enriched = llm_enrich.enrich_all(audit_data, enable=True)
    audit_data["llm_enrich"] = enriched
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS.parent))

from lib.karpathy_examples import EXAMPLES, BANNED_PHRASES, STYLE_ANCHORS  # noqa: E402

CACHE_DIR = THIS.parent / "data" / "llm-cache"
CLI_CMD = "claude"            # Override via LLM_ENRICH_CLI env var
CLI_FLAGS = ["-p"]            # `-p` = print mode, non-interactive
TIMEOUT_SECONDS = 90

# Sections we enrich. Each maps to a prompt-builder function below.
ENRICHABLE_SECTIONS = [
    "tldr", "naive", "verification", "assumptions",
    "stack_rationale", "decisions", "tradeoffs",
    "silent_failures", "v_next", "takeaway",
    "core_loop_annotations",
]


# ─────────────────────────────────────────────────────────────────────────────
# Prompt building
# ─────────────────────────────────────────────────────────────────────────────

def _repo_context_block(d: dict) -> str:
    """Compact repo facts the LLM needs to ground its prose."""
    files = d.get("files") or {}
    git = d.get("git") or {}
    deps = d.get("deps") or {}
    kind = d.get("kind") or {}
    kind_str = ", ".join(k.replace("is_", "").replace("_", " ") for k in kind) or "—"

    top_deps: list[str] = []
    for key in ("npm", "spm", "cargo", "pip", "chrome_permissions"):
        items = deps.get(key) or []
        if items:
            top_deps.append(f"{key}: {', '.join(items[:5])}")

    return (
        f"name: {d.get('name', '?')}\n"
        f"kind: {kind_str}\n"
        f"primary language: {files.get('primary_language', '?')}\n"
        f"loc: {files.get('loc_total', 0):,}  files: {files.get('file_count', 0):,}\n"
        f"commits: {git.get('commit_count', 0):,}  last commit: {(git.get('last_commit_date') or '')[:10]}\n"
        f"top deps: {' · '.join(top_deps) if top_deps else '(none declared)'}\n"
        f"audit-meta tldr: {(d.get('audit_meta') or {}).get('tldr') or '(none)'}\n"
        f"description: {d.get('description') or '(none)'}"
    )


def _examples_block(section_key: str) -> str:
    """Render the in-context examples for one section."""
    items = EXAMPLES.get(section_key, [])
    if not items:
        return ""
    blocks = []
    for i, ex in enumerate(items[:2], 1):
        src = ex.get("source", "")
        text = ex.get("text", "")
        blocks.append(f"Example {i} (from {src}):\n  {text}")
    return "Karpathy's actual voice on similar topics:\n\n" + "\n\n".join(blocks)


def _shared_voice_rules() -> str:
    return (
        "VOICE RULES (non-negotiable):\n"
        f"  - BANNED phrases (the post-filter will reject your output): {', '.join(BANNED_PHRASES[:18])}…\n"
        "  - OK to use: Honestly, Amusingly, Naively, The naive thing would be, You should be nervous about\n"
        "  - Be concrete. Numbers when you have them. No generic praise.\n"
        "  - If the signal in the context is too thin to write something honest, say so explicitly. "
        "    Don't fabricate. \"I can't tell from this code alone whether X\" is a valid answer.\n"
        "  - Output ONLY the prose for the section. No headings. No meta-commentary. No \"here is\".\n"
        "  - Plain text or simple HTML inline tags (<code>, <strong>) only. No markdown headers."
    )


PROMPTS = {
    "tldr": (
        "Write a one-sentence pitch for this repo. ~12 words. Punchy. Concrete. "
        "Mirror Karpathy's READMEs: 'The simplest, fastest repository for X' or 'A Y in Z lines'.\n\n"
        "{context}\n\n"
        "{examples}\n\n"
        "{voice_rules}\n\n"
        "Output ONLY the sentence."
    ),
    "naive": (
        "Answer: what's the simplest possible version of this repo that would still solve the same problem? "
        "1–2 sentences. Karpathy Recipe stage 3 energy: 'The dumb thing would be a single function. A regex. A flat file.'\n\n"
        "{context}\n\n"
        "{examples}\n\n"
        "{voice_rules}"
    ),
    "verification": (
        "Where does this system check its own work? Tests? Asserts? CI? Manual review? LLM-as-judge? "
        "If nothing, say so honestly. 1–3 sentences.\n\n"
        "{context}\n\n"
        "Verification signals from disk: {verification_signals}\n\n"
        "{examples}\n\n"
        "{voice_rules}"
    ),
    "assumptions": (
        "Name 3–5 things this code is silently assuming. Karpathy 2024+ critique style: "
        "'the user is always online', 'the file always exists', 'input is well-formed'. "
        "Look at the deps + permissions for hints. Output as a list, one assumption per line, "
        "prefixed with `- `.\n\n"
        "{context}\n\n"
        "{examples}\n\n"
        "{voice_rules}"
    ),
    "stack_rationale": (
        "One sentence on the dependency philosophy of this repo. "
        "Is it minimal (pure stdlib + 1 framework)? Sprawling? Pinned to one ecosystem? "
        "What's notably ABSENT that you'd expect? Karpathy-style: 'pure Python, no PyTorch, in 100 lines'.\n\n"
        "{context}\n\n"
        "{examples}\n\n"
        "{voice_rules}"
    ),
    "decisions": (
        "From the repo signal below, draft 3 architectural decisions that were probably made. "
        "For each: a likely date, a title, and the WHY (not the what). Karpathy's rule: a decision is the WHY. "
        "Output 3 bullets, one per line, prefixed with `- `.\n\n"
        "{context}\n\n"
        "Recent commits (surface, not decisions): {recent_commits}\n\n"
        "{examples}\n\n"
        "{voice_rules}"
    ),
    "tradeoffs": (
        "List 2–4 trade-offs implied by the repo's architecture. "
        "Every choice cuts something else. 'We chose X over Y because Z' format. "
        "Output bullets prefixed with `- `.\n\n"
        "{context}\n\n"
        "{examples}\n\n"
        "{voice_rules}"
    ),
    "silent_failures": (
        "Karpathy 'what could go wrong' but FORWARD-LOOKING. "
        "List 3–5 ways this repo could silently break — wrong output with no exception, slow degradation, "
        "data corruption that looks fine. NOT past bugs. Examples: "
        "'If the storage quota fills, writes succeed silently with no data persisted.' "
        "Output as bullets, one per line, prefixed with `- `.\n\n"
        "{context}\n\n"
        "{examples}\n\n"
        "{voice_rules}"
    ),
    "v_next": (
        "Three plausible v0.next items for this repo — what would you change today? "
        "Open questions count. Each item: 1 line. Prefix with `- `. "
        "Karpathy honest-uncertainty energy.\n\n"
        "{context}\n\n"
        "{examples}\n\n"
        "{voice_rules}"
    ),
    "takeaway": (
        "1–2 transferable lessons from this repo. Plain prose, no jargon, no grand claims. "
        "Something another LoveSpark project could steal. Karpathy closing style: humility + concrete.\n\n"
        "{context}\n\n"
        "{examples}\n\n"
        "{voice_rules}"
    ),
    "core_loop_annotations": (
        "You are looking at the most important file in this repo (its 'core loop' per Karpathy). "
        "Identify 5–10 lines where a curious reader would want a one-phrase '← what this does' annotation. "
        "Output ONLY a JSON array of {{\"line\": int, \"note\": str}} objects, 1-indexed line numbers, "
        "note ≤ 60 chars each. No prose, no markdown. Example: "
        "[{{\"line\": 3, \"note\": \"register custom fonts before any view body resolves\"}}]\n\n"
        "{context}\n\n"
        "File path: {core_loop_path}\n"
        "First 80 lines:\n```{core_loop_lang}\n{core_loop_preview}\n```\n\n"
        "{voice_rules}\n\nReturn ONLY the JSON array."
    ),
}


def _build_prompt(section_key: str, d: dict) -> str:
    """Compose the final prompt string for a given section."""
    context = _repo_context_block(d)
    examples = _examples_block(section_key) if section_key != "core_loop_annotations" else ""
    voice_rules = _shared_voice_rules()
    template = PROMPTS.get(section_key)
    if not template:
        return ""
    extras: dict[str, str] = {
        "context": context,
        "examples": examples,
        "voice_rules": voice_rules,
    }
    if section_key == "verification":
        repo_path = Path(d.get("local_path", "."))
        sigs: list[str] = []
        if (repo_path / "tests").is_dir() or (repo_path / "test").is_dir():
            sigs.append("test dir present")
        if (repo_path / ".github" / "workflows").is_dir():
            sigs.append(".github/workflows present")
        extras["verification_signals"] = "; ".join(sigs) if sigs else "(none detected)"
    elif section_key == "decisions":
        recent = (d.get("git") or {}).get("recent_commits") or []
        extras["recent_commits"] = "; ".join(f"{c['subject']}" for c in recent[:6])
    elif section_key == "core_loop_annotations":
        cl = d.get("core_loop") or {}
        extras["core_loop_path"] = cl.get("path", "?")
        extras["core_loop_preview"] = cl.get("preview", "")
        extras["core_loop_lang"] = Path(cl.get("path", "")).suffix.lstrip(".")
    return template.format(**extras)


# ─────────────────────────────────────────────────────────────────────────────
# CLI subprocess + cache
# ─────────────────────────────────────────────────────────────────────────────

def _cache_key(section_key: str, prompt: str) -> str:
    h = hashlib.sha256()
    h.update(section_key.encode())
    h.update(b"::")
    h.update(prompt.encode())
    return h.hexdigest()[:16]


def _cache_path(section_key: str, prompt: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{section_key}-{_cache_key(section_key, prompt)}.txt"


def _call_cli(prompt: str, *, cli: str = CLI_CMD, flags: list[str] | None = None) -> str | None:
    """Invoke the local LLM CLI. Returns stdout or None on failure."""
    args = [cli] + (flags if flags is not None else CLI_FLAGS) + [prompt]
    try:
        r = subprocess.run(
            args, capture_output=True, text=True,
            timeout=TIMEOUT_SECONDS, check=False,
        )
    except (subprocess.SubprocessError, FileNotFoundError, OSError) as e:
        print(f"[llm_enrich] CLI invocation failed: {e}", file=sys.stderr)
        return None
    if r.returncode != 0:
        print(f"[llm_enrich] CLI returned {r.returncode}: {r.stderr[:200]}", file=sys.stderr)
        return None
    return (r.stdout or "").strip() or None


def _filter_banned(text: str) -> tuple[str, list[str]]:
    """Return (cleaned_text, list_of_banned_phrases_found)."""
    lower = text.lower()
    found = [p for p in BANNED_PHRASES if p in lower]
    return text, found


def _generate(section_key: str, prompt: str, *, retries: int = 1) -> str | None:
    """Try generate → ban-filter → optional retry. Returns final text or None."""
    cache_p = _cache_path(section_key, prompt)
    if cache_p.exists():
        cached = cache_p.read_text(encoding="utf-8").strip()
        if cached:
            return cached

    attempt = 0
    while attempt <= retries:
        output = _call_cli(prompt)
        if not output:
            return None
        cleaned, banned = _filter_banned(output)
        if not banned:
            cache_p.write_text(cleaned, encoding="utf-8")
            return cleaned
        # Banned phrases found — retry with stronger instruction
        print(f"[llm_enrich] {section_key}: banned phrases {banned} — retrying", file=sys.stderr)
        prompt = (
            prompt + "\n\nIMPORTANT: your previous output contained banned phrase(s): "
            f"{', '.join(banned)}. Rewrite without those words. "
            "Be more concrete, less marketing-y."
        )
        attempt += 1
    # Two attempts both contained banned phrases — return None so template uses placeholder
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Public surface
# ─────────────────────────────────────────────────────────────────────────────

def enrich_all(d: dict, *, enable: bool = True, sections: list[str] | None = None) -> dict:
    """Run all enrichments and return a dict the template can merge.

    `sections` lets the caller cap which keys to compute (e.g., medium-mode only
    enriches tldr + takeaway).
    """
    if not enable:
        return {}
    out: dict[str, object] = {}

    wanted = sections or ENRICHABLE_SECTIONS

    for key in wanted:
        if key not in PROMPTS:
            continue
        # Skip if user already wrote the override in audit-meta
        if _has_audit_meta(d, key):
            continue
        prompt = _build_prompt(key, d)
        if not prompt.strip():
            continue
        result = _generate(key, prompt)
        if result is None:
            continue
        if key == "core_loop_annotations":
            # Parse JSON
            try:
                # Strip ```json fences if present
                cleaned = result.strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned.split("```")[1] if "```" in cleaned else cleaned
                    if cleaned.startswith("json"):
                        cleaned = cleaned[4:].strip()
                out[key] = json.loads(cleaned)
            except (json.JSONDecodeError, IndexError):
                continue
        else:
            out[key] = result
    return out


def _has_audit_meta(d: dict, section_key: str) -> bool:
    """Map a section key to the audit-meta.yml field that overrides it."""
    meta = d.get("audit_meta") or {}
    if not isinstance(meta, dict):
        return False
    field_map = {
        "tldr": "tldr",
        "naive": "naive_version",
        "verification": "verification",
        "assumptions": "assumptions",
        "decisions": "decisions",
        "tradeoffs": "tradeoffs",
        "v_next": "v_next",
        "takeaway": "takeaway",
        "silent_failures": "silent_failures",
    }
    field = field_map.get(section_key)
    if not field:
        return False
    val = meta.get(field)
    return val is not None and val != [] and val != "" and val != {}
