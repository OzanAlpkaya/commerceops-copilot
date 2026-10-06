from pathlib import Path

from sqlalchemy import Engine, text

from mock_api.seed.config import SeedConfig
from mock_api.seed.dataset import SeedDataset, build_dataset
from mock_api.seed.load import load_dataset, table_checksums
from mock_api.seed.olist import OlistData
from mock_api.seed.returns import NOTE_TEMPLATES

README = Path(__file__).parents[2] / "README.md"


def test_build_is_deterministic(
    olist_data: OlistData, seed_config: SeedConfig, dataset: SeedDataset
) -> None:
    assert build_dataset(olist_data, seed_config) == dataset


def test_seed_changes_the_data(
    olist_data: OlistData, seed_config: SeedConfig, dataset: SeedDataset
) -> None:
    other = build_dataset(olist_data, seed_config.model_copy(update={"seed": 7}))
    assert [c.name for c in other.customers] != [c.name for c in dataset.customers]


def test_load_is_idempotent(db_engine: Engine, dataset: SeedDataset) -> None:
    load_dataset(db_engine, dataset)
    with db_engine.connect() as conn:
        first = table_checksums(conn)
        conn.execute(text("INSERT INTO idempotency_keys VALUES ('c', 'k', 'h', 201, '{}', now())"))
        conn.commit()

    load_dataset(db_engine, dataset)

    with db_engine.connect() as conn:
        assert table_checksums(conn) == first
        assert conn.execute(text("SELECT count(*) FROM orders")).scalar_one() == len(dataset.orders)
        assert conn.execute(text("SELECT count(*) FROM idempotency_keys")).scalar_one() == 0
        next_return = conn.execute(
            text("SELECT 'RMA-' || nextval('return_number_seq')")
        ).scalar_one()
        assert next_return == f"RMA-{100001 + len(dataset.returns.returns)}"


def test_readme_lists_every_note_template() -> None:
    """The Day 3 Slack-exceptions corpus is written against the README copy."""
    readme = README.read_text()
    for note_id, template in NOTE_TEMPLATES.items():
        assert f"| `{note_id}` |" in readme
        assert template in readme, note_id
