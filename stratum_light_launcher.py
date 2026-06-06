#!/usr/bin/env python3
"""
STRATUM_LIGHT Launcher

This is the main entry point for the STRATUM_LIGHT system. It detects the environment,
initializes telemetry, bootstrap, and fault governance, and logs runtime sessions.

Usage:
    python stratum_light_launcher.py [options]

Options:
    --mode=MODE         Operating mode (api, cli, service, all) [default: all]
    --env=ENV           Environment tier (dev, staging, prod) [default: auto]
    --config=FILE       Path to configuration file [default: light_config.json]
    --log-level=LEVEL   Logging level (debug, info, warning, error) [default: info]
    --no-telemetry      Disable telemetry
    --no-governance     Disable fault governance
    --help              Show this help message and exit
    --version           Show version and exit

Examples:
    python stratum_light_launcher.py --mode=api --env=dev
    python stratum_light_launcher.py --mode=cli --config=custom_config.json
    python stratum_light_launcher.py --mode=service --env=prod --log-level=warning
"""

import os
import sys
import json
import time
import uuid
import socket
import logging
import argparse
import platform
import traceback
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Set, Union
from enum import Enum, auto
from dataclasses import dataclass

# Ensure project root is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import modules using product.* package paths
from product.bootstrap import initialize as initialize_system
from product.bootstrap.runtime import RuntimeContext
from product.bootstrap.logging import configure_logging
from product.configs.environment import detect_environment, load_environment_config
from product.configs.settings import config as load_config
from product.core.services.registry import ServiceRegistry
from product.core.behavior.monitor import BehaviorSentinel
from product.core.behavior.policies import BehaviorPolicyEngine
from product.core.governance.fault_handler import FaultGovernor
# The following modules appear to be placeholders; keep as local imports if present
try:
    from product.core.governance.protocols import get_failover_protocol  # type: ignore
except Exception:
    def get_failover_protocol():
        return None
try:
    from product.core.services.example_services import (
        get_failover_integration,
        connect_fault_governor,
        connect_behavior_sentinel,
    )  # type: ignore
except Exception:
    def get_failover_integration():
        return None
    def connect_fault_governor(*args, **kwargs):
        return None
    def connect_behavior_sentinel(*args, **kwargs):
        return None
try:
    from product.scripts.telemetry_integration import TelemetryManager  # type: ignore
except Exception:
    class TelemetryManager:  # fallback stub
        def __init__(self, *args, **kwargs):
            pass

# Define launcher enums
class LauncherMode(Enum):
    """Operating modes for the launcher."""
    API = auto()
    CLI = auto()
    SERVICE = auto()
    ALL = auto()

class EnvironmentTier(Enum):
    """Environment tiers."""
    DEV = auto()
    STAGING = auto()
    PROD = auto()
    AUTO = auto()

@dataclass
class LauncherContext:
    """Data structure for launcher context."""
    session_id: str
    start_time: float
    mode: LauncherMode
    environment: EnvironmentTier
    config_path: str
    log_level: str
    telemetry_enabled: bool
    governance_enabled: bool
    hostname: str
    platform_info: str
    runtime_context: Optional[RuntimeContext] = None

class StratumLightLauncher:
    """
    Main launcher for the STRATUM_LIGHT system.
    
    This class is responsible for:
    1. Detecting the environment (dev/staging/prod)
    2. Initializing telemetry, bootstrap, and fault governance
    3. Logging runtime sessions
    4. Feeding back to BehaviorFaultIntegrator
    """
    
    def __init__(self):
        """Initialize the launcher."""
        self.context = None
        self.config = None
        self.logger = logging.getLogger("stratum_light.launcher")
        self.services = {}
        self.service_registry = None
        self.behavior_sentinel = None
        self.fault_governor = None
        self.telemetry_manager = None
    
    def parse_arguments(self) -> argparse.Namespace:
        """
        Parse command line arguments.
        
        Returns:
            Parsed arguments
        """
        parser = argparse.ArgumentParser(
            description="STRATUM_LIGHT Launcher",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog=__doc__
        )
        
        parser.add_argument(
            "--mode",
            choices=["api", "cli", "service", "all"],
            default="all",
            help="Operating mode (api, cli, service, all) [default: all]"
        )
        
        parser.add_argument(
            "--env",
            choices=["dev", "staging", "prod", "auto"],
            default="auto",
            help="Environment tier (dev, staging, prod, auto) [default: auto]"
        )
        
        parser.add_argument(
            "--config",
            default="light_config.json",
            help="Path to configuration file [default: light_config.json]"
        )
        
        parser.add_argument(
            "--log-level",
            choices=["debug", "info", "warning", "error"],
            default="info",
            help="Logging level (debug, info, warning, error) [default: info]"
        )
        
        parser.add_argument(
            "--no-telemetry",
            action="store_true",
            help="Disable telemetry"
        )
        
        parser.add_argument(
            "--no-governance",
            action="store_true",
            help="Disable fault governance"
        )
        
        parser.add_argument(
            "--version",
            action="store_true",
            help="Show version and exit"
        )
        
        return parser.parse_args()
    
    def initialize(self, args: argparse.Namespace) -> bool:
        """
        Initialize the launcher with the given arguments.
        
        Args:
            args: Command line arguments
            
        Returns:
            True if initialization was successful, False otherwise
        """
        try:
            # Show version if requested
            if args.version:
                self._show_version()
                return False
            
            # Create session ID
            session_id = str(uuid.uuid4())
            
            # Parse mode
            if args.mode == "api":
                mode = LauncherMode.API
            elif args.mode == "cli":
                mode = LauncherMode.CLI
            elif args.mode == "service":
                mode = LauncherMode.SERVICE
            else:
                mode = LauncherMode.ALL
            
            # Parse environment
            if args.env == "dev":
                environment = EnvironmentTier.DEV
            elif args.env == "staging":
                environment = EnvironmentTier.STAGING
            elif args.env == "prod":
                environment = EnvironmentTier.PROD
            else:
                environment = EnvironmentTier.AUTO
            
            # Create launcher context
            self.context = LauncherContext(
                session_id=session_id,
                start_time=time.time(),
                mode=mode,
                environment=environment,
                config_path=args.config,
                log_level=args.log_level,
                telemetry_enabled=not args.no_telemetry,
                governance_enabled=not args.no_governance,
                hostname=socket.gethostname(),
                platform_info=platform.platform()
            )
            
            # Configure logging
            log_level = getattr(logging, args.log_level.upper())
            configure_logging(log_level)
            
            self.logger.info(f"Initializing STRATUM_LIGHT launcher (Session ID: {session_id})")
            self.logger.info(f"Mode: {mode.name}, Environment: {environment.name}")
            
            # Load configuration
            self._load_configuration()
            
            # Detect environment if auto
            if environment == EnvironmentTier.AUTO:
                detected_env = detect_environment()
                if detected_env == "development":
                    self.context.environment = EnvironmentTier.DEV
                elif detected_env == "staging":
                    self.context.environment = EnvironmentTier.STAGING
                elif detected_env == "production":
                    self.context.environment = EnvironmentTier.PROD
                else:
                    self.context.environment = EnvironmentTier.DEV
                
                self.logger.info(f"Auto-detected environment: {self.context.environment.name}")
            
            # Load environment-specific configuration
            env_config = load_environment_config(self.context.environment.name.lower())
            if env_config:
                self.config.update(env_config)
            
            # Initialize system components
            self._initialize_system()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Initialization error: {str(e)}")
            self.logger.error(traceback.format_exc())
            return False
    
    def _show_version(self) -> None:
        """Show version information and exit."""
        version = "1.0.0"
        print(f"STRATUM_LIGHT version {version}")
        print(f"Python version: {platform.python_version()}")
        print(f"Platform: {platform.platform()}")
    
    def _load_configuration(self) -> None:
        """Load configuration from file."""
        config_path = self.context.config_path
        
        # Check if path is absolute
        if not os.path.isabs(config_path):
            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), config_path)
        
        self.logger.info(f"Loading configuration from {config_path}")
        
        try:
            self.config = load_config(config_path)
            self.logger.info("Configuration loaded successfully")
        except Exception as e:
            self.logger.error(f"Error loading configuration: {str(e)}")
            self.logger.warning("Using default configuration")
            self.config = self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """
        Get default configuration.
        
        Returns:
            Default configuration dictionary
        """
        return {
            "system": {
                "name": "STRATUM_LIGHT",
                "version": "1.0.0",
                "description": "Enterprise AI Security Platform"
            },
            "logging": {
                "level": self.context.log_level,
                "file": "/var/log/stratum_light/stratum_light.log",
                "max_size_mb": 10,
                "backup_count": 5
            },
            "telemetry": {
                "enabled": self.context.telemetry_enabled,
                "endpoint": None,
                "interval_seconds": 60,
                "batch_size": 100
            },
            "governance": {
                "enabled": self.context.governance_enabled,
                "fault_threshold": 80,
                "auto_recovery": True
            },
            "api": {
                "host": "0.0.0.0",
                "port": 8000,
                "workers": 4,
                "timeout": 30
            },
            "services": {
                "registry_enabled": True,
                "autostart": True
            }
        }
    
    def _initialize_system(self) -> None:
        """Initialize system components."""
        self.logger.info("Initializing system components")
        
        # Create runtime context
        self.context.runtime_context = RuntimeContext(
            session_id=self.context.session_id,
            environment=self.context.environment.name.lower(),
            mode=self.context.mode.name.lower(),
            config=self.config
        )
        
        # Initialize system
        initialize_system(self.context.runtime_context)
        
        # Initialize telemetry if enabled
        if self.context.telemetry_enabled:
            self._initialize_telemetry()
        
        # Initialize service registry
        self._initialize_service_registry()
        
        # Initialize behavior sentinel
        self._initialize_behavior_sentinel()
        
        # Initialize fault governance if enabled
        if self.context.governance_enabled:
            self._initialize_fault_governance()
        
        self.logger.info("System initialization complete")
    
    def _initialize_telemetry(self) -> None:
        """Initialize telemetry manager."""
        self.logger.info("Initializing telemetry")
        
        try:
            telemetry_config = self.config.get("telemetry", {})
            self.telemetry_manager = TelemetryManager(telemetry_config)
            
            # Register session start
            self.telemetry_manager.register_event(
                event_type="session_start",
                data={
                    "session_id": self.context.session_id,
                    "mode": self.context.mode.name,
                    "environment": self.context.environment.name,
                    "hostname": self.context.hostname,
                    "platform": self.context.platform_info
                }
            )
            
            self.logger.info("Telemetry initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Error initializing telemetry: {str(e)}")
            self.logger.error(traceback.format_exc())
    
    def _initialize_service_registry(self) -> None:
        """Initialize service registry."""
        self.logger.info("Initializing service registry")
        
        try:
            registry_enabled = self.config.get("services", {}).get("registry_enabled", True)
            if registry_enabled:
                self.service_registry = ServiceRegistry()
                
                # Register core services
                self._register_core_services()
                
                self.logger.info("Service registry initialized successfully")
            else:
                self.logger.info("Service registry disabled in configuration")
                
        except Exception as e:
            self.logger.error(f"Error initializing service registry: {str(e)}")
            self.logger.error(traceback.format_exc())
    
    def _register_core_services(self) -> None:
        """Register core services with the service registry."""
        if not self.service_registry:
            return
        
        # Import core services
        from core.services.example_services import (
            TokenAnalysisService,
            PromptGenerationService,
            ReportingService
        )
        
        # Create and register services
        self.services["token_analysis"] = TokenAnalysisService()
        self.services["prompt_generation"] = PromptGenerationService()
        self.services["reporting"] = ReportingService()
        
        for name, service in self.services.items():
            self.service_registry.register_service(name, service)
            self.logger.info(f"Registered service: {name}")
    
    def _initialize_behavior_sentinel(self) -> None:
        """Initialize behavior sentinel."""
        self.logger.info("Initializing behavior sentinel")
        
        try:
            # Create behavior sentinel
            self.behavior_sentinel = BehaviorSentinel()
            
            # Create behavior policy engine
            self.behavior_policy = BehaviorPolicyEngine()
            
            # Connect behavior sentinel to policy engine
            self.behavior_sentinel.connect_policy_engine(self.behavior_policy)
            
            # Register session with behavior sentinel
            self.behavior_sentinel.register_session(
                session_id=self.context.session_id,
                metadata={
                    "mode": self.context.mode.name,
                    "environment": self.context.environment.name,
                    "hostname": self.context.hostname,
                    "platform": self.context.platform_info,
                }
            )

            self.logger.info("Behavior sentinel initialized")
        except Exception as e:
            self.logger.error(f"Error initializing behavior sentinel: {str(e)}")
            self.logger.error(traceback.format_exc())

    def run(self) -> None:
        """Execute the launcher based on selected mode."""
        mode = self.context.mode
        if mode == LauncherMode.API:
            self._run_api()
        elif mode == LauncherMode.CLI:
            self._run_cli()
        elif mode == LauncherMode.SERVICE:
            self._run_services()
        else:
            self._run_all()

    # Placeholder run implementations
    def _run_api(self) -> None:
        self.logger.info("API mode selected - no implementation in demo")

    def _run_cli(self) -> None:
        self.logger.info("CLI mode selected - no implementation in demo")

    def _run_services(self) -> None:
        self.logger.info("Service mode selected - no implementation in demo")

    def _run_all(self) -> None:
        self.logger.info("Running all components - no implementation in demo")


def main() -> None:
    launcher = StratumLightLauncher()
    args = launcher.parse_arguments()
    if launcher.initialize(args):
        launcher.run()


if __name__ == "__main__":
    main()
