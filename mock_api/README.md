# mock-api: Lumora Home order system (simulated)

A stand-in for Lumora Home's in-house order system: its database (`lumora_commerce`) and,
from checkpoint 2, its REST API. `copilot` treats it as a third-party system and only talks
to it over HTTP.

## Seed

```bash
make up      # Postgres
make seed    # reset lumora_commerce to the seed state (~5 s)
make psql-commerce
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
