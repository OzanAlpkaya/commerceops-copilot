# Progress

## Week 1 — Discovery & prototype

Status: In progress
Branch: `week-1-discovery-prototype`

### Definition of Done

- [x] Discovery summary written (`docs/01-discovery.md`)
- [x] Repo skeleton: uv workspace, ruff, pyright, pytest, pre-commit
- [x] Local Postgres with pgvector via Docker Compose
- [x] Makefile and CI running `make check`
- [x] `CLAUDE.md`, `PROGRESS.md`, `docs/ROADMAP.md` and Claude Code skills
      (`/week-start`, `/week-close`, `/review`)
- [x] Mock customer API: orders, customers, products, shipments, returns; API key
      auth, rate limit, cursor pagination
- [x] Seed data from the Olist dataset loaded with `make seed`
- [ ] Document corpus: return policy (two versions, three undecided rules), Slack
      exceptions export, Zendesk macros, supplier PDFs with ground truth
- [ ] Ingestion and hybrid retrieval (pgvector + full-text search, RRF) with
      `make ingest`
- [ ] Reranking and cited answer generation; undecided rules are flagged, not
      answered
- [ ] `POST /ask` endpoint with read-only order context from the mock API
- [ ] Minimal UI for the demo
- [ ] `make up` starts the full stack; README quickstart
- [ ] 3-minute demo video

### Notes

**Day 1 — discovery and skeleton**

- Discovery done as a client role-play (Selin, then Burak and Emre). Key finding: part
  of the inconsistency comes from the policy itself, not from the agents.
- Fedora setup issues: uv does not download Python (installed 3.12 with dnf), SELinux
  needs `:Z` on bind mounts, ports 5432/5433 are taken locally (this repo uses 5434).
- pre-commit only checks tracked files; a hook that fixes a file stops the commit.

**Day 2 — mock customer API and seed**

- Claude Code wrote the mock API and seed from an approved plan, in two checkpoints.
  10 commits, 102 tests, CI green.
- Bug found in the Day 1 scaffolding: with `--import-mode=importlib` the repo's
  `mock_api/` folder shadowed the real package, and the smoke test could never fail.
  Lesson: see a test fail once before trusting it.
- Added `.claude/settings.json` permission rules (allow / ask / deny, `.env` denied)
  to cut routine approval prompts.

**For later**

- Return eligibility must take "today" from config, not the system clock. The seed is
  fixed at `AS_OF = 2026-10-05`, while returns created through the API use the real
  clock. Otherwise eligibility answers and eval expectations drift day by day.
- Finding for the client: in the EU the statutory withdrawal period is 14 days from
  delivery. Policy v2 ("30 days from order date") leaves less than that when delivery
  takes more than 16 days. Raise it with Selin and legal; not a fourth undecided rule.
- `.dockerignore` excludes `copilot/src/`; change it when the copilot image is added.
