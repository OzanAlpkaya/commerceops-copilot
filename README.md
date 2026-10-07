# CommerceOps Copilot

AI assistant for e-commerce support and operations teams, built as a simulated
Forward Deployed Engineer engagement with a fictional client (Lumora Home).

**Status:** Week 1 — Discovery & prototype (in progress)

- Discovery summary: [docs/01-discovery.md](docs/01-discovery.md)

## Data

- Order data in the mock order system is derived from the
  [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
  (CC BY-NC-SA 4.0). The raw files are not committed; `make seed` reads them from
  `data/raw/olist/`.
- The client's document corpus (`data/corpus/`, `data/ground_truth/`) is synthetic and
  generated with `make corpus`. Supplier PDFs carry Olist-derived prices and dimensions, so
  they are generated locally into `data/generated/` and not committed.
- The local question pool is filtered from the
  [Bitext customer-support dataset](https://huggingface.co/datasets/bitext/Bitext-customer-support-llm-chatbot-training-dataset),
  (c) Bitext Innovations, 2024, under CDLA-Sharing-1.0. It is not committed; data derived
  from it and published must carry the same licence.
