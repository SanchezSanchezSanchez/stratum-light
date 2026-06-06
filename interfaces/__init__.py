"""Interfaces package.

Avoid importing heavy submodules at package import time. Attributes are
resolved lazily via __getattr__ to prevent side effects during commands like
`python -m product.interfaces.cli.main --help`.
"""

from importlib import import_module
from typing import Any

__all__ = [
    "create_api_app",
    "RuntimeController",
    "ServicesController",
    "ControlController",
    "MetricsController",
    "SystemInfoResponse",
    "ServiceListResponse",
    "ServiceDetailResponse",
    "ServiceControlRequest",
    "ServiceControlResponse",
    "RuntimeStateResponse",
    "MetricsResponse",
    "ControlActionRequest",
    "ControlActionResponse",
    "ErrorResponse",
    "SuccessResponse",
    "LogsResponse",
]

_ATTR_TO_MODULE = {
    "create_api_app": "product.interfaces.api_router",
    "RuntimeController": "product.interfaces.controllers.runtime",
    "ServicesController": "product.interfaces.controllers.services",
    "ControlController": "product.interfaces.controllers.control",
    "MetricsController": "product.interfaces.controllers.metrics",
    # schema exports
    "SystemInfoResponse": "product.interfaces.schema",
    "ServiceListResponse": "product.interfaces.schema",
    "ServiceDetailResponse": "product.interfaces.schema",
    "ServiceControlRequest": "product.interfaces.schema",
    "ServiceControlResponse": "product.interfaces.schema",
    "RuntimeStateResponse": "product.interfaces.schema",
    "MetricsResponse": "product.interfaces.schema",
    "ControlActionRequest": "product.interfaces.schema",
    "ControlActionResponse": "product.interfaces.schema",
    "ErrorResponse": "product.interfaces.schema",
    "SuccessResponse": "product.interfaces.schema",
    "LogsResponse": "product.interfaces.schema",
}

def __getattr__(name: str) -> Any:  # PEP 562 lazy attribute resolution
    module_path = _ATTR_TO_MODULE.get(name)
    if module_path is None:
        raise AttributeError(name)
    module = import_module(module_path)
    return getattr(module, name)
