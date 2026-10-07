"""python -m lumora_corpus: build Lumora Home's document corpus.

Deterministic and idempotent: every run rewrites the same files with the same bytes.
Everything except the policy documents is built from the seed dataset, which needs the
Olist CSVs in data/raw/olist/ (see mock_api/README.md); the dataset is built in memory
with the same settings as `make seed`, so no database is needed.
"""

import argparse
import sys
from pathlib import Path

from lumora_corpus.layout import Layout, write_file
from lumora_corpus.manifest import build_manifest, manifest_yaml
from lumora_corpus.params import policy_params
from lumora_corpus.policies.build import RenderedDoc, build_policies, write_policies
from lumora_corpus.support.build import SupportCorpus, build_support, write_support
from mock_api.seed.config import SeedConfig
from mock_api.seed.dataset import SeedDataset, build_dataset
from mock_api.seed.olist import load_olist

PARTS = ("all", "policies", "support")


class MissingOlist(Exception):
    pass


def _seed(layout: Layout) -> tuple[SeedDataset, SeedConfig]:
    if not layout.olist.is_dir():
        raise MissingOlist(
            f"{layout.olist} not found. This part is built from the seed dataset and needs the "
            "Olist CSVs (see mock_api/README.md). `python -m lumora_corpus policies` builds the "
            "policy documents without them."
        )
    cfg = SeedConfig(
        source_dir=layout.olist, policy_params=layout.root / "config/policy_params.yaml"
    )
    print(f"Building the seed dataset from {layout.olist} ...", flush=True)
    return build_dataset(load_olist(layout.olist), cfg), cfg


def _policies(layout: Layout) -> list[RenderedDoc]:
    docs = build_policies(policy_params(layout.root / "config/policy_params.yaml"))
    write_policies(docs, layout)
    print("Policy documents:")
    for doc in docs:
        print(f"  {layout.policies / doc.pdf_name}  ({len(doc.pages)} pages)")
    return docs


def _support(layout: Layout, ds: SeedDataset, cfg: SeedConfig) -> SupportCorpus:
    support = build_support(ds, cfg.seed, cfg.policy)
    write_support(support, layout)
    print(f"Slack export: {layout.slack}  ({len(support.slack.messages)} messages)")
    print(f"Zendesk macros: {layout.zendesk / 'macros.json'}")
    return support


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m lumora_corpus", description=__doc__)
    parser.add_argument("part", choices=PARTS, help="what to build")
    parser.add_argument("--root", type=Path, default=Path("."), help="repository root")
    args = parser.parse_args(argv)
    layout = Layout(args.root)

    try:
        if args.part == "policies":
            _policies(layout)
        elif args.part == "support":
            _support(layout, *_seed(layout))
        else:
            ds, cfg = _seed(layout)
            docs = _policies(layout)
            support = _support(layout, ds, cfg)
            manifest = build_manifest(docs, support, ds, cfg.policy, cfg.seed)
            write_file(layout.manifest, manifest_yaml(manifest))
            print(f"Manifest: {layout.manifest}  ({len(manifest.difficulties)} difficulties)")
    except MissingOlist as e:
        print(f"corpus failed: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
