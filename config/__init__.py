"""Compatibility shim for legacy imports.

Allows importing `config.environment` and `config.settings` while the
actual implementation lives under `product.configs`.
"""

from product.configs.environment import *  # noqa: F401,F403
from product.configs.settings import *  # noqa: F401,F403

__all__ = []  # re-exported by the imported modules


