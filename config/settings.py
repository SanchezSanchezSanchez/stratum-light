"""Compatibility shim for legacy import path `config.settings`.

Re-exports specific names from `product.configs.settings`.
"""

from product.configs.settings import ConfigManager, config  # noqa: F401
from product.configs.schemas import MainConfig  # re-export for tests

__all__ = [
    "ConfigManager",
    "config",
    "MainConfig",
]


