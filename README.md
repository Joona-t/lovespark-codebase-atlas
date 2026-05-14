# LoveSpark Codebase Atlas Public

Karpathy-style audit of every Joona-t public repo. Each repo gets an HTML
page explaining what it does, the data flow, the core loop, the decisions, the
trade-offs, and what would change in v0.next.

**This repo is generated.** Don't hand-edit `audit/*.html` or `index.html` —
the source pipeline (`atlas-discover` → `atlas-audit` → `atlas-index` →
`atlas-publish`) regenerates them on every push to any audited repo.

To override the auto-generated content for a repo, add `audit-meta.yml` at
that repo's root with any of: `tier`, `tldr`, `data`, `architecture`,
`decisions`, `tradeoffs`, `v_next`, `takeaway`, `reproducibility`.

## Snapshot

- Visibility: **public**
- Audited repos: **41**
- Generator: atlas v0.1.0
- Pipeline source: `Claude x LoveSpark/scripts/atlas/` (private)

## Karpathy lens

Each audit follows the same Karpathy-inspired flow:

1. TL;DR
2. The Data (inputs / outputs / shape)
3. The Architecture (C4 diagram + components)
4. The Core Loop (THE one important file, line by line)
5. The Stack (every meaningful dep + why)
6. The Decisions (chronological log + rationale)
7. The Trade-offs (what got cut)
8. The Metrics (LOC / files / scores)
9. The Failures (bugs >1h + reversed decisions)
10. v0.next (what would change today)
11. Reproducibility (exact clone + run commands)
12. The Karpathy Takeaway (1–3 transferable lessons)

## Research foundation

Built on patterns from RepoAgent (Sun et al., 2024), Agentless (Xia et al., 2024),
AlphaCodium (Ridnik et al., 2024), the C4 Model (Brown), and Karpathy's nanoGPT
/ nanochat pedagogical style.

## License

MIT. See [LICENSE](LICENSE).
