# Atlas — bugs and iterations

Per CLAUDE.md rule #11: log every bug fix and iteration with date, problem,
root cause, and fix. This repo is the published output; the pipeline source
lives in `Claude x LoveSpark/scripts/atlas/`.

## 2026-05-14 · ITER-001 — Bootstrap

Initial atlas pipeline shipped. Phase 0 smoke test:
- 3 Tier 1 deep audits: sparky, glyph-grid-studio, primordial
- atlas-discover.py enumerates 180 repos from gh CLI
- atlas-audit.py runs per repo; deterministic instruments only (no LLM yet)
- atlas-index.py emits searchable index
- atlas-publish.py splits public/private cleanly

Known gaps (to be addressed in subsequent phases):
- Phase 1: LLM enrichment via `claude -p` subprocess for narrative sections
- Phase 2: GH Action template + nightly cron backstop
- Phase 3: Tier 2 medium audits
- Phase 4: Tier 3 bulk cards (145 repos)
- Phase 5: CLAUDE.md integration + scaffold hooks

## 2026-07-08 · BUG-002 / ITER-002 — Nightly cron dead since bootstrap, both mirrors 55 days stale

**Problem:** `com.lovespark.atlas-nightly` (04:00 daily launchd job) was registered
and "running" every night, but every single run had failed since the day it was
installed — both mirrors sat at the 2026-05-14 bootstrap commit, 41/182 public
and 141/182 private repos audited, with no visible error anywhere the swarm
would normally look (`launchctl list` just shows a nonzero last-exit code).

**Root cause:** `~/Library/LaunchAgents/com.lovespark.atlas-nightly.plist` hardcodes
`EnvironmentVariables.PATH = /opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin`.
Both `gh` and `claude` are installed at `/Users/darkfire/.local/bin/` (not
Homebrew), which isn't on that PATH. launchd doesn't source `.zshrc`/`.zprofile`,
so every invocation of `atlas-discover.py` (step 1 of atlas-nightly.py) died
immediately with `FileNotFoundError: [Errno 2] No such file or directory: 'gh'`
before anything else in the pipeline ever ran. Confirmed 51 identical tracebacks
in `~/.claude/data/atlas-logs/atlas-nightly.err.log`, one per missed night since
the plist was created.

**Fix:** added `/Users/darkfire/.local/bin` to the front of the plist's PATH
and set `HOME` explicitly, then `launchctl bootout` + `bootstrap` to reload.
Verified in an env matching the plist exactly (`env -i HOME=... PATH=...`) that
`gh auth status` and `claude --version` both resolve correctly, and that
`atlas-discover.py` now runs end-to-end (220 repos discovered).

**Second bug found in the same pass:** `atlas-publish.py`'s `ensure_local_checkout()`
only handles "valid git checkout" or "doesn't exist" — the real target dirs at
`~/atlas-publish/lovespark-codebase-atlas{,-private}` are neither: they're
leftover files from the very first 2026-05-14 run that wrote content but never
reached `git init`/clone. A real (non-dry-run) publish would have hit
`gh repo clone` against a non-empty non-git directory and failed. Fixed by
wiping the stale non-git dir before cloning (`Claude x LoveSpark/scripts/atlas/atlas-publish.py`).

**Feature added in the same pass:** a red "stale" badge in the shared index
template (`atlas-index.py` → `render_index_html`/`INDEX_JS`/`INDEX_CSS_EXTRA`,
which both this repo's and the private mirror's `index.html` render from via
`atlas_index_helper.build_scoped_index`). A repo's badge shows when
`Date.now() - audited_at > 48h`, evaluated client-side at view time so a page
that isn't regenerated for a while still reports accurately when reopened.

**Verification (smoke test only — per unit scope, did NOT run the full
200-repo nightly or push to the live repos; that's left for tonight's 04:00 run):**
- `atlas-audit-single.py` on one small existing repo (Focus-Bloom) → exit 0,
  `audited_at` correctly stamped with today's timestamp.
- `atlas-index.py` against a scratch copy of the real `data/` dir → confirmed
  the new `isStale()` logic and `stale-badge` class are present in the emitted
  HTML/JS, and that querying the emitted `atlas-data.json` shows the 139
  still-2026-05-14-dated rows as stale-eligible vs. the 1 freshly audited row
  as not.
- `atlas-publish.py --dry-run` against a clean scratch `--target-root` →
  staging + commit-message generation succeed end-to-end.
- Did **not** hand-regenerate the two live `index.html` files in this commit:
  doing so from a manifest rebuilt only out of each mirror's own already-audited
  `audit/*.json` would have silently dropped the "182 total / 41 audited"
  unaudited-repo rows (the real `repos.json` manifest with the full repo
  universe isn't checked into these published mirrors). The badge takes effect
  automatically once tonight's now-fixed cron runs `atlas-index.py`/
  `atlas-publish.py` with the authoritative manifest.

Files touched (pipeline source, not under git — `Claude x LoveSpark/` has no
`.git`, so no separate commit there):
- `~/Library/LaunchAgents/com.lovespark.atlas-nightly.plist`
- `Claude x LoveSpark/scripts/atlas/atlas-publish.py`
- `Claude x LoveSpark/scripts/atlas/atlas-index.py`

## 2026-07-08 · ITER-003 — Phase 4 (Tier-3 bulk cards): coverage gap closed, 41→51 public

**Problem:** Per ITER-002, both atlas mirrors sat at 41/182 public and 141/182
private repos audited (the documented Phase 4 "Tier-3 bulk cards" pass never
shipped — CLAUDE.md rule #13 and the atlas roadmap both flagged it as the last
gap before the pipeline could be called complete).

**Fix:** Ran `atlas-audit.py` deterministic (no-LLM) card-mode audits across
every repo in the manifest that hadn't been covered by the Tier-1/Tier-2 passes.
Combined with re-running `atlas-discover.py` first (fixed in ITER-002), the
manifest now enumerates 220 repos total (was 180/182) — 51 public, 169 private,
all archived repos excluded. Regenerated the public/private-scoped indexes via
`atlas-index.py --public-only` / `--private-only` and staged the complete
`audit/*.{html,json}` set plus refreshed `index.html`/`atlas-meta.json`/`README.md`
into this checkout on the existing `fleet-p0` branch (did not touch `main`,
did not use `atlas-publish.py`'s built-in `git push origin main` — that script
pushes straight to the default branch, which conflicts with this unit's
branch-first policy, so the copy+commit was done by hand instead).

**Coverage: before → after**
- Public: 41/182 → **51/51** (100% of the 51 public repos in the current
  220-repo manifest; the "182" figure in ITER-002 was itself stale — discover
  now finds 220 total repos, not 182, so coverage is reported against the
  current manifest)
- Private: 141/182 → **169/169** (100% of the 169 private repos in the current
  manifest)
- Combined: 182/364 (using the old manifest's stale denominator) → **220/220**
  against the current, correct manifest. Every repo has a `card`, `medium`, or
  `deep` mode audit with no error stubs (spot-checked; `audit_mode` present and
  non-null on all 220 JSON files, zero repos with a missing/`None` mode).

**Verification:** confirmed `data/audit/*.json` in the pipeline working dir has
exactly 220 entries matching `repos.json` 1:1 (0 missing, 0 extra); confirmed
the public/private split is a hard partition (e.g. `glyph-grid-studio`, a
public repo, is present only in the public checkout's `audit/`, absent from
private — `atlas-publish.py`'s privacy guarantee held); spot-checked a Tier-1
deep audit (`sparky`) and several Tier-3 cards (`Aaron-Public-Knowledge-Unblocker`)
for real narrative/description content, not empty stubs.

**Not done in this pass:** did not re-run LLM enrichment on any repo (that's a
separate, slower Phase-1-style pass, out of scope for the Phase-4 bulk-card
unit); did not reinstall/verify the nightly cron itself (covered by ITER-002);
did not merge the `fleet-p0` PRs — left open for review per branch policy.
