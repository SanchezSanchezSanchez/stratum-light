from __future__ import annotations
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from product.configs.environment import env, get_env

@dataclass
class RuntimeState:
    env_context: Dict[str, Any]
    start_time: float = field(default_factory=time.time)
    features: Dict[str, bool] = field(default_factory=dict)
    state: Dict[str, Any] = field(default_factory=dict)
    modules: Dict[str, bool] = field(default_factory=dict)
    health: Dict[str, Any] = field(default_factory=lambda: {"status": "unknown"})

    def set_feature(self, name: str, enabled: bool) -> None:
        self.features[name] = enabled

    def is_feature_enabled(self, name: str) -> bool:
        return self.features.get(name, False)

    def set_state(self, key: str, value: Any) -> None:
        self.state[key] = value

    def get_state(self, key: str, default: Any = None) -> Any:
        return self.state.get(key, default)

    def register_module(self, name: str) -> None:
        self.modules[name] = True

    def is_module_initialized(self, name: str) -> bool:
        return self.modules.get(name, False)

    def update_health(self, status: str, **details: Any) -> None:
        self.health = {"status": status, **details}

    def get_health(self) -> Dict[str, Any]:
        return self.health.copy()

    def get_uptime(self) -> float:
        return time.time() - self.start_time

    def to_dict(self) -> Dict[str, Any]:
        return {
            "env": {
                **{k: (v.value if hasattr(v, 'value') else v) for k, v in self.env_context.items() if k != 'tier'},
                "tier": getattr(self.env_context.get("tier"), "value", self.env_context.get("tier"))
            },
            "features": self.features,
            "state": self.state,
            "modules": list(self.modules.keys()),
            "health": self.health,
            "uptime": self.get_uptime(),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


_runtime_state: Optional[RuntimeState] = None

def initialize_runtime(env_context: Optional[Dict[str, Any]] = None) -> RuntimeState:
    global _runtime_state
    if env_context is None:
        env_context = get_env().get_env_context()
    _runtime_state = RuntimeState(env_context)
    return _runtime_state


def get_runtime_state() -> RuntimeState:
    global _runtime_state
    if _runtime_state is None:
        _runtime_state = initialize_runtime()
    return _runtime_state


@dataclass
class RuntimeContext:
    session_id: str
    environment: str
    mode: str
    config: Dict[str, Any]
