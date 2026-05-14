"""Instruments — deterministic data collectors for one repo.

Each function takes a repo Path and returns a dict (or list/value) of facts.
No LLM here. No subjective claims. Just things you can measure.

The audit pipeline composes these into the audit JSON. The template uses the
JSON; the LLM enricher (Phase 1) adds prose for narrative sections only.
"""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

# File-extension → language map. Mirrors cloc's basic detection but works without it.
EXT_LANG = {
    ".py": "Python",
    ".js": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".jsx": "JavaScript",
    ".swift": "Swift",
    ".rs": "Rust",
    ".go": "Go",
    ".rb": "Ruby",
    ".java": "Java",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".hpp": "C++",
    ".cs": "C#",
    ".css": "CSS",
    ".scss": "SCSS",
    ".html": "HTML",
    ".htm": "HTML",
    ".vue": "Vue",
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".fish": "Shell",
    ".md": "Markdown",
    ".json": "JSON",
    ".yml": "YAML",
    ".yaml": "YAML",
    ".toml": "TOML",
    ".xml": "XML",
    ".gd": "GDScript",
    ".lua": "Lua",
    ".sql": "SQL",
}

# Directories we skip for LOC counts (build artifacts, deps, history).
SKIP_DIRS = {
    ".git", ".github_archive", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache",
    "dist", "build", "target", ".next", ".nuxt", ".turbo", ".cache",
    "DerivedData", "Pods", ".swiftpm", ".build", "checkouts",
    "vendor", ".bundle", "Carthage", ".idea", ".vscode",
    "worktrees", ".claude",
    "out", "release", "Release", "Debug", "Library",
    "coverage", "htmlcov", ".tox", ".mypy_cache", ".ruff_cache",
    "_build", "_site", "site-packages", "Frameworks",
}

SKIP_FILE_PATTERNS = re.compile(r"\.(min\.js|min\.css|bundle\.js|lock|snap|map|pbxproj|xcuserstate)$")

# Languages we consider "documentation/data/markup" rather than primary source code.
# Used to pick a meaningful "primary language" — a repo with 200KB of generated
# HTML docs and 30KB of Swift is a Swift project, not an HTML project.
NON_CODE_LANGS = {
    "HTML", "CSS", "SCSS", "JSON", "YAML", "TOML", "XML", "Markdown", "Other",
}


def pick_primary_language(loc_by_lang: dict[str, int]) -> str:
    """Return the dominant CODE language, falling back to whichever has most LOC."""
    code = {k: v for k, v in loc_by_lang.items() if k not in NON_CODE_LANGS}
    if code:
        return max(code, key=code.get)
    if loc_by_lang:
        return next(iter(loc_by_lang))
    return ""


def _safe_run(cmd: list[str], cwd: Path | None = None, timeout: int = 30) -> str:
    """Run a command and return stdout; empty string on any failure."""
    try:
        r = subprocess.run(
            cmd, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout, check=False,
        )
        return r.stdout if r.returncode == 0 else ""
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return ""


def is_git_repo(path: Path) -> bool:
    return (path / ".git").exists()


def git_info(repo: Path) -> dict:
    """Commit count, date range, branch, latest commit summary."""
    if not is_git_repo(repo):
        return {"is_git": False}

    out = _safe_run(["git", "rev-list", "--count", "HEAD"], cwd=repo)
    commit_count = int(out.strip()) if out.strip().isdigit() else 0

    branch = _safe_run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo).strip()
    first_date = _safe_run(
        ["git", "log", "--reverse", "--format=%aI", "-n", "1"], cwd=repo
    ).strip().splitlines()
    last_date = _safe_run(["git", "log", "-n", "1", "--format=%aI"], cwd=repo).strip()

    contributors_raw = _safe_run(["git", "shortlog", "-sne", "HEAD"], cwd=repo)
    contributors = []
    for line in contributors_raw.splitlines():
        m = re.match(r"\s*(\d+)\s+(.+)", line)
        if m:
            contributors.append({"commits": int(m.group(1)), "name": m.group(2).strip()})

    recent_raw = _safe_run(
        ["git", "log", "-n", "30", "--format=%h|%aI|%s"], cwd=repo
    )
    recent = []
    for line in recent_raw.strip().splitlines():
        parts = line.split("|", 2)
        if len(parts) == 3:
            recent.append({"sha": parts[0], "date": parts[1], "subject": parts[2]})

    remote = _safe_run(["git", "remote", "get-url", "origin"], cwd=repo).strip()

    return {
        "is_git": True,
        "branch": branch,
        "commit_count": commit_count,
        "first_commit_date": first_date[0] if first_date else None,
        "last_commit_date": last_date or None,
        "contributors": contributors,
        "contributor_count": len(contributors),
        "recent_commits": recent,
        "remote_url": remote,
    }


def file_scan(repo: Path, max_files: int = 30000) -> dict:
    """Walk repo skipping SKIP_DIRS. Count files, LOC by language."""
    file_count = 0
    binary_count = 0
    loc_by_lang: dict[str, int] = {}
    files_by_lang: dict[str, int] = {}
    largest: list[tuple[int, str]] = []

    for path in repo.rglob("*"):
        if file_count > max_files:
            break
        if not path.is_file():
            continue

        # Skip anything under a SKIP_DIRS directory
        try:
            rel = path.relative_to(repo)
        except ValueError:
            continue
        parts = rel.parts
        if any(p in SKIP_DIRS for p in parts):
            continue
        if path.is_symlink():
            continue
        name = path.name
        if name.startswith(".") and name not in {".gitignore", ".env.example"}:
            continue
        if SKIP_FILE_PATTERNS.search(name):
            continue

        file_count += 1
        ext = path.suffix.lower()
        lang = EXT_LANG.get(ext)
        if lang is None:
            # Probably a binary; skip LOC
            try:
                head = path.read_bytes()[:4096]
                if b"\0" in head:
                    binary_count += 1
                    continue
            except OSError:
                continue
            lang = "Other"

        # Count lines (non-binary text)
        try:
            with path.open("rb") as f:
                lines = sum(1 for _ in f)
        except OSError:
            continue

        loc_by_lang[lang] = loc_by_lang.get(lang, 0) + lines
        files_by_lang[lang] = files_by_lang.get(lang, 0) + 1
        # Track top 12 largest source files
        size = path.stat().st_size
        if lang not in {"Markdown", "JSON", "YAML", "TOML", "XML", "Other"}:
            largest.append((size, str(rel)))

    largest.sort(reverse=True)
    sorted_loc = dict(sorted(loc_by_lang.items(), key=lambda x: -x[1]))
    return {
        "file_count": file_count,
        "binary_count": binary_count,
        "loc_total": sum(loc_by_lang.values()),
        "loc_by_lang": sorted_loc,
        "files_by_lang": files_by_lang,
        "primary_language": pick_primary_language(sorted_loc),
        "largest_source_files": [{"path": p, "bytes": s} for s, p in largest[:12]],
    }


def detect_kind(repo: Path) -> dict:
    """Sniff out the project type from manifest files."""
    flags = {
        "is_chrome_extension": (repo / "manifest.json").exists(),
        "is_swift_package": (repo / "Package.swift").exists(),
        "is_xcode_project": any(repo.glob("*.xcodeproj")) or any(repo.glob("*.xcworkspace")),
        "is_node_project": (repo / "package.json").exists(),
        "is_python_project": (repo / "pyproject.toml").exists() or (repo / "setup.py").exists()
            or (repo / "requirements.txt").exists(),
        "is_rust_project": (repo / "Cargo.toml").exists(),
        "is_expo_project": (repo / "app.json").exists() and (repo / "package.json").exists(),
        "is_tauri_project": any(repo.glob("**/tauri.conf.json")) and not any(
            "node_modules" in str(p) for p in repo.glob("**/tauri.conf.json")
        ),
        "is_go_project": (repo / "go.mod").exists(),
    }
    return {k: v for k, v in flags.items() if v}


def parse_deps(repo: Path) -> dict:
    """Pull dependency lists from common manifests. Cheap, best-effort."""
    deps: dict[str, list[str]] = {}

    # package.json
    pj = repo / "package.json"
    if pj.exists():
        try:
            data = json.loads(pj.read_text(encoding="utf-8"))
            ds = list((data.get("dependencies") or {}).keys())
            dd = list((data.get("devDependencies") or {}).keys())
            deps["npm"] = sorted(ds)
            deps["npm_dev"] = sorted(dd)
        except (json.JSONDecodeError, OSError):
            pass

    # Cargo.toml — very light parse, just look for [dependencies] block
    ct = repo / "Cargo.toml"
    if ct.exists():
        try:
            text = ct.read_text(encoding="utf-8")
            in_deps = False
            crates: list[str] = []
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith("[") and stripped.endswith("]"):
                    in_deps = stripped in {"[dependencies]", "[dev-dependencies]"}
                    continue
                if in_deps and "=" in stripped and not stripped.startswith("#"):
                    name = stripped.split("=")[0].strip()
                    if name:
                        crates.append(name)
            deps["cargo"] = sorted(set(crates))
        except OSError:
            pass

    # Package.swift — list dependencies via regex
    ps = repo / "Package.swift"
    if ps.exists():
        try:
            text = ps.read_text(encoding="utf-8")
            pkgs = re.findall(r'\.package\([^)]*url:\s*"([^"]+)"', text)
            local = re.findall(r'\.package\([^)]*path:\s*"([^"]+)"', text)
            deps["spm"] = sorted(set(pkgs))
            if local:
                deps["spm_local"] = sorted(set(local))
        except OSError:
            pass

    # requirements.txt / pyproject.toml
    rt = repo / "requirements.txt"
    if rt.exists():
        try:
            pkgs = []
            for line in rt.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("-"):
                    continue
                name = re.split(r"[=<>!~\[]", line)[0].strip()
                if name:
                    pkgs.append(name)
            deps["pip"] = sorted(set(pkgs))
        except OSError:
            pass

    pt = repo / "pyproject.toml"
    if pt.exists() and "pip" not in deps:
        try:
            text = pt.read_text(encoding="utf-8")
            block = re.search(r"dependencies\s*=\s*\[(.*?)\]", text, re.DOTALL)
            if block:
                pkgs = re.findall(r'"([^"]+)"', block.group(1))
                names = [re.split(r"[=<>!~ ]", p)[0] for p in pkgs]
                deps["pip"] = sorted(set(n for n in names if n))
        except OSError:
            pass

    # Chrome extension permissions
    mj = repo / "manifest.json"
    if mj.exists():
        try:
            data = json.loads(mj.read_text(encoding="utf-8"))
            perms = data.get("permissions") or []
            host_perms = data.get("host_permissions") or []
            if perms:
                deps["chrome_permissions"] = sorted(perms)
            if host_perms:
                deps["chrome_host_permissions"] = sorted(host_perms)
        except (json.JSONDecodeError, OSError):
            pass

    return deps


def parse_version(repo: Path) -> str | None:
    """Best-effort version extraction."""
    for f, key in [("manifest.json", "version"), ("package.json", "version"), ("app.json", "version")]:
        p = repo / f
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                expo = data.get("expo")
                if isinstance(expo, dict) and "version" in expo:
                    return str(expo["version"])
                if key in data:
                    return str(data[key])
            except (json.JSONDecodeError, OSError):
                pass

    # Cargo.toml
    ct = repo / "Cargo.toml"
    if ct.exists():
        try:
            text = ct.read_text(encoding="utf-8")
            m = re.search(r'^\s*version\s*=\s*"([^"]+)"', text, re.MULTILINE)
            if m:
                return m.group(1)
        except OSError:
            pass

    # VERSION file
    vf = repo / "VERSION"
    if vf.exists():
        try:
            return vf.read_text(encoding="utf-8").strip()
        except OSError:
            pass
    return None


def docs_present(repo: Path) -> dict:
    """Which canonical docs exist at repo root."""
    check = [
        "README.md", "README.rst", "README", "LICENSE",
        "CHANGELOG.md", "BUGS_AND_ITERATIONS.md",
        "plan.md", "research.md", "PLAN.md", "RESEARCH.md",
        "audit-meta.yml", "audit-meta.yaml",
        "PRE-PUBLIC-CHECKLIST.md", "PUBLIC-LAUNCH-PLAN.md",
        "CLAUDE.md", "AGENTS.md", "ARCHITECTURE.md", "CONTRIBUTING.md",
    ]
    return {f: (repo / f).exists() for f in check}


CORE_LOOP_CANDIDATES = [
    # (filename-or-pattern, role)
    ("background.js", "Chrome extension service worker / background"),
    ("service_worker.js", "Chrome extension service worker"),
    ("content.js", "Chrome extension content script"),
    ("manifest.json", "Chrome extension manifest"),
    ("main.py", "Python entry point"),
    ("__main__.py", "Python module entry"),
    ("app.py", "Python web app entry"),
    ("main.rs", "Rust binary entry"),
    ("lib.rs", "Rust library root"),
    ("main.go", "Go entry point"),
    ("index.js", "JavaScript entry"),
    ("index.ts", "TypeScript entry"),
    ("App.tsx", "React app root"),
    ("App.jsx", "React app root"),
]


def find_core_loop(repo: Path, file_scan_result: dict) -> dict | None:
    """Heuristic: best guess at THE core loop file.

    Strategy:
      1. Look for canonical entry points (App.swift, main.py, background.js…)
      2. Fall back to largest non-test source file
    """
    # Pass 1: canonical names
    for name, role in CORE_LOOP_CANDIDATES:
        for cand in repo.rglob(name):
            try:
                rel = cand.relative_to(repo)
            except ValueError:
                continue
            if any(p in SKIP_DIRS for p in rel.parts):
                continue
            return {"path": str(rel), "role": role, "source": "canonical-name"}

    # Pass 2: Swift App entry (*App.swift)
    for cand in repo.rglob("*App.swift"):
        try:
            rel = cand.relative_to(repo)
        except ValueError:
            continue
        if any(p in SKIP_DIRS for p in rel.parts):
            continue
        if any(p.lower() in {"tests", "test"} for p in rel.parts):
            continue
        return {"path": str(rel), "role": "SwiftUI app entry", "source": "pattern-match"}

    # Pass 3: largest non-test, non-markdown source file
    for entry in file_scan_result.get("largest_source_files", []):
        p = entry["path"]
        lower = p.lower()
        if "test" in lower or "spec" in lower:
            continue
        return {"path": p, "role": "largest source file", "source": "size-heuristic"}

    return None


def read_first_lines(repo: Path, rel_path: str, max_lines: int = 80) -> str | None:
    """Return up to max_lines of a file, for the Core Loop preview."""
    f = repo / rel_path
    if not f.exists() or not f.is_file():
        return None
    try:
        with f.open(encoding="utf-8", errors="replace") as fh:
            return "".join([fh.readline() for _ in range(max_lines)])
    except OSError:
        return None


def read_audit_meta(repo: Path) -> dict:
    """Parse audit-meta.yml at repo root. Very small subset of YAML, no PyYAML dep."""
    for name in ("audit-meta.yml", "audit-meta.yaml"):
        p = repo / name
        if not p.exists():
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        try:
            import yaml  # type: ignore
            return yaml.safe_load(text) or {}
        except ImportError:
            return _tiny_yaml(text)
    return {}


def _tiny_yaml(text: str) -> dict:
    """Last-resort YAML parser for the keys we actually use in audit-meta.yml.

    Handles: top-level strings/numbers, lists of strings, simple list-of-dicts.
    """
    out: dict = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        if not line.startswith(" ") and ":" in line:
            key, _, rest = line.partition(":")
            key = key.strip()
            rest = rest.strip()
            if rest:
                rest = rest.strip("\"' ")
                if rest.lstrip("-").isdigit():
                    out[key] = int(rest)
                else:
                    out[key] = rest
                i += 1
                continue
            # block — gather indented children
            children: list = []
            i += 1
            current: dict | None = None
            while i < len(lines) and (lines[i].startswith(" ") or not lines[i].strip()):
                cline = lines[i]
                if not cline.strip():
                    i += 1
                    continue
                stripped = cline.strip()
                if stripped.startswith("- "):
                    rest = stripped[2:].strip()
                    if ":" in rest and not rest.startswith('"'):
                        k2, _, v2 = rest.partition(":")
                        current = {k2.strip(): v2.strip().strip("\"'")}
                        children.append(current)
                    else:
                        children.append(rest.strip("\"'"))
                        current = None
                elif current is not None and ":" in stripped:
                    k2, _, v2 = stripped.partition(":")
                    current[k2.strip()] = v2.strip().strip("\"'")
                i += 1
            out[key] = children
        else:
            i += 1
    return out


def run_ls_check(repo: Path) -> dict | None:
    """Run ls-check --json if the tool is available. Returns score+warnings or None."""
    out = _safe_run(["ls-check", str(repo), "--json"], timeout=60)
    if not out:
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


def collect_failures(repo: Path) -> list[dict]:
    """Parse BUGS_AND_ITERATIONS.md headings for the Failures section."""
    for name in ("BUGS_AND_ITERATIONS.md", "BUGS.md", "ITERATIONS.md"):
        f = repo / name
        if not f.exists():
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except OSError:
            continue
        entries: list[dict] = []
        # Match headings like "## BUG-001 — Title (2026-03-21)" or just "## Bug: ..."
        for m in re.finditer(r"^#{2,3}\s+(.+?)$", text, re.MULTILINE):
            heading = m.group(1).strip()
            if any(k in heading.upper() for k in ["BUG", "ITER", "FIX", "FAIL"]):
                entries.append({"title": heading})
            if len(entries) >= 25:
                break
        return entries
    return []


def now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def compute_efficiency(repo: Path, fs: dict, deps: dict) -> dict:
    """Karpathy-style efficiency ratios: LOC/feature, deps/kloc, test/source.

    Auto-derived but the kind of "real numbers" he expects in any audit.
    """
    loc_total = fs.get("loc_total") or 0
    files_total = fs.get("file_count") or 1
    loc_by = fs.get("loc_by_lang") or {}

    # Source LOC = code-language LOC (per pick_primary_language's filter)
    source_loc = sum(v for k, v in loc_by.items() if k not in NON_CODE_LANGS)
    source_file_count = sum(
        c for k, c in (fs.get("files_by_lang") or {}).items()
        if k not in NON_CODE_LANGS
    ) or 1

    # Walk for tests: count LOC under test/tests/__tests__/Tests
    test_loc = 0
    if repo.is_dir():
        for tdir in ("tests", "test", "__tests__", "Tests", "spec"):
            tpath = repo / tdir
            if not tpath.is_dir():
                continue
            for f in tpath.rglob("*"):
                if not f.is_file():
                    continue
                if f.suffix.lower() not in EXT_LANG:
                    continue
                if EXT_LANG.get(f.suffix.lower()) in NON_CODE_LANGS:
                    continue
                try:
                    with f.open("rb") as fh:
                        test_loc += sum(1 for _ in fh)
                except OSError:
                    continue

    dep_count = sum(len(v) for k, v in deps.items()
                    if k in ("npm", "spm", "cargo", "pip"))

    eff = {
        "source_loc": source_loc,
        "source_file_count": source_file_count,
        "loc_per_source_file": (source_loc / source_file_count) if source_file_count else None,
        "deps_total": dep_count,
        "deps_per_kloc": (dep_count / (source_loc / 1000)) if source_loc >= 1000 else None,
        "test_loc": test_loc,
        "test_to_source_ratio": (test_loc / source_loc) if source_loc > 0 else None,
    }
    return eff


def collect_all(repo: Path) -> dict:
    """Top-level convenience: run every instrument, return one dict."""
    fs = file_scan(repo)
    g = git_info(repo)
    deps = parse_deps(repo)
    kind = detect_kind(repo)
    return {
        "audited_at": now_iso(),
        "name": repo.name,
        "local_path": str(repo),
        "git": g,
        "files": fs,
        "kind": kind,
        "deps": deps,
        "version": parse_version(repo),
        "docs": docs_present(repo),
        "core_loop": find_core_loop(repo, fs),
        "audit_meta": read_audit_meta(repo),
        "ls_check": run_ls_check(repo),
        "failures": collect_failures(repo),
        "efficiency": compute_efficiency(repo, fs, deps),
    }
