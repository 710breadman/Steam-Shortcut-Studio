# Board Decisions

## D-001 — Defer source-picture work

- **Proposal:** ignore the source picture until non-visual product work is sorted.
- **Evidence:** direct owner instruction, 2026-07-22.
- **User value:** prevents visual work from hiding correctness and release gaps.
- **Technical value:** protects focus on CI, persistence, identity, workflows, and packaging.
- **Safety impact:** positive.
- **Ruling:** approved; owner override.

## D-002 — Keep the Python core

- **Proposal:** retain existing domain, persistence, controller, and transaction services.
- **Evidence:** mature tested foundations and current roadmap decision.
- **Opposition:** a full UI rewrite could appear cleaner.
- **Ruling:** approved. Toolkit proof may replace views later, never the core by default.

## D-003 — Green CI before expansion

- **Proposal:** stop feature expansion until current Windows failures are fixed.
- **Evidence:** PR #39 Windows CI and Source CLI jobs fail.
- **Ruling:** approved unanimously.

## D-004 — Migration framework before schema features

- **Proposal:** build migration/rollback tests before identity, recipes, or structured-note columns.
- **Safety impact:** critical.
- **Ruling:** approved.

## D-005 — No title-only identity merge

- **Proposal:** exact identifiers and corroborating evidence are required; title-only proposals remain review-required.
- **Ruling:** approved and permanent.

## D-006 — One explicit target Steam profile

- **Proposal:** preview and apply always name one chosen profile.
- **Ruling:** approved. Never default to all profiles.

## D-007 — One unified change plan

- **Proposal:** shortcut, artwork, notes, compatibility, collection, backup, verification, and rollback effects are represented before apply.
- **Ruling:** approved. UI must consume the plan rather than invent write behavior.

## D-008 — Launcher order

- **Proposal:** Playnite, then GOG, then Battle.net; reassess others later.
- **Ruling:** approved subject to fixture and maintenance gates.

## D-009 — Packaging before broad source expansion

- **Proposal:** prove a usable Windows alpha before adding many adapters.
- **Ruling:** approved. One or two adapter sprints may proceed in parallel only after CI and migration foundations are stable.

## D-010 — Explicit repository license required

- **Proposal:** choose and add a root license before public alpha distribution.
- **Ruling:** approved; owner decision required.
