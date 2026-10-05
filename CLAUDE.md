# CLAUDE.md

## Project

CommerceOps Copilot is an AI assistant for the support and operations team of
Lumora Home, a fictional mid-size e-commerce company. It is built as a simulated
Forward Deployed Engineer engagement. Read `docs/01-discovery.md` for the client
context, constraints and pilot scope before planning any work.

## Repository layout

- `mock_api/` — the client's order system (simulated). Treat it as a third-party
  system we do not own.
- `copilot/` — our service: ingestion, retrieval, generation, API.
- `infra/` — local database init scripts; Terraform arrives in week 4.
- `docs/` — discovery summary, decision records (`docs/decisions/`), notes.
- `data/` — document corpus and ground truth; `data/raw/` is never committed.

## Architecture rules

- `copilot` never imports from `mock_api`. It talks to it only over HTTP,
  through copilot's own API client.
- `mock_api` and `copilot` use separate databases: `lumora_commerce` and `copilot`.
- Return eligibility is decided by deterministic code driven by config, never by
  the LLM. The LLM explains the decision.
- Write access to the order API (creating returns) stays behind an explicit
  approval step and is off by default.
- Copilot never guesses on undecided policy rules (see the discovery summary);
  it flags them for escalation.
- All LLM and embedding calls go through a provider interface in `copilot`, so
  the provider can change (Amazon Bedrock in week 4).

## Ownership

`docs/ROADMAP.md` lists who writes each area. In Ozan-owned areas (retrieval,
evals, agent loop and guardrails, eligibility logic, the copilot FastAPI service),
do not write or rewrite implementation code or its tests unless Ozan explicitly
asks for it in that message. Offer a plan, hints or `/review` instead.

## Commands

- `make up` / `make down` / `make reset` / `make psql` — local services
- `make lint` / `make format` / `make typecheck` / `make test`
- `make check` — all checks; CI runs the same target. Run it before every commit.

## Conventions

- Python 3.12 in a uv workspace. Add runtime dependencies with
  `uv add --package <mock-api|copilot> <pkg>`; dev tools at the root with
  `uv add --dev <pkg>`. Always commit `uv.lock`.
- Type hints everywhere; pyright in standard mode must pass.
- Pydantic models at every boundary: HTTP, config and LLM output.
- Tests live in `<package>/tests`. Every bug fix comes with a test.
- Code, comments, docs and commit messages are in English.
- Conventional commits: `feat`, `fix`, `chore`, `docs`, `test`, `ci`, `refactor`.

## Workflow

- One branch per week (`week-N-<slug>`), a draft PR from day one, squash-merge at
  the end of the week. No auto-merge.
- Plan before code: propose an implementation plan and wait for approval before
  writing code.
- Skills: `/week-start` opens a week, `/week-close` closes it, `/review` reviews
  Ozan's code in coach mode.
- Tick the matching item in `PROGRESS.md` when a Definition of Done item is done.
