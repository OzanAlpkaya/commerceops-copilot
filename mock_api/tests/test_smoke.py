from pathlib import Path

import mock_api


def test_package_imports() -> None:
    # A namespace module for the repo's mock_api/ directory would have no __file__.
    assert mock_api.__file__ is not None
    assert Path(mock_api.__file__).parent.parent.name == "src"
