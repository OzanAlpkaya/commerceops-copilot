# mock-api: Lumora Home order system (simulated)

A stand-in for Lumora Home's in-house order system: its database (`lumora_commerce`) and
its REST API. `copilot` treats it as a third-party system and only talks to it over HTTP.

```bash
make up      # Postgres + the API on http://localhost:8001
make seed    # reset lumora_commerce to the seed state (~5 s)
curl -H 'X-API-Key: dev-copilot-key' localhost:8001/orders/LH-1004205
```

## API

The client was handed a static spec, served at `GET /openapi.yaml`. It is partly outdated;
the internal section below lists where. FastAPI's generated docs (`/docs`, `/redoc`,
`/openapi.json`) are disabled.

| Endpoint | Notes |
| --- | --- |
| `GET /customers/{id}`, `GET /customers?email=` | Email match is exact and case-insensitive. |
| `GET /orders/{id}` | Includes items with product names. |
| `GET /orders?customer_id=&status=` | Newest first. `status` accepts either enum and matches the stored value. |
| `GET /orders/{id}/shipment` | 404 if the order has no shipment yet. |
| `GET /products/{sku}`, `GET /products?supplier_id=` | By SKU. |
| `GET /returns/{id}`, `GET /returns?order_id=` | Newest first, with items. |
| `POST /returns` | Needs the `write` scope and an `Idempotency-Key` header; creates a `requested` return. |
| `GET /health` | No auth. Checks the database. |

How the API behaves across endpoints:

- **Auth.** `X-API-Key` header, one key per client, from
  `MOCK_API_KEYS=name:key:scopes,...`. The scopes are `read` and `write` (`read+write` for
  both). A missing or unknown key gets 401; a missing scope gets 403.
- **Rate limit.** 100 requests per minute per key, as a sliding window kept in memory (so
  the service runs one worker). Over the limit you get 429 with `Retry-After` in seconds.
  Every response carries `X-RateLimit-Limit` and `X-RateLimit-Remaining`.
- **Pagination.** `limit` (1–100, default 25) and an opaque `cursor`; responses look like
  `{"data": [...], "next_cursor": "..." | null}`. A malformed cursor gets 400.
- **Errors.** Always `{"error": {"code": "...", "message": "..."}}`.
- **Money.** Decimal strings (`"59.90"`), in EUR.
- **Idempotency.** Same key and same body replays the stored 201, with
  `Idempotent-Replayed: true`. Same key with a different body gets 422. Keys are per client,
  and failed requests are not stored.
- **No policy checks on create.** `POST /returns` checks structure only: the order exists
  and is delivered (`delivered` or `COMPLETED`), and the items belong to it with enough
  quantity left. Like the real system, it does not enforce return windows or policy rules.
- **Realism flags** (off by default). `MOCK_API_LATENCY_MS` (`250` or `50-400`) adds
  latency, and `MOCK_API_ERROR_RATE` (0–1) answers that share of requests with a random
  500/502/503. `/health` is exempt from both.

## Seed

```bash
make psql-commerce   # psql on lumora_commerce
```

`make seed` reads the Olist CSVs from `data/raw/olist/` (not committed), connects to
`$POSTGRES_HOST:$POSTGRES_PORT` from `.env`, and prints a summary with table checksums.
The data is a sample of the order system, not its real volume: 8,000 orders over two
years (about 11 a day). Don't use it for load, rate or volume estimates.

It is deterministic and idempotent. Each run drops and recreates every table in one
transaction, so it also wipes returns created through the API and stored idempotency keys.

Knobs live in `src/mock_api/seed/config.py`. `SEED_AS_OF` (default `2026-10-05`) moves the
whole timeline. It is fixed on purpose, because order IDs, return windows and eval answers
depend on it.

### What the seed does

| Step | Rule |
| --- | --- |
| Orders | Olist orders whose items are all in the home & living categories of `CATEGORY_MAP`. Whole customers are sampled down to 8,000 orders. |
| Dates | One offset in whole weeks, so the newest order lands in the week ending on `AS_OF`. Events pushed past `AS_OF` have not happened yet (in-transit orders). |
| Order status | Orders placed before 2025-09-01 keep the legacy enum (`NEW`, `PAID`, `INVOICED`, `PICKING`, `DISPATCHED`, `COMPLETED`, `CANCELLED`). |
| Products | Each product gets a subtype that fits its Olist weight. The subtype sets the name and `is_hygiene`. `is_outlet` is set on ~4% of products by hash. |
| Coupons | Orders with an Olist voucher payment get a campaign code that was live on the order date. `discount_amount` is that code's percentage of the subtotal. |
| Suppliers | 120 suppliers. Olist sellers are dealt into category-specific suppliers. |
| Customers | Faker `en_IE` names, Irish towns and Eircodes, and `@example.*` emails. |
| Shipments | Hollis Freight for orders over 20 kg; otherwise Parcelo, NordPost or SwiftLane Express. |
| In transit | About 20 recent orders are in transit, a third of them a few days past their ETA. 8 lost parcels; other stale Olist shipments are marked delivered near their ETA. Orders with a return are never changed. |
| Returns | 6.5% of delivered orders. Fixed quotas cover the undecided policy rules (decided and still open, below). Every other return has a clear outcome. |

Amounts are Olist's BRL figures relabelled as EUR.

## Internal: deliberate difficulties (do not hand to the client)

### Placeholder policy used by the seed

Seeded return outcomes follow a placeholder policy until the real one is written:

- v1 applies to orders placed before 1 March 2026: 30 days from delivery.
- v2 applies from 1 March 2026: 30 days from the order date.
- Opened hygiene items are not returnable.

Returns that touch none of the undecided rules follow this placeholder policy and carry no
`agent_note`.

### Undecided rules in the data

| Rule | Decided (closed) | Open (`requested`) | What makes a case |
| --- | --- | --- | --- |
| 1. Window start | 48 (`W1`/`W2`) | 3 | v2 order, `changed_mind`, requested after order date + 30 days but within delivery date + 30 days |
| 2. Campaign items | 24 outlet (`C1`/`C2`/`C5`), 24 coupon (`C3`/`C4`/`C5`) | 3 outlet, 3 coupon | `changed_mind` on an outlet item, or on an order with a coupon code, inside the window |
| 3. Hygiene + defective | 36 (`H1`/`H2`) | 3 | `defective` hygiene item with `condition = opened`, inside the window |

Each case touches exactly one rule. Decided cases are old enough to be closed, and their
outcomes are split between team practices to show the inconsistency the discovery found.

### Open returns

About 40 returns are open (`requested`, `approved` or `received`). None has an
`agent_note`, because nobody has decided them yet. Most come from targeted groups
(counts in `seed/config.py`):

| Group | Count | Status | Shape |
| --- | --- | --- | --- |
| Undecided rule | 3 per rule (window, outlet, coupon, hygiene) | `requested` in the last 36 h | As in the table above |
| Clear-cut eligible | 5 | `requested` in the last 36 h | `changed_mind` or `defective`, non-hygiene, non-campaign, inside every window reading |
| Clear-cut ineligible | 4 | `requested` in the last 36 h | `changed_mind`, more than 30 days after delivery |
| In progress | 8 | `approved` or `received` | Clear-cut eligible, requested 3–7 days ago |

The remaining open returns are recent clear cases.

### `agent_note` templates

The Day 3 Slack-exceptions corpus must use this exact wording and the
`#returns-exceptions` channel name. The source of truth is `NOTE_TEMPLATES` in
`src/mock_api/seed/returns.py`, and a test keeps this table in sync with it.

| ID | Rule | Outcome | Template |
| --- | --- | --- | --- |
| `W1` | 1 window | approved, refund | Requested {days_since_order} days after order but {days_since_delivery} days after delivery. Approved, counting the window from delivery. |
| `W2` | 1 window | rejected | Requested {days_since_order} days after order. Rejected: outside the 30-day window from order date (policy v2). |
| `C1` | 2 outlet | approved, exchange | Outlet item. Exchange offered instead of a refund, per team practice for campaign items. |
| `C2` | 2 outlet | approved, refund | Outlet item. Refund approved: no campaign restriction found in the policy. |
| `C3` | 2 coupon | approved, exchange | Coupon order ({coupon_code}). Treated as a campaign item: exchange only. |
| `C4` | 2 coupon | approved, refund | Coupon order ({coupon_code}). Refund approved: coupon orders are not campaign items. |
| `C5` | 2 either | rejected | Campaign item, changed mind. Return rejected; customer offered store credit. |
| `H1` | 3 hygiene | approved, refund | Hygiene item opened but defective. Accepted as an exception, see #returns-exceptions. |
| `H2` | 3 hygiene | rejected | Hygiene item opened. Rejected under the opened-packaging rule; defect claim not assessed. |

### Spec drift

How the static `openapi.yaml` differs from the live API. `tests/api/test_spec_drift.py`
pins this list.

| Where | The spec says | The API does |
| --- | --- | --- |
| Customer | `first_name`, `last_name` | a single `name` |
| Order | `total` | `total_amount`, plus `currency` |
| Order | no `coupon_code` or `discount_amount` | returns both |
| Order status | the current enum only | legacy values for orders before 2025-09-01 |
| Product | no `is_hygiene` or `is_outlet` | returns both |
| Shipment | `eta` and `tracking_url` | `estimated_delivery_at`, and no tracking URL |
| Responses | no 429 or `Retry-After` | rate limits at 100 requests/min |
| Auth | one key, no scopes mentioned | `read` and `write` scopes (403 without `write`) |

### Other traps

- `?status=` matches the stored value literally, so `status=delivered` does not return
  legacy `COMPLETED` orders.
- 25 legacy orders are still `DISPATCHED` with an in-transit shipment, never closed by
  the old system. They are data-quality leftovers, not real parcels.
- 8 current orders are `shipped` and weeks to months past their estimated delivery: lost
  parcels, spread across ages.
- Orders placed in the last 10 days are in transit (fewer than 20 when the sample has
  fewer). About a third are already a few days past their ETA: the "where is my order?"
  cases.
