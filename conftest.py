"""Import the workspace packages before pytest imports any test module.

With --import-mode=importlib, pytest names mock_api/tests/conftest.py
"mock_api.tests.conftest" and, if "mock_api" is not in sys.modules yet, creates it as a
namespace package for the repo's mock_api/ directory. That empty module shadows the real
package (mock_api/src/mock_api). Importing the real packages here, first, prevents it.
"""

import copilot  # noqa: F401
import mock_api  # noqa: F401
