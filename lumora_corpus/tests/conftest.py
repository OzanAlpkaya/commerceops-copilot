from pathlib import Path

import pytest

from lumora_corpus.layout import Layout
from lumora_corpus.params import policy_params
from lumora_corpus.policies.build import RenderedDoc, build_policies
from lumora_corpus.support.build import SupportCorpus, build_support
from mock_api.policy import PolicyParams
from mock_api.seed.config import SeedConfig
from mock_api.seed.dataset import SeedDataset, build_dataset
from mock_api.seed.fixture import fixture_config, write_olist_fixture
from mock_api.seed.olist import load_olist

REPO = Path(__file__).parents[2]


@pytest.fixture(scope="session")
def repo_layout() -> Layout:
    return Layout(REPO)


@pytest.fixture(scope="session")
def policy() -> PolicyParams:
    return policy_params(REPO / "config" / "policy_params.yaml")


@pytest.fixture(scope="session")
def policy_docs(policy: PolicyParams) -> dict[str, RenderedDoc]:
    return {d.name: d for d in build_policies(policy)}


@pytest.fixture(scope="session")
def fixture_seed(tmp_path_factory: pytest.TempPathFactory) -> tuple[SeedDataset, SeedConfig]:
    """The small synthetic seed dataset (Olist is not in CI)."""
    directory = tmp_path_factory.mktemp("olist")
    write_olist_fixture(directory)
    cfg = fixture_config(directory)
    return build_dataset(load_olist(directory), cfg), cfg


@pytest.fixture(scope="session")
def fixture_support(fixture_seed: tuple[SeedDataset, SeedConfig]) -> SupportCorpus:
    ds, cfg = fixture_seed
    return build_support(ds, cfg.seed, cfg.policy)


@pytest.fixture(scope="session")
def real_seed(repo_layout: Layout) -> tuple[SeedDataset, SeedConfig]:
    """The real seed dataset; local only, as it needs the Olist CSVs."""
    if not repo_layout.olist.is_dir():
        pytest.skip("needs the Olist CSVs in data/raw/olist")
    cfg = SeedConfig(
        _env_file=None,  # type: ignore[call-arg]
        source_dir=repo_layout.olist,
        policy_params=REPO / "config" / "policy_params.yaml",
    )
    return build_dataset(load_olist(repo_layout.olist), cfg), cfg
