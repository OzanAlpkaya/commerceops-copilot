"""python -m lumora_corpus: build Lumora Home's document corpus.

Deterministic and idempotent: every run rewrites the same files with the same bytes.
"""

import argparse
import sys
from pathlib import Path

from lumora_corpus.layout import Layout
from lumora_corpus.params import policy_params
from lumora_corpus.policies.build import build_policies, write_policies


def _policies(layout: Layout) -> None:
    docs = build_policies(policy_params())
    write_policies(docs, layout)
    for doc in docs:
        print(f"  {layout.policies / doc.pdf_name}  ({len(doc.pages)} pages)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m lumora_corpus", description=__doc__)
    parser.add_argument("part", choices=["policies"], help="what to build")
    parser.add_argument("--root", type=Path, default=Path("."), help="repository root")
    args = parser.parse_args(argv)
    layout = Layout(args.root)

    if args.part == "policies":
        print("Policy documents:")
        _policies(layout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
