"""Seed parameters. Every number that shapes the generated data lives here."""

from datetime import date
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Olist category (Portuguese) -> Lumora category. Orders are kept only when every item is in
# one of these. portateis_cozinha_e_preparadores_de_alimentos has no row in Olist's
# translation CSV, so the mapping is maintained here rather than read from that file.
CATEGORY_MAP: dict[str, str] = {
    "cama_mesa_banho": "bedding_bath",
    "moveis_decoracao": "decor",
    "utilidades_domesticas": "housewares",
    "la_cuisine": "housewares",
    "moveis_escritorio": "home_office",
    "moveis_sala": "living_room",
    "casa_conforto": "home_comfort",
    "casa_conforto_2": "home_comfort",
    "moveis_cozinha_area_de_servico_jantar_e_jardim": "dining_garden",
    "construcao_ferramentas_iluminacao": "lighting",
    "artigos_de_natal": "seasonal",
    "moveis_quarto": "bedroom",
    "portateis_casa_forno_e_cafe": "kitchen_appliances",
    "portateis_cozinha_e_preparadores_de_alimentos": "kitchen_appliances",
    "moveis_colchao_e_estofado": "mattresses",
}


class SeedConfig(BaseSettings):
    """Seed knobs. SEED_* environment variables (or .env) override the defaults."""

    model_config = SettingsConfigDict(env_prefix="SEED_", env_file=".env", extra="ignore")

    source_dir: Path = Path("data/raw/olist")
    # Fixed so order IDs, return windows and eval answers stay stable. Re-anchor on purpose.
    as_of: date = date(2026, 10, 5)
    target_orders: int = 8000
    seed: int = 20260301

    legacy_cutoff: date = date(2025, 9, 1)  # order system v2 go-live
    policy_change: date = date(2026, 3, 1)  # return policy v2 applies from this order date
    # Placeholder policy used only to give seeded returns consistent outcomes:
    # v1 counts the window from delivery, v2 from the order date.
    return_window_days: int = 30

    supplier_count: int = 120
    outlet_share: float = 0.04
    return_rate: float = 0.065

    # Returns generated for each undecided policy rule (split between outcomes).
    quota_window: int = 48
    quota_outlet: int = 24
    quota_coupon: int = 24
    quota_hygiene: int = 36
    # Open returns nobody has decided yet (status "requested", no note): per undecided rule
    # (window, outlet, coupon, hygiene), plus clear-cut eligible and ineligible requests.
    open_per_rule: int = 3
    open_eligible: int = 5
    open_ineligible: int = 4
    # Clear-cut eligible returns in progress (approved or received).
    open_in_progress: int = 8

    # In-transit shipments (see seed/transit.py).
    lost_parcels: int = 8  # current-status shipped orders kept in transit as lost
    lost_min_overdue_days: int = 14  # lost parcels are at least this far past their ETA
    recent_transit_days: int = 10  # "recent" means placed within this many days
    recent_transit: int = 20  # recent orders put in transit (fewer if not enough exist)
    recent_late_share: float = 1 / 3  # of those, already past their ETA
