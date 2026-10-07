"""Seed tests run on the small synthetic Olist dataset in mock_api.seed.fixture."""

from pathlib import Path

import pytest

from mock_api.seed.config import SeedConfig
from mock_api.seed.dataset import SeedDataset, build_dataset
from mock_api.seed.fixture import fixture_config, write_olist_fixture
from mock_api.seed.olist import OlistData, load_olist


@pytest.fixture(scope="session")
def olist_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    directory = tmp_path_factory.mktemp("olist")
    write_olist_fixture(directory)
    return directory


@pytest.fixture(scope="session")
def olist_data(olist_dir: Path) -> OlistData:
    return load_olist(olist_dir)


@pytest.fixture(scope="session")
def seed_config(olist_dir: Path) -> SeedConfig:
    return fixture_config(olist_dir)


@pytest.fixture(scope="session")
def dataset(olist_data: OlistData, seed_config: SeedConfig) -> SeedDataset:
    return build_dataset(olist_data, seed_config)
