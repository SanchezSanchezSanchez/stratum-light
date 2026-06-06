"""Product core package.

This module intentionally avoids importing submodules at package import time
to prevent side effects. Import specific modules directly, e.g.:
`from product.core.analyzer import TokenAnalyzer`.
"""

# Re-export integration_scenarios name for tests that patch
try:
    from . import reporter as integration_scenarios  # type: ignore
except Exception:  # pragma: no cover
    integration_scenarios = None  # type: ignore

__all__ = ["integration_scenarios"]
