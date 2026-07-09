"""gh_path — resolve an absolute path to the `gh` CLI binary.

Root cause fixed here: launchd LaunchAgents run with whatever PATH is set in
the plist's EnvironmentVariables block (or a bare-bones default PATH if none
is set). If that PATH doesn't include gh's install directory, every
`subprocess.run(["gh", ...])` call raises FileNotFoundError — not a gh error,
a Python-can't-find-the-executable error. This bit atlas-nightly silently for
~2 months (see week-0/cron-reliability.md in the ship-roadmap repo).

Belt-and-suspenders fix: don't rely on the launchd plist PATH alone (it can
drift/regress). Resolve gh's absolute path once, checking shutil.which()
first (respects whatever PATH is actually set) and falling back to the known
install locations on this machine. Callers should use GH_BIN in their
subprocess cmd list instead of the bare string "gh".
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

# Known install locations, in priority order. gh is installed via the
# `gh` self-update mechanism into ~/.local/opt on this machine (symlinked
# from ~/.local/bin/gh) — see `ls -la ~/.local/bin/gh`. Homebrew paths are
# included as fallbacks in case gh is ever reinstalled via brew.
_CANDIDATES = [
    "/Users/darkfire/.local/bin/gh",
    "/opt/homebrew/bin/gh",
    "/usr/local/bin/gh",
]


def resolve_gh() -> str:
    """Return an absolute path to the gh binary, or exit loudly if none found.

    Never returns a bare "gh" — every caller gets something subprocess can
    actually exec regardless of what PATH the calling process inherited.
    """
    found = shutil.which("gh")
    if found:
        return found
    for candidate in _CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    # Fail loud, not silent: this is exactly the class of bug we're
    # eliminating. Don't return "gh" and let a bare FileNotFoundError
    # traceback be the only signal three subprocess frames deep.
    print(
        "[gh_path] FATAL: gh CLI not found via shutil.which() or any known "
        f"install location ({_CANDIDATES}). Install gh or update _CANDIDATES "
        "in scripts/atlas/lib/gh_path.py.",
        file=sys.stderr,
    )
    sys.exit(1)


GH_BIN = None  # lazily resolved via resolve_gh() by callers that import this
