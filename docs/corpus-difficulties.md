# Corpus difficulties

Each difficulty is a deliberate trap in the document corpus and becomes test cases in
the week 2 eval set. Client context: `docs/01-discovery.md`.

## General rules

- Language: English. Client: Lumora Home, Ireland, prices in EUR.
- Formats as the client would hand them over: policies as PDF (Markdown sources kept as
  ground truth), Slack export as JSON in Slack's export format, Zendesk macros as a JSON
  export, supplier documents as PDF.
- Single source of truth: `config/policy_params.yaml` holds version dates, window
  lengths and return fees. Documents are generated from it and the seed reads it.
- No statutory periods: the EU 2-year legal guarantee and the 14-day withdrawal period
  appear nowhere in the corpus. They would resolve D4 and contradict the 30-day rules.
  The warranty document says only that it does not affect statutory rights.
- Every difficulty is listed in a machine-readable manifest
  (`data/ground_truth/corpus_manifest.yaml`) with the exact document and section, so
  week 2 evals can target it. Each difficulty gets at least 5 eval questions.
- Size: policies 8–12 pages in total, Slack 60–100 messages, about 25 macros,
  40 supplier PDFs, one promotions document.

## Policy and support documents

### D1 — Two policy versions

- **Where:** `returns-policy-v1.pdf` (in force until 28 Feb 2026) and
  `returns-policy-v2.pdf` (orders placed on or after 1 March 2026).
- **How it looks:** Same title and structure; most paragraphs are identical. v1 is
  marked "Superseded" only in a one-line header. v2 states explicitly that it applies
  to orders placed on or after 1 March 2026.
- **What it tests:** Version selection by order date, near-duplicate retrieval,
  reranking, version metadata on chunks.
- **Expected behaviour:** Answers from the version in force on the order date and names
  that version. If no order is given, states both rules and asks for the order.

### D2 — Return window start contradicts itself

- **Where:** `returns-policy-v2.pdf` §2 "Return window" and §6 "How to return".
- **How it looks:** §2: "You can return items within 30 days of the order date."
  §6, left over from v1: "Send the item back within 30 days of receiving it."
- **What it tests:** Retrieving both conflicting passages, faithfulness, noticing a
  contradiction instead of picking one passage.
- **Expected behaviour:** If both readings give the same answer, answers normally. If the
  request is more than 30 days after the order but within 30 days of delivery, does not
  decide: quotes both clauses and escalates to the team lead.

### D3 — "Campaign item" is never defined

- **Where:** `returns-policy-v2.pdf` §4, `promo-codes-2026.pdf`, the Outlet section of
  `shipping-and-delivery.pdf`.
- **How it looks:** v2: "Campaign items can be exchanged but not refunded." No definition
  anywhere. The promotions document calls codes "campaign codes" ("Spring campaign:
  SPRING15"). The Outlet section says "Outlet items are sold at reduced prices." Neither
  says whether they are campaign items.
- **What it tests:** Not inventing a definition from suggestive wording.
- **Expected behaviour:** For an order with an outlet item or a coupon, states the rule,
  says that "campaign item" is not defined, and escalates. For an order with neither,
  applies the normal rule.

### D4 — Hygiene exception exists only in Slack

- **Where:** §5 "Hygiene items" in both policy versions, `warranty-and-defects.pdf`,
  Slack `#returns-exceptions`.
- **How it looks:** Policy: "Opened pillows, bedding, mattresses and mattress protectors
  cannot be returned for hygiene reasons. The same applies to towels, bathrobes, mattress
  toppers and weighted blankets." (the second sentence covers the other hygiene products
  in the seed). Warranty document: "Defective items can be
  returned for a replacement or refund within 30 days of delivery", with no mention of
  hygiene items. In Slack, the team lead accepts an opened defective duvet "as an
  exception"; other messages show the opposite decision, using the H1/H2 note wording
  from the seed.
- **What it tests:** Conflicting rules across documents; source authority (Slack records
  practice, not policy).
- **Expected behaviour:** States both written rules, mentions the Slack practice as
  informal, flags the case as undecided, and escalates.

### D5 — Exact identifiers

- **Where:** `promo-codes-2026.pdf` (codes with validity and terms), supplier PDFs
  (SKUs), `shipping-and-delivery.pdf` (carrier names).
- **How it looks:** "BOXING25: 25% off your order, 25 December 2025 – 6 January 2026,
  cannot be combined with WELCOME10." Codes, dates and discounts follow the seed's
  campaign table. Similar codes sit next to each other (BF25, XMAS15, BOXING25).
- **What it tests:** Keyword search; the case for hybrid search over vector-only search.
- **Expected behaviour:** Retrieves the passage with the exact code or SKU and never
  answers from a similar one.

### D6 — Answer inside a table

- **Where:** `shipping-and-delivery.pdf` §3 (carrier × service × delivery time × price)
  and the return shipping costs table.
- **How it looks:** Return shipping is free for defective, wrong_item and
  damaged_in_transit; €4.95 is deducted for changed_mind; collection by Hollis Freight
  (items over 20 kg) costs €29. The fees apply to orders placed from 1 March 2026 (policy
  v2); v1 orders get a full refund, and the seed deducts the fees from v2 refunds. The
  delivery table has one row per carrier, split into standard parcels and large items,
  with ranges that cover the seeded delivery times.
- **What it tests:** Table-aware chunking; keeping header rows with their values.
- **Expected behaviour:** Gives the exact figure and cites the table.

### D7 — Cross-reference between documents

- **Where:** `returns-policy-v2.pdf` §5 "Damaged items": "See Shipping & Delivery
  Policy §4." That section sets the rule: report within 7 days of delivery, with photos.
- **What it tests:** Multi-hop retrieval.
- **Expected behaviour:** Combines both passages and cites both documents.

### D8 — Outdated Zendesk macro

- **Where:** Zendesk export, macro "Return – changed mind".
- **How it looks:** Still uses v1 wording: "within 30 days of delivery … full refund".
- **What it tests:** Source priority: policy over macro.
- **Expected behaviour:** Follows policy v2 and points out that the macro is outdated.

### D9 — Internal jargon

- **Where:** Slack export and Zendesk macros.
- **How it looks:** RMA, RTS (returned to sender), DOA (defective on arrival),
  OOW (out of window), SC (store credit).
- **What it tests:** Vocabulary mismatch between plain-language questions and jargon in
  the text; semantic search.
- **Expected behaviour:** Finds the jargon passages from a plain-language question.

### D10 — Deliberate gaps

- **Where:** Nowhere. These topics are absent on purpose: price matching, gift wrapping,
  shipping outside Ireland, extended warranties. Statutory periods (see General rules)
  are absent too; a test checks a list of forbidden terms against every document.
- **What it tests:** Abstention.
- **Expected behaviour:** Says the documents do not cover the topic and suggests
  escalating. Never invents a policy.

## Supplier PDFs

All supplier PDFs describe real products from the seed, using the same SKUs and names.

### P1 — Layout variety

Four templates: single-product spec sheet, multi-product price list (table), two-column
catalogue page, invoice-style delivery note.

- **What it tests:** Parsing and extraction robustness across layouts.

### P2 — Scanned documents

About 20% are rasterised with skew and noise and have no text layer.

- **What it tests:** Detecting a missing text layer and falling back to OCR. Extraction
  accuracy is reported separately for scanned documents.

### P3 — Units and number formats

Dimensions in cm or inches; weights in g, kg or lb; decimal commas ("1.234,50");
prices in EUR or GBP.

- **What it tests:** Normalisation into the schema units (cm, g, EUR), keeping the
  original value.

### P4 — Split tables and missing fields

A price-list table continues on the next page without a repeated header; some products
have no EAN or care instructions.

- **What it tests:** Joining rows across pages. Missing fields stay null and are never
  guessed.

### P5 — Conflicts with the catalogue

About 10% of PDFs give dimensions or materials that differ from the product in the mock
API: the catalogue error from the discovery summary.

- **What it tests:** Week 3 extraction flags the mismatch for catalogue review.
