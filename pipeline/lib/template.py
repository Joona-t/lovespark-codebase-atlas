"""Karpathy-template section renderers.

Each `section_*` function takes the audit dict (output of instruments.collect_all)
and returns HTML for one Karpathy-flow section. The `render_audit_html` driver
composes them into the full page using design.py's chrome.

Section depth varies by tier (deep / medium / card) per the approved plan.
"""

from __future__ import annotations

import html
from pathlib import Path

from . import design


SECTIONS = [
    ("tldr", "TL;DR"),
    ("data", "The Data"),
    ("naive", "The Naive Version"),
    ("architecture", "The Architecture"),
    ("core_loop", "The Core Loop"),
    ("verification", "The Verification Loop"),
    ("assumptions", "The Assumptions"),
    ("stack", "The Stack"),
    ("decisions", "The Decisions"),
    ("tradeoffs", "The Trade-offs"),
    ("metrics", "The Metrics"),
    ("failures", "The Failures"),
    ("v_next", "v0.next / Open Questions"),
    ("reproducibility", "Reproducibility"),
    ("takeaway", "The Takeaway"),
]

# Sections that are hidden in card mode (Tier 3 minimal pages)
CARD_HIDDEN = {"naive", "architecture", "core_loop", "verification",
               "assumptions", "decisions", "tradeoffs", "v_next", "takeaway"}


# ──────────────────────────────────────────────────────────────────────────────
# helpers
# ──────────────────────────────────────────────────────────────────────────────

def _esc(s: object) -> str:
    return html.escape(str(s)) if s is not None else ""


def _short_date(iso: str | None) -> str:
    if not iso:
        return "—"
    return iso[:10]


def _kv(k: str, v: str | int | float, tone: str = "") -> str:
    cls = f" {tone}" if tone else ""
    return f'<div class="kv"><div class="k">{_esc(k)}</div><span class="v{cls}">{_esc(v)}</span></div>'


def _empty(msg: str) -> str:
    return f'<p class="empty-state">{_esc(msg)}</p>'


def _placeholder(msg: str, body: str = "") -> str:
    """Wrap auto-derived content with a ⚠️ banner so unsubstantiated material is visible."""
    return f'<div class="placeholder-banner">⚠️ <strong>auto-derived placeholder.</strong> {msg}</div>{body}'


def _llm_drafted(body: str) -> str:
    """Wrap LLM-drafted content with a small attribution badge."""
    return f'<div class="llm-banner">🤖 LLM-drafted from deterministic signal · override via <code>audit-meta.yml</code></div>{body}'


def _has_meta(d: dict, *keys: str) -> bool:
    """Walk audit_meta keys; return True if a non-empty value is set at the path."""
    cur: object = d.get("audit_meta") or {}
    for k in keys:
        if not isinstance(cur, dict) or not cur.get(k):
            return False
        cur = cur[k]
    return True


def _llm_section(d: dict, key: str) -> str | None:
    """Pull LLM-drafted prose for a section if llm_enrich.py populated it."""
    enrich = (d.get("llm_enrich") or {}).get(key)
    if isinstance(enrich, str) and enrich.strip():
        return enrich
    return None


def _list(items: list, ordered: bool = False) -> str:
    if not items:
        return ""
    tag = "ol" if ordered else "ul"
    body = "".join(f"<li>{_esc(x)}</li>" for x in items)
    return f"<{tag}>{body}</{tag}>"


def _code_block(text: str, lang: str = "") -> str:
    cls = f' class="lang-{_esc(lang)}"' if lang else ""
    return f'<pre><code{cls}>{html.escape(text)}</code></pre>'


def _tier_class(tier: int) -> str:
    return f"tier-{tier}" if tier in (1, 2, 3) else "tier-3"


# ──────────────────────────────────────────────────────────────────────────────
# sections
# ──────────────────────────────────────────────────────────────────────────────

def section_tldr(d: dict, mode: str) -> str:
    meta = d.get("audit_meta") or {}
    tldr = meta.get("tldr") or meta.get("description") or ""
    git = d.get("git") or {}
    files = d.get("files") or {}

    primary_lang = files.get("primary_language") or "—"
    if primary_lang == "—" and files.get("loc_by_lang"):
        primary_lang = next(iter(files["loc_by_lang"]))

    blocks = []
    if tldr:
        blocks.append(f"<p>{_esc(tldr)}</p>")
    else:
        # Try LLM-drafted tldr
        llm = _llm_section(d, "tldr")
        if llm:
            blocks.append(_llm_drafted(f"<p>{_esc(llm)}</p>"))
        else:
            kind = d.get("kind") or {}
            kind_str = next(iter(kind.keys()), "").replace("is_", "").replace("_", " ").title()
            auto = f"A {_esc(kind_str)} written primarily in {_esc(primary_lang)}." if kind_str else "—"
            blocks.append(_placeholder(
                "Add a one-sentence pitch to <code>audit-meta.yml</code> → <code>tldr</code>. "
                "Karpathy-style: punchy, concrete, no \"exciting\" / \"powerful\".",
                f"<p>{auto}</p>",
            ))

    blocks.append('<div class="kv-grid">')
    blocks.append(_kv("Primary language", primary_lang))
    blocks.append(_kv("LOC (source)", f"{files.get('loc_total', 0):,}"))
    blocks.append(_kv("Files", f"{files.get('file_count', 0):,}"))
    if d.get("version"):
        blocks.append(_kv("Version", d["version"]))
    blocks.append(_kv("Last commit", _short_date(git.get("last_commit_date"))))
    blocks.append(_kv("Commits", f"{git.get('commit_count', 0):,}"))
    blocks.append("</div>")
    return "\n".join(blocks)


def section_data(d: dict, mode: str) -> str:
    meta = (d.get("audit_meta") or {}).get("data") or {}
    inputs = meta.get("inputs") if isinstance(meta, dict) else None
    outputs = meta.get("outputs") if isinstance(meta, dict) else None
    shape = meta.get("shape") if isinstance(meta, dict) else None
    example = meta.get("example") if isinstance(meta, dict) else None

    out: list[str] = []
    has_meta = any([inputs, outputs, shape, example])

    if has_meta:
        if inputs:
            out.append("<h3>Inputs</h3>")
            out.append(_list(inputs) if isinstance(inputs, list) else f"<p>{_esc(inputs)}</p>")
        if outputs:
            out.append("<h3>Outputs</h3>")
            out.append(_list(outputs) if isinstance(outputs, list) else f"<p>{_esc(outputs)}</p>")
        if shape:
            out.append("<h3>Shape &amp; scale</h3>")
            out.append(f"<p>{_esc(shape)}</p>")
        if example:
            out.append("<h3>Example</h3>")
            out.append(_code_block(str(example)))
    else:
        # Auto-fallback from project kind. Always banner this.
        kind = d.get("kind") or {}
        deps = d.get("deps") or {}
        auto: list[str] = []
        if kind.get("is_chrome_extension"):
            auto.append("Input: browser tab events, user clicks in popup/options, storage reads.")
            auto.append("Output: DOM mutations on web pages, badge text, chrome.storage writes.")
            perms = deps.get("chrome_permissions") or []
            if perms:
                auto.append("Permissions surface (proxy for capability): " + ", ".join(perms[:8]))
        if kind.get("is_xcode_project") or kind.get("is_swift_package"):
            auto.append("Input: SwiftUI gesture/touch events, app lifecycle, system notifications.")
            auto.append("Output: rendered SwiftUI views, persistence writes (UserDefaults/SwiftData/Core Data).")
        if kind.get("is_node_project") and not kind.get("is_expo_project"):
            auto.append("Input: HTTP requests (if server) or DOM/user events (if client).")
            auto.append("Output: HTTP responses, files, or rendered UI.")
        if kind.get("is_rust_project"):
            auto.append("Input: CLI args / stdin / library API calls.")
            auto.append("Output: stdout, files, or library return values.")
        if kind.get("is_python_project"):
            auto.append("Input: CLI args, files, stdin, or HTTP requests.")
            auto.append("Output: stdout, files, HTTP responses, or library return values.")
        body = _list(auto) if auto else ""
        out.append(_placeholder(
            "Add a <code>data:</code> block to <code>audit-meta.yml</code> with concrete inputs/outputs and one real example record. "
            "Karpathy's rule: look at the data first.",
            body,
        ))

    # Real data samples surfaced by data_inspector (deterministic)
    samples = d.get("data_samples") or []
    if samples:
        out.append("<h3>Real samples</h3>")
        for s in samples[:3]:
            label = s.get("label", "sample")
            content = s.get("content", "")
            lang = s.get("lang", "")
            out.append(f'<p><strong>{_esc(label)}</strong></p>')
            out.append(_code_block(content, lang=lang) if content else _empty("(empty)"))

    return "\n".join(out)


def section_naive(d: dict, mode: str) -> str:
    """The Naive Version — what's the simplest possible version of this?"""
    if mode == "card":
        return ""
    meta = (d.get("audit_meta") or {}).get("naive_version")
    if meta:
        if isinstance(meta, list):
            return _list(meta)
        return f"<p>{_esc(meta)}</p>"

    llm = _llm_section(d, "naive")
    if llm:
        return _llm_drafted(f"<p>{_esc(llm)}</p>")

    return _placeholder(
        "Karpathy Recipe stage 3: build the dumbest thing that works first. "
        "Add <code>naive_version:</code> to <code>audit-meta.yml</code> — 1–2 sentences answering: "
        "what's the simplest possible version of this that still solves the problem? "
        "(The naive thing might be a single function. A regex. A flat file.)",
    )


def section_verification(d: dict, mode: str) -> str:
    """The Verification Loop — where does this system check its own work?"""
    if mode == "card":
        return ""

    meta = (d.get("audit_meta") or {}).get("verification")
    if meta:
        if isinstance(meta, list):
            return _list(meta)
        return f"<p>{_esc(meta)}</p>"

    llm = _llm_section(d, "verification")
    if llm:
        return _llm_drafted(f"<p>{_esc(llm)}</p>")

    # Deterministic auto-discovery
    repo_path = Path(d.get("local_path", "."))
    signals: list[str] = []
    if repo_path.is_dir():
        for tdir in ("tests", "test", "__tests__", "Tests", "spec"):
            if (repo_path / tdir).is_dir():
                signals.append(f"Test directory: <code>{_esc(tdir)}/</code>")
                break
        if (repo_path / ".github" / "workflows").is_dir():
            workflows = list((repo_path / ".github" / "workflows").glob("*.yml"))
            if workflows:
                signals.append(f"GitHub Actions: {len(workflows)} workflow(s)")
        for ci_file in ("pre-commit-config.yaml", ".pre-commit-config.yaml"):
            if (repo_path / ci_file).exists():
                signals.append("pre-commit hooks configured")
                break
        # Heuristic: look for "assert" in main source files
        ls = d.get("ls_check")
        if ls and isinstance(ls, dict):
            signals.append(f"ls-check score: {ls.get('score', '?')}, warnings: {ls.get('warnings', '?')}")

    body = _list(signals) if signals else "<p>No tests, no CI, no assertions detected. The verification loop is YOU.</p>"
    return _placeholder(
        "Add <code>verification:</code> to <code>audit-meta.yml</code>. "
        "Karpathy's 2024+ frame: where does this system check its own work? "
        "Tests? Asserts? LLM-as-judge? Manual review? If nothing — say so.",
        body,
    )


def section_assumptions(d: dict, mode: str) -> str:
    """The Assumptions — what is the code silently assuming?"""
    if mode == "card":
        return ""

    meta = (d.get("audit_meta") or {}).get("assumptions")
    if meta:
        if isinstance(meta, list):
            return _list(meta)
        return f"<p>{_esc(meta)}</p>"

    llm = _llm_section(d, "assumptions")
    if llm:
        return _llm_drafted(f"<p>{_esc(llm)}</p>" if not llm.startswith("-") else _list([l.lstrip("- ").strip() for l in llm.splitlines() if l.strip()]))

    return _placeholder(
        "Add <code>assumptions:</code> (list of 2–5 bullets) to <code>audit-meta.yml</code>. "
        "What is this code silently assuming? User always online? File always exists? Input always well-formed? "
        "Karpathy's instinct: don't hide confusion."
    )


def section_architecture(d: dict, mode: str) -> str:
    if mode == "card":
        return ""

    meta = (d.get("audit_meta") or {}).get("architecture") or {}
    custom = meta.get("diagram") if isinstance(meta, dict) else None
    components = meta.get("components") if isinstance(meta, dict) else None

    # Auto: top-level directory map → simple mermaid block
    repo_path = Path(d.get("local_path", "."))
    top_dirs = []
    if repo_path.is_dir():
        for child in sorted(repo_path.iterdir()):
            if not child.is_dir():
                continue
            name = child.name
            if name.startswith(".") or name in {"node_modules", "venv", ".venv", "DerivedData", "Pods"}:
                continue
            top_dirs.append(name)
            if len(top_dirs) >= 14:
                break

    out = []
    if components:
        out.append("<h3>Components (from audit-meta.yml)</h3>")
        if isinstance(components, list):
            rows = []
            for c in components:
                if isinstance(c, dict):
                    n = c.get("name", "?")
                    role = c.get("role", "")
                    rows.append(f"<tr><td><code>{_esc(n)}</code></td><td>{_esc(role)}</td></tr>")
                else:
                    rows.append(f"<tr><td colspan='2'><code>{_esc(c)}</code></td></tr>")
            out.append('<table><thead><tr><th>Component</th><th>Role</th></tr></thead><tbody>'
                       + "".join(rows) + '</tbody></table>')

    if custom:
        out.append('<div class="mermaid-host">')
        out.append(f'<pre><code class="language-mermaid">{html.escape(str(custom))}</code></pre>')
        out.append("</div>")
    elif top_dirs:
        mer = ["graph TD"]
        mer.append(f'  Repo["{d.get("name", "repo")}"]')
        for dn in top_dirs:
            safe = dn.replace("-", "_").replace(".", "_")
            mer.append(f"  Repo --> {safe}[\"{dn}/\"]")
        out.append("<h3>Top-level layout (auto)</h3>")
        out.append('<div class="mermaid-host">')
        out.append(f'<pre><code class="language-mermaid">{html.escape(chr(10).join(mer))}</code></pre>')
        out.append("</div>")
        out.append('<p class="empty-state">Replace with a real C4 diagram via <code>audit-meta.yml</code> → <code>architecture.diagram</code>.</p>')
    else:
        out.append(_empty("No top-level directories detected (single-file repo?). Add a <code>diagram</code> in audit-meta.yml."))

    return "\n".join(out)


def section_core_loop(d: dict, mode: str) -> str:
    if mode == "card":
        return ""

    cl = d.get("core_loop")
    if not cl:
        return _placeholder(
            "No obvious core-loop file detected. Tag one via <code>audit-meta.yml</code> → "
            "<code>core_loop.path</code>. Karpathy: \"if you only read one file, read this one.\""
        )

    out = [f"<p>File: <code>{_esc(cl['path'])}</code></p>"]
    out.append(f"<p class='empty-state'>Role: {_esc(cl.get('role', ''))} &middot; detection: {_esc(cl.get('source', ''))}</p>")

    preview = cl.get("preview")
    if preview and mode == "deep":
        ext = Path(cl["path"]).suffix.lstrip(".") or ""
        # Inline annotations from LLM (list of {line: int, note: str})
        annotations = (d.get("llm_enrich") or {}).get("core_loop_annotations") or []
        if annotations:
            out.append(_llm_drafted(_annotated_code(preview, annotations, ext)))
        else:
            out.append(_code_block(preview, lang=ext))
        if cl.get("truncated"):
            out.append("<p class='empty-state'>(truncated to first 80 lines — see source for the rest)</p>")
    elif mode == "medium":
        out.append("<p>Open the file to read it inline (preview hidden in medium mode).</p>")
    return "\n".join(out)


def _annotated_code(text: str, annotations: list, lang: str = "") -> str:
    """Render code with `# ←` annotation comments on specified lines.

    Annotations are {line: int (1-indexed), note: str}. The annotation is added
    as a trailing comment on that line in the source language's comment style.
    """
    if not text or not annotations:
        return _code_block(text, lang)

    comment_prefix = {
        "py": "#", "rb": "#", "sh": "#", "bash": "#", "yml": "#", "yaml": "#",
        "js": "//", "ts": "//", "jsx": "//", "tsx": "//", "rs": "//",
        "swift": "//", "java": "//", "c": "//", "cpp": "//", "go": "//",
    }.get(lang, "#")

    notes_by_line = {a["line"]: a["note"] for a in annotations if "line" in a and "note" in a}
    lines = text.splitlines()
    annotated: list[str] = []
    for i, line in enumerate(lines, start=1):
        if i in notes_by_line:
            annotated.append(f"{line}    {comment_prefix} ← {notes_by_line[i]}")
        else:
            annotated.append(line)
    return _code_block("\n".join(annotated), lang=lang)


def section_stack(d: dict, mode: str) -> str:
    deps = d.get("deps") or {}
    if not deps:
        return _placeholder("No declared dependencies detected. If this is intentional (pure stdlib), say so in <code>audit-meta.yml</code> → <code>stack_rationale</code>.")

    name_map = {
        "npm": "npm runtime",
        "npm_dev": "npm dev",
        "cargo": "Cargo crates",
        "spm": "Swift Package Manager (remote)",
        "spm_local": "Swift Package Manager (local)",
        "pip": "Python pip",
        "chrome_permissions": "Chrome permissions",
        "chrome_host_permissions": "Chrome host permissions",
    }

    out = []

    # LLM-drafted rationale per top dep (if present)
    rationale = (d.get("llm_enrich") or {}).get("stack_rationale")
    if rationale:
        out.append(_llm_drafted(f"<p>{_esc(rationale)}</p>"))

    # audit-meta override for top-3 stack rationale
    meta_stack = (d.get("audit_meta") or {}).get("stack_top3")
    if isinstance(meta_stack, list) and meta_stack:
        out.append("<h3>Why we picked these (top 3)</h3>")
        rows = []
        for entry in meta_stack:
            if isinstance(entry, dict):
                dep = entry.get("dep", entry.get("name", "?"))
                why = entry.get("why", "")
                rows.append(f"<tr><td><code>{_esc(dep)}</code></td><td>{_esc(why)}</td></tr>")
            else:
                rows.append(f"<tr><td colspan='2'>{_esc(entry)}</td></tr>")
        out.append('<table><thead><tr><th>Dep</th><th>Why</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table>")

    for key, items in deps.items():
        if not items:
            continue
        label = name_map.get(key, key)
        out.append(f"<h3>{_esc(label)} <small style='font-weight:400;color:var(--ls-text-soft);'>({len(items)})</small></h3>")
        cap = 8 if mode == "card" else 40
        shown = items[:cap]
        out.append(_list(shown))
        if len(items) > cap:
            out.append(f"<p class='empty-state'>… and {len(items) - cap} more</p>")
    return "\n".join(out)


def section_decisions(d: dict, mode: str) -> str:
    if mode == "card":
        return ""
    decisions = ((d.get("audit_meta") or {}).get("decisions")) or []

    if decisions:
        rows = []
        for entry in decisions:
            if isinstance(entry, dict):
                date = entry.get("date", "")
                title = entry.get("title", "")
                why = entry.get("why", "")
                rows.append(
                    f"<tr><td>{_esc(date)}</td><td><strong>{_esc(title)}</strong>"
                    f"<br><span style='color:var(--ls-text-soft)'>{_esc(why)}</span></td></tr>"
                )
            else:
                rows.append(f"<tr><td>—</td><td>{_esc(entry)}</td></tr>")
        return ('<table><thead><tr><th>Date</th><th>Decision</th></tr></thead><tbody>'
                + "".join(rows) + "</tbody></table>")

    llm = _llm_section(d, "decisions")
    if llm:
        return _llm_drafted(f"<p>{_esc(llm)}</p>")

    # Fallback: commit subjects, always banner
    recent = (d.get("git") or {}).get("recent_commits") or []
    body = ""
    if recent:
        cards = recent[:5]
        body = ('<table><thead><tr><th>Date</th><th>Subject</th></tr></thead><tbody>'
                + "".join(f"<tr><td>{_short_date(c['date'])}</td><td>{_esc(c['subject'])}</td></tr>" for c in cards)
                + "</tbody></table>")
    return _placeholder(
        "Add <code>decisions:</code> to <code>audit-meta.yml</code> — each item: <code>date</code>, <code>title</code>, <code>why</code>. "
        "Karpathy's instinct: WHY, not WHAT. Commit subjects below are surface, not decisions.",
        body,
    )


def section_tradeoffs(d: dict, mode: str) -> str:
    if mode == "card":
        return ""
    items = ((d.get("audit_meta") or {}).get("tradeoffs")) or []
    if items:
        return _list(items) if isinstance(items, list) else f"<p>{_esc(items)}</p>"
    llm = _llm_section(d, "tradeoffs")
    if llm:
        return _llm_drafted(f"<p>{_esc(llm)}</p>")
    return _placeholder(
        "Add <code>tradeoffs:</code> to <code>audit-meta.yml</code>. "
        "Karpathy's rule: every decision is a trade-off. What got cut? What broke when you chose X over Y?"
    )


def section_metrics(d: dict, mode: str) -> str:
    files = d.get("files") or {}
    git = d.get("git") or {}
    ls = d.get("ls_check") or {}
    eff = d.get("efficiency") or {}

    out = ['<div class="kv-grid">']
    out.append(_kv("Total LOC", f"{files.get('loc_total', 0):,}"))
    out.append(_kv("Files", f"{files.get('file_count', 0):,}"))
    if files.get("binary_count"):
        out.append(_kv("Binary files", f"{files.get('binary_count', 0):,}"))
    out.append(_kv("Commits", f"{git.get('commit_count', 0):,}"))
    out.append(_kv("Contributors", f"{git.get('contributor_count', 0):,}"))
    if d.get("version"):
        out.append(_kv("Version", d["version"]))

    # Efficiency ratios (Karpathy-style: compute/output, LOC/feature)
    if eff.get("loc_per_source_file") is not None:
        out.append(_kv("LOC / source file", f"{eff['loc_per_source_file']:.0f}"))
    if eff.get("deps_per_kloc") is not None:
        out.append(_kv("Deps / 1k LOC", f"{eff['deps_per_kloc']:.1f}"))
    if eff.get("test_to_source_ratio") is not None:
        tone = "good" if eff["test_to_source_ratio"] >= 0.2 else "warn"
        out.append(_kv("Test / source LOC", f"{eff['test_to_source_ratio']:.2f}", tone))

    if ls and isinstance(ls, dict):
        if "score" in ls:
            out.append(_kv("ls-check score", ls.get("score")))
        if "warnings" in ls:
            tone = "good" if ls.get("warnings") == 0 else "warn"
            out.append(_kv("ls-check warnings", ls.get("warnings"), tone))
    out.append("</div>")

    loc_by = files.get("loc_by_lang") or {}
    if loc_by:
        out.append("<h3>Lines of code by language</h3>")
        rows = []
        total = sum(loc_by.values()) or 1
        for lang, n in list(loc_by.items())[:12]:
            pct = 100 * n / total
            rows.append(
                f"<tr><td>{_esc(lang)}</td>"
                f"<td style='text-align:right'>{n:,}</td>"
                f"<td style='text-align:right'>{pct:.1f}%</td></tr>"
            )
        out.append('<table><thead><tr><th>Language</th>'
                   '<th style="text-align:right">Lines</th>'
                   '<th style="text-align:right">%</th></tr></thead><tbody>'
                   + "".join(rows) + "</tbody></table>")
    return "\n".join(out)


def section_failures(d: dict, mode: str) -> str:
    failures = d.get("failures") or []
    silent = _llm_section(d, "silent_failures")

    if mode == "card":
        if not failures and not silent:
            return _empty("No BUGS_AND_ITERATIONS.md found.")
        return f"<p>{len(failures)} past entries in <code>BUGS_AND_ITERATIONS.md</code>.</p>"

    out = []
    # Past failures
    if failures:
        out.append("<h3>Past failures (from <code>BUGS_AND_ITERATIONS.md</code>)</h3>")
        items = [f["title"] for f in failures[:15]]
        out.append(_list(items))
        if len(failures) > 15:
            out.append(f'<p class="empty-state">… and {len(failures) - 15} more</p>')
    else:
        out.append(_placeholder(
            "Create a <code>BUGS_AND_ITERATIONS.md</code> per CLAUDE.md rule #11 — every bug fix logged."
        ))

    # Silent failure modes (LLM-drafted forward-looking)
    out.append("<h3>Silent failure modes</h3>")
    if silent:
        if isinstance(silent, list):
            out.append(_llm_drafted(_list(silent)))
        else:
            out.append(_llm_drafted(f"<p>{_esc(silent)}</p>"))
    else:
        out.append(_placeholder(
            "Add <code>silent_failures:</code> (list) to <code>audit-meta.yml</code>. "
            "Karpathy: name 3–5 ways this would <em>silently</em> break — wrong output, slow degradation, no exception. "
            "If 90% of inputs disappeared, would you notice?"
        ))

    return "\n".join(out)


def section_v_next(d: dict, mode: str) -> str:
    if mode == "card":
        return ""
    items = ((d.get("audit_meta") or {}).get("v_next")) or []
    if items:
        return _list(items) if isinstance(items, list) else f"<p>{_esc(items)}</p>"
    llm = _llm_section(d, "v_next")
    if llm:
        return _llm_drafted(_list([l.lstrip("- ").strip() for l in llm.splitlines() if l.strip()]) if "\n" in llm else f"<p>{_esc(llm)}</p>")
    return _placeholder(
        "Add <code>v_next:</code> (a list of strings) to <code>audit-meta.yml</code> — "
        "3–5 things you'd change today. Open questions count. Honest uncertainty welcomed."
    )


def section_reproducibility(d: dict, mode: str) -> str:
    git = d.get("git") or {}
    remote = git.get("remote_url") or ""
    name = d.get("name", "repo")
    meta = d.get("audit_meta") or {}
    meta_repro = meta.get("reproducibility")
    timing = meta.get("reproducibility_timing") or meta.get("timing")
    hardware = meta.get("reproducibility_hardware") or meta.get("hardware")

    lines = []
    if remote:
        clone_url = remote.replace("git@github.com:", "https://github.com/").rstrip(".git") + ".git"
        lines.append(f"# clone\ngit clone {clone_url}\ncd {name}")
    else:
        lines.append(f"# local path\ncd {d.get('local_path', '.')}")

    kind = d.get("kind") or {}
    if kind.get("is_node_project"):
        lines.append("# install + run\nnpm install\nnpm run dev   # or: npm start")
    if kind.get("is_python_project"):
        lines.append("# install + run\npython -m venv .venv && source .venv/bin/activate\npip install -r requirements.txt\npython -m " + name.replace("-", "_"))
    if kind.get("is_rust_project"):
        lines.append("# build + run\ncargo build --release\ncargo run")
    if kind.get("is_xcode_project") or kind.get("is_swift_package"):
        lines.append("# build + run\nxcodebuild -scheme " + name + " build\n# or: open *.xcodeproj")
    if kind.get("is_chrome_extension"):
        lines.append("# load extension\n# Chrome → chrome://extensions → 'Load unpacked' → select this directory")

    if meta_repro:
        lines.append("# from audit-meta.yml")
        if isinstance(meta_repro, list):
            lines.extend(str(x) for x in meta_repro)
        else:
            lines.append(str(meta_repro))

    out = [_code_block("\n\n".join(lines), lang="bash")]

    # Timing + hardware (Karpathy-style: "trains in 3 min on 1 A100")
    if timing or hardware:
        out.append('<div class="kv-grid">')
        if timing:
            out.append(_kv("Expected runtime", timing))
        if hardware:
            out.append(_kv("Tested on", hardware))
        out.append("</div>")
    else:
        out.append(_placeholder(
            "Add <code>reproducibility_timing</code> and <code>reproducibility_hardware</code> to "
            "<code>audit-meta.yml</code>. nanoGPT-style: \"trains in 3 minutes on a single GPU.\""
        ))

    return "\n".join(out)


def section_takeaway(d: dict, mode: str) -> str:
    if mode == "card":
        return ""
    items = ((d.get("audit_meta") or {}).get("takeaway")) or []
    if items:
        return _list(items) if isinstance(items, list) else f"<p>{_esc(items)}</p>"
    llm = _llm_section(d, "takeaway")
    if llm:
        if isinstance(llm, list):
            return _llm_drafted(_list(llm))
        return _llm_drafted(f"<p>{_esc(llm)}</p>")
    return _placeholder(
        "Add <code>takeaway:</code> (list of 1–3 strings) to <code>audit-meta.yml</code>. "
        "Karpathy-style: plain-prose lessons another project could steal. No jargon. No grand claims."
    )


# ──────────────────────────────────────────────────────────────────────────────
# composer
# ──────────────────────────────────────────────────────────────────────────────

SECTION_RENDERERS = {
    "tldr": section_tldr,
    "data": section_data,
    "naive": section_naive,
    "architecture": section_architecture,
    "core_loop": section_core_loop,
    "verification": section_verification,
    "assumptions": section_assumptions,
    "stack": section_stack,
    "decisions": section_decisions,
    "tradeoffs": section_tradeoffs,
    "metrics": section_metrics,
    "failures": section_failures,
    "v_next": section_v_next,
    "reproducibility": section_reproducibility,
    "takeaway": section_takeaway,
}


def render_audit_html(
    d: dict,
    *,
    mode: str = "deep",
    mascot_url: str = "../assets/mascot.png",
    font_reg_url: str = "../fonts/OpenDyslexic-Regular.otf",
    font_bold_url: str = "../fonts/OpenDyslexic-Bold.otf",
    atlas_url: str = "../index.html",
    atlas_label: str = "LoveSpark Codebase Atlas",
    audit_version: str = "0.1",
) -> str:
    name = d.get("name", "?")
    title = f"{name} — atlas"
    tier = (d.get("audit_meta") or {}).get("tier", d.get("tier") or 3)

    visibility = d.get("visibility") or "?"
    archived = d.get("is_archived", False)

    git = d.get("git") or {}
    remote = git.get("remote_url") or ""
    gh_url = remote.replace("git@github.com:", "https://github.com/").rstrip(".git") if remote else ""

    # ── chrome ────────────────────────────────────────────────────────────────
    head = design.render_head(title, font_reg_url, font_bold_url)
    body_class = "card-mode" if mode == "card" else "deep-mode"

    # nav (skipped sections excluded from sidebar in card mode)
    nav_items = []
    for sid, label in SECTIONS:
        if mode == "card" and sid in CARD_HIDDEN:
            continue
        nav_items.append(f'<a href="#sec-{sid}">{_esc(label)}</a>')
    nav = '<nav class="nav">' + "".join(nav_items) + "</nav>"

    brand = design.render_brand(mascot_url, atlas_url=atlas_url, tagline=atlas_label)

    sidebar_html = ""
    if mode != "card":
        sidebar_html = (
            '<aside class="sidebar">'
            + brand + nav + design.render_theme_toggle()
            + "</aside>"
        )

    # ── header ────────────────────────────────────────────────────────────────
    badges = [f'<span class="tier-badge tier-{tier}">Tier&nbsp;{tier}</span>']
    if visibility == "public":
        badges.append('<span class="visibility-badge">public</span>')
    elif visibility == "private":
        badges.append('<span class="visibility-badge">private</span>')
    if archived:
        badges.append('<span class="archived-badge">archived</span>')

    meta_bits = badges[:]
    if gh_url:
        meta_bits.append(f'<a href="{_esc(gh_url)}" target="_blank" rel="noopener">{_esc(gh_url.replace("https://github.com/", ""))}</a>')
    if d.get("version"):
        meta_bits.append(f"v{_esc(d['version'])}")

    header_html = (
        '<header class="repo-head">'
        f'<h1>{_esc(name)}</h1>'
        f'<div class="meta">{" · ".join(meta_bits)}</div>'
        '</header>'
    )

    # ── sections ──────────────────────────────────────────────────────────────
    section_html: list[str] = []
    for sid, label in SECTIONS:
        if mode == "card" and sid in CARD_HIDDEN:
            continue
        body = SECTION_RENDERERS[sid](d, mode)
        if not body or body.strip() == "":
            continue
        section_html.append(
            f'<section class="atlas-section" id="sec-{sid}">'
            f'<h2>{_esc(label)}</h2>'
            f'{body}'
            '</section>'
        )

    # ── footer ────────────────────────────────────────────────────────────────
    footer_html = (
        '<footer class="repo-foot">'
        f'<div>Generated by atlas v{audit_version} · {_esc(d.get("audited_at", ""))}</div>'
        f'<div><a href="{_esc(atlas_url)}">&larr; atlas index</a></div>'
        '</footer>'
    )

    main_html = (
        '<main class="main">'
        + header_html
        + "".join(section_html)
        + footer_html
        + "</main>"
    )

    return (
        head
        + f'<body class="{body_class}"><div class="layout">'
        + sidebar_html
        + main_html
        + "</div>"
        + design.script_tag()
        + "</body></html>"
    )
