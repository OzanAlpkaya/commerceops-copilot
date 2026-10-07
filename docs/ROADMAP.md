# Roadmap

Four one-week sprints that follow a real Forward Deployed Engineer engagement:
discover and prototype, prove it works, connect it to the client's systems, then
deploy and hand over. Client context and constraints: `docs/01-discovery.md`.

Each week ends with a short written document and a client demo.
Each week also includes 2–3 hours of interview preparation (client role-play,
live Python coding with a vague spec, AI system design, past stories); it is
tracked in the weekly retro, not in the Definition of Done.

## Ownership

Who writes each area. Claude Code follows this table (see `CLAUDE.md`).

| Area | Written by | Claude Code's role |
| --- | --- | --- |
| Scaffolding, Docker, CI, Makefile | Claude Code | Writes; Ozan reviews |
| Terraform and AWS setup | Claude Code | Writes; Ozan reviews and must be able to explain the architecture |
| Mock customer API and seed scripts | Claude Code | Writes; Ozan reviews |
| Synthetic data generators | Claude Code | Writes; Ozan designs the deliberate difficulties |
| Demo UI | Claude Code | Writes; Ozan reviews |
| Retrieval: chunking, hybrid search, RRF, reranking | Ozan | Plans, hints, `/review` |
| Evals: test set, metrics, LLM-as-judge, CI eval | Ozan | Plans, hints, `/review` |
| Agent loop, tools, guardrails, approval step | Ozan | Plans, hints, `/review` |
| Return eligibility logic | Ozan | Plans, hints, `/review` |
| Copilot FastAPI service: routes, models, dependencies | Ozan | Glue code only when asked; `/review` |
| Client documents: decision docs, runbook, handover, summaries | Ozan | Reviews |

## Week 1 — Discovery & prototype

Branch: `week-1-discovery-prototype`

Understand the client, scope the pilot, and show a working end-to-end prototype.

### Definition of Done

- [ ] Discovery summary written (`docs/01-discovery.md`)
- [ ] Repo skeleton: uv workspace, ruff, pyright, pytest, pre-commit
- [ ] Local Postgres with pgvector via Docker Compose
- [ ] Makefile and CI running `make check`
- [ ] `CLAUDE.md`, `PROGRESS.md`, `docs/ROADMAP.md` and Claude Code skills
      (`/week-start`, `/week-close`, `/review`)
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

## Week 2 — Evals & reliability

Branch: `week-2-evals-reliability`

Prove with numbers that the copilot answers correctly, consistently and at an
acceptable cost, and show why this approach was chosen.

### Definition of Done

- [ ] Test set of at least 100 questions in `evals/`: policy, order and product
      questions, paraphrase groups, all three undecided rules and out-of-scope
      questions; each with expected answer, expected sources and expected decision
- [ ] Retrieval metrics (recall@k, MRR) computed by `make eval`
- [ ] Answer metrics (correctness, faithfulness, citation validity) using an
      LLM-as-judge, checked against at least 30 hand-labeled answers with the
      agreement rate reported
- [ ] Variants compared in one table (at least: with and without reranking)
- [ ] Eval in CI: a fast subset on every PR, the full run on demand
- [ ] Tracing with Langfuse for every request
- [ ] Cost and latency per request measured (p50/p95, cost per 1,000 questions)
- [ ] Model routing and confidence-based fallback, with the measured effect on
      cost and accuracy
- [ ] README: eval, cost and latency tables
- [ ] Decision document for the client: `docs/decisions/ADR-001-approach.md`
- [ ] 3-minute demo video

## Week 3 — Agents & integration

Branch: `week-3-agents-integration`

Let the copilot act on the client's systems safely, and extract structured data
from supplier PDFs.

### Definition of Done

- [ ] Tools over the mock API: `get_order`, `get_shipment`, `list_returns`,
      `check_return_eligibility` (deterministic, config-driven), `draft_return`
- [ ] `create_return` behind an explicit approval step and a feature flag, off by
      default, with an idempotency key
- [ ] Error handling for rate limits (429 with Retry-After), 5xx and timeouts
- [ ] Guardrails: undecided policy rules are escalated; eligibility is only stated
      when the tool computed it; inputs are validated
- [ ] Agent mode runs on the eval set; week 1 deterministic routing vs. agent
      compared on accuracy, cost and latency
- [ ] MCP server exposing the same tools
- [ ] Supplier PDF extraction with Pydantic/Instructor into a typed product
      schema, including scanned PDFs
- [ ] Extraction eval against ground truth with field-level accuracy reported
      (target at least 95%)
- [ ] Integration document for the client's IT lead: endpoints used, scopes, rate
      limits, failure modes
- [ ] 3-minute demo video

## Week 4 — Deploy & handover

Branch: `week-4-deploy-handover`

Run the pilot in the client's AWS account and leave the client able to operate it.

### Definition of Done

- [ ] Terraform for AWS eu-central-1: containers on ECS Fargate, RDS Postgres
      with pgvector, Secrets Manager, networking; `terraform destroy` removes
      everything
- [ ] LLM and embedding calls switched to Amazon Bedrock through the provider
      interface; eval re-run with no regression
- [ ] Login for pilot agents via OAuth/OIDC (Amazon Cognito)
- [ ] No secrets in code, images or Terraform state outputs
- [ ] Structured logs, metrics and alarms in CloudWatch: errors, latency, cost
- [ ] Architecture diagram
- [ ] Runbook: deploy, rollback, rotate keys, common failures
- [ ] Handover document for the client's team
- [ ] One-page results summary for a non-technical executive
- [ ] Live demo recorded
- [ ] Case study post and CV lines

## Project Definition of Done

- [ ] All four weeks are Done in `PROGRESS.md`
- [ ] A clean clone runs locally with the README quickstart
- [ ] The README tells the story: problem, approach, results with numbers
- [ ] AWS resources are torn down, or their running cost is documented
