"""STRATUM_LIGHT top-level package.

This package's ``__init__`` deliberately avoids importing submodules that
perform environment initialization at import time. Import subpackages
directly (e.g., ``product.interfaces.cli.main``) to prevent side effects.
"""

__all__ = []
