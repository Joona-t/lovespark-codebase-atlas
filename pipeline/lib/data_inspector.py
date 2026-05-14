"""Data inspector — surface 3 concrete samples per repo, by project kind.

Karpathy rule #1: "look at the data first." Most audit docs talk about inputs
abstractly. This module surfaces ACTUAL records flowing through the system so
the reader can see what the code is operating on.

For each repo kind we surface a small, deterministic set of artifacts:
  - Chrome extension → manifest permissions, sample storage key list, content-script targets
  - SwiftUI iOS / Xcode → 3 SwiftUI View struct names + their body shape
  - Python tool → 3 top-level public function signatures
  - Rust → 3 public crate API items (pub fn / pub struct)
  - Node / TypeScript → 3 exported symbols / top-level routes
  - Tauri → src-tauri entry + frontend entry, plus 2 IPC commands

Hard caps:
  - 50 LOC per sample
  - 3 samples per repo
  - No execution — pure static parsing

Output shape (consumed by template.section_data):
  [
    {"label": "...", "content": "...", "lang": "swift|js|py|rs|json|..."},
    ...
  ]
"""

from __future__ import annotations

import json
import re
from pathlib import Path

MAX_SAMPLE_CHARS = 1800
MAX_PREVIEW_LINES = 30


def _read_lines(p: Path, max_lines: int = MAX_PREVIEW_LINES) -> str:
    try:
        with p.open(encoding="utf-8", errors="replace") as f:
            buf = []
            for i, line in enumerate(f):
                if i >= max_lines:
                    break
                buf.append(line.rstrip("\n"))
            return "\n".join(buf)
    except OSError:
        return ""


def _trim(text: str, cap: int = MAX_SAMPLE_CHARS) -> str:
    if len(text) <= cap:
        return text
    return text[:cap] + "\n… (truncated)"


def inspect_chrome_extension(repo: Path) -> list[dict]:
    samples: list[dict] = []
    mj = repo / "manifest.json"
    if mj.exists():
        try:
            data = json.loads(mj.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
        # Sample 1: permissions surface
        perms = sorted(data.get("permissions") or [])
        host = sorted(data.get("host_permissions") or [])
        body = "permissions:\n  " + ("\n  ".join(perms) if perms else "(none)")
        if host:
            body += "\nhost_permissions:\n  " + "\n  ".join(host)
        samples.append({"label": "Capability surface (from manifest.json)", "content": body, "lang": "yaml"})

        # Sample 2: content script targets
        cs = data.get("content_scripts") or []
        if cs:
            body = "content_scripts:\n"
            for s in cs[:3]:
                matches = ", ".join(s.get("matches") or [])
                js = ", ".join(s.get("js") or [])
                body += f"  - matches: {matches}\n    js: {js}\n"
            samples.append({"label": "Content script targets", "content": body, "lang": "yaml"})

        # Sample 3: background entry
        bg = data.get("background") or {}
        if bg:
            sw = bg.get("service_worker") or bg.get("scripts") or "?"
            samples.append({"label": "Background entry", "content": f"service_worker: {sw}", "lang": "yaml"})

    return samples[:3]


def inspect_swiftui(repo: Path) -> list[dict]:
    """Surface 3 SwiftUI View struct names + body shapes."""
    samples: list[dict] = []
    swift_files: list[Path] = []
    for p in repo.rglob("*.swift"):
        try:
            rel = p.relative_to(repo)
        except ValueError:
            continue
        parts = rel.parts
        if any(x in parts for x in (".build", "DerivedData", ".swiftpm", "Pods", "checkouts", "Tests")):
            continue
        if "test" in p.name.lower() or "preview" in p.name.lower():
            continue
        swift_files.append(p)

    # Find files containing "struct X: View"
    view_re = re.compile(r"struct\s+(\w+)\s*:\s*View\s*\{", re.MULTILINE)
    found = 0
    for p in sorted(swift_files):
        if found >= 3:
            break
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        match = view_re.search(text)
        if not match:
            continue
        struct_name = match.group(1)
        # Find the body of the View struct (rough: 25 lines after the match)
        start = match.start()
        snippet = text[start:start + 1200]
        # Trim to first balanced-ish brace ending
        rel_path = p.relative_to(repo)
        samples.append({
            "label": f"SwiftUI View: {struct_name} ({rel_path})",
            "content": _trim(snippet),
            "lang": "swift",
        })
        found += 1
    return samples


def inspect_python(repo: Path) -> list[dict]:
    """Surface 3 top-level public function or class signatures."""
    samples: list[dict] = []
    files: list[Path] = []
    for p in repo.rglob("*.py"):
        try:
            rel = p.relative_to(repo)
        except ValueError:
            continue
        parts = rel.parts
        if any(x in parts for x in ("__pycache__", ".venv", "venv", "tests", "test", "build", "dist")):
            continue
        if p.name.startswith("test_") or p.name.startswith("_") and p.name != "__init__.py":
            continue
        files.append(p)

    sig_re = re.compile(
        r"^(def\s+(\w+)\s*\([^)]*\)|class\s+(\w+)\s*[\(:]\s*[^\n]*?:)",
        re.MULTILINE,
    )

    candidates: list[tuple[Path, str, str, int]] = []
    for p in sorted(files):
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in sig_re.finditer(text):
            sig_text = m.group(0).rstrip(":")
            name = m.group(2) or m.group(3) or ""
            if name.startswith("_"):
                continue
            # Grab docstring + 6 lines after
            line_start = text.rfind("\n", 0, m.start()) + 1
            tail = text[m.start():m.start() + 600]
            candidates.append((p, name, _trim(tail, 600), line_start))
            if len(candidates) >= 12:
                break
        if len(candidates) >= 12:
            break

    seen_names: set[str] = set()
    for p, name, content, _ in candidates:
        if name in seen_names:
            continue
        seen_names.add(name)
        rel = p.relative_to(repo)
        samples.append({
            "label": f"Public symbol: {name}() ({rel})",
            "content": content,
            "lang": "python",
        })
        if len(samples) >= 3:
            break
    return samples


def inspect_rust(repo: Path) -> list[dict]:
    """Surface 3 public crate API items (pub fn / pub struct / pub enum)."""
    samples: list[dict] = []
    lib_rs = repo / "src" / "lib.rs"
    main_rs = repo / "src" / "main.rs"
    files: list[Path] = []
    if lib_rs.exists():
        files.append(lib_rs)
    if main_rs.exists():
        files.append(main_rs)
    for p in (repo / "src").rglob("*.rs") if (repo / "src").is_dir() else []:
        files.append(p)
    files = list(dict.fromkeys(files))[:8]

    pub_re = re.compile(r"^pub\s+(fn|struct|enum|trait)\s+(\w+)", re.MULTILINE)
    for p in files:
        if len(samples) >= 3:
            break
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in pub_re.finditer(text):
            kind = m.group(1)
            name = m.group(2)
            snippet = text[m.start():m.start() + 500]
            rel = p.relative_to(repo)
            samples.append({
                "label": f"pub {kind} {name} ({rel})",
                "content": _trim(snippet, 500),
                "lang": "rust",
            })
            if len(samples) >= 3:
                break
    return samples


def inspect_node(repo: Path) -> list[dict]:
    """Surface package.json scripts + 3 top-level exports / route files."""
    samples: list[dict] = []
    pj = repo / "package.json"
    if pj.exists():
        try:
            data = json.loads(pj.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
        scripts = data.get("scripts") or {}
        if scripts:
            body = "scripts:\n" + "\n".join(f"  {k}: {v}" for k, v in list(scripts.items())[:6])
            samples.append({"label": "Run targets (from package.json)", "content": body, "lang": "yaml"})

    # Common Next/Express/CRA entry points
    candidates = ["src/index.ts", "src/index.tsx", "src/index.js", "src/main.ts",
                  "src/App.tsx", "src/App.jsx", "src/app.ts", "src/app.js",
                  "pages/index.js", "pages/index.tsx", "app/page.tsx", "app/page.js"]
    for c in candidates:
        if len(samples) >= 3:
            break
        p = repo / c
        if p.exists():
            samples.append({
                "label": f"Entry: {c}",
                "content": _read_lines(p),
                "lang": p.suffix.lstrip("."),
            })
    return samples


def inspect_tauri(repo: Path) -> list[dict]:
    """Tauri-specific: src-tauri main.rs + a couple IPC command signatures."""
    samples: list[dict] = []
    main_rs = repo / "src-tauri" / "src" / "main.rs"
    if main_rs.exists():
        samples.append({
            "label": "src-tauri/src/main.rs",
            "content": _read_lines(main_rs, max_lines=40),
            "lang": "rust",
        })
    lib_rs = repo / "src-tauri" / "src" / "lib.rs"
    if lib_rs.exists():
        text = _read_lines(lib_rs, max_lines=50)
        samples.append({"label": "src-tauri/src/lib.rs", "content": text, "lang": "rust"})

    # Look for #[tauri::command]
    if (repo / "src-tauri" / "src").is_dir():
        for p in (repo / "src-tauri" / "src").rglob("*.rs"):
            if len(samples) >= 3:
                break
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            m = re.search(r"#\[tauri::command\][^\n]*\nfn\s+(\w+)[^\n]*", text)
            if m:
                samples.append({
                    "label": f"IPC command: {m.group(1)} ({p.name})",
                    "content": _trim(text[m.start():m.start() + 400]),
                    "lang": "rust",
                })
    return samples[:3]


def collect_samples(repo: Path, kind: dict) -> list[dict]:
    """Dispatch to the right inspector(s) based on detected kind."""
    if not repo.is_dir():
        return []
    samples: list[dict] = []
    if kind.get("is_chrome_extension"):
        samples.extend(inspect_chrome_extension(repo))
    if kind.get("is_xcode_project") or kind.get("is_swift_package"):
        samples.extend(inspect_swiftui(repo))
    if kind.get("is_tauri_project"):
        samples.extend(inspect_tauri(repo))
    if kind.get("is_rust_project") and not kind.get("is_tauri_project"):
        samples.extend(inspect_rust(repo))
    if kind.get("is_python_project"):
        samples.extend(inspect_python(repo))
    if kind.get("is_node_project") and not kind.get("is_tauri_project"):
        samples.extend(inspect_node(repo))
    return samples[:3]
