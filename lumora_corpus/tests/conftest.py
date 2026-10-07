from pathlib import Path

import pytest

from lumora_corpus.layout import Layout
from lumora_corpus.params import policy_params
from lumora_corpus.policies.build import RenderedDoc, build_policies
from mock_api.policy import PolicyParams

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
