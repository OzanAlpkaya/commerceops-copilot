"""Where the corpus lives under the repository, and how it is written."""

import shutil
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Layout:
    root: Path

    # Committed: what the client hands over, plus the ground truth.
    @property
    def policies(self) -> Path:
        return self.root / "data" / "corpus" / "policies"

    @property
    def slack(self) -> Path:
        return self.root / "data" / "corpus" / "slack" / "returns-exceptions"

    @property
    def zendesk(self) -> Path:
        return self.root / "data" / "corpus" / "zendesk"

    @property
    def policy_sources(self) -> Path:
        return self.root / "data" / "ground_truth" / "policies"

    @property
    def manifest(self) -> Path:
        return self.root / "data" / "ground_truth" / "corpus_manifest.yaml"

    # Local only (gitignored): Olist-derived or third-party data.
    @property
    def suppliers(self) -> Path:
        return self.root / "data" / "generated" / "suppliers"

    @property
    def question_pool(self) -> Path:
        return self.root / "data" / "generated" / "question_pool"

    @property
    def olist(self) -> Path:
        return self.root / "data" / "raw" / "olist"

    @property
    def bitext_cache(self) -> Path:
        return self.root / "data" / "raw" / "bitext"


def replace_dir(target: Path, files: Mapping[str, bytes]) -> None:
    """Make `target` contain exactly `files` (relative path -> content).

    Files are written to a temporary directory next to `target`, which then replaces it,
    so a failed build never leaves a half-written directory and stale files disappear.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=f".{target.name}-", dir=target.parent))
    try:
        for relative, content in sorted(files.items()):
            path = tmp / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        for directory in [tmp, *(p for p in tmp.rglob("*") if p.is_dir())]:
            directory.chmod(0o755)
        if target.exists():
            shutil.rmtree(target)
        tmp.rename(target)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise


def write_file(target: Path, content: bytes) -> None:
    """Replace one file atomically."""
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f".{target.name}.tmp")
    tmp.write_bytes(content)
    tmp.replace(target)
