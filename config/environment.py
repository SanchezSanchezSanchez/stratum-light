"""Compatibility shim for legacy import path `config.environment`.

Re-exports specific names from `product.configs.environment` for tests.
"""

from product.configs.environment import EnvironmentSchema, EnvironmentTier, ValidationLevel, env  # noqa: F401

__all__ = [
    "EnvironmentSchema",
    "EnvironmentTier",
    "ValidationLevel",
    "env",
]


