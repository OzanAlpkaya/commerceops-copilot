"""Build the Slack export and the Zendesk macros from a seed dataset."""

from dataclasses import dataclass

from lumora_corpus.layout import Layout, replace_dir
from lumora_corpus.support.cases import SeedCase, decided_cases
from lumora_corpus.support.slack import SlackExport, build_slack
from lumora_corpus.support.zendesk import build_zendesk
from mock_api.policy import PolicyParams
from mock_api.seed.dataset import SeedDataset


@dataclass(frozen=True, slots=True)
class SupportCorpus:
    cases: dict[str, list[SeedCase]]
    slack: SlackExport
    zendesk: dict[str, bytes]  # relative path -> content


def build_support(ds: SeedDataset, seed: int, policy: PolicyParams) -> SupportCorpus:
    cases = decided_cases(ds)
    return SupportCorpus(
        cases=cases,
        slack=build_slack(cases, seed, policy.versions.v2.orders_from),
        zendesk=build_zendesk(cases, policy),
    )


def write_support(support: SupportCorpus, layout: Layout) -> None:
    replace_dir(layout.slack, support.slack.files)
    replace_dir(layout.zendesk, support.zendesk)
