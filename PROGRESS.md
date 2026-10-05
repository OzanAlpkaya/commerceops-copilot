# Progress

## Week 1 — Discovery & prototype

Branch: `week-1-discovery-prototype`

### Definition of Done

- [x] Discovery summary written (`docs/01-discovery.md`)
- [x] Repo skeleton: uv workspace, ruff, pyright, pytest, pre-commit
- [x] Local Postgres with pgvector via Docker Compose
- [x] Makefile and CI running `make check`
- [x] `CLAUDE.md` and `PROGRESS.md`
- [ ] Mock customer API: orders, customers, products, shipments, returns; API key
      auth, rate limit, cursor pagination
- [ ] Seed data from the Olist dataset loaded with `make seed`
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
