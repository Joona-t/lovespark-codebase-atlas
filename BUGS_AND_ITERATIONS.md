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
