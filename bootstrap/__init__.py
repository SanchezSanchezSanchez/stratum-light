#!/usr/bin/env python3
# System Entrypoint and Bootstrap Module for STRATUM_LIGHT

import os
import sys
import logging
import importlib
from typing import Dict, Any, Optional, List, Callable

# Set up basic logging before proper configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s|%(levelname)s|%(message)s')
logger = logging.getLogger(__name__)

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import environment symbols lazily to avoid side effects at import time
try:
    from config.environment import env, EnvironmentTier
except ImportError as e:
    logger.critical(f"Failed to import environment schema: {str(e)}")
    logger.critical("Environment schema must be available on PYTHONPATH")
    # Do not exit; allow tests/importers to proceed and fail when used

# Import bootstrap modules from product namespace to avoid circular shim issues
try:
    from product.bootstrap.logging import configure_logging
    from product.bootstrap.runtime import RuntimeState
except ImportError as e:
    logger.critical(f"Failed to import bootstrap modules: {str(e)}")
    logger.critical("Bootstrap modules must be present")
    sys.exit(1)

class StratumBootstrap:
    """
    Central bootstrap system for STRATUM_LIGHT
    
    This class handles the initialization of all system components
    based on the current environment tier.
    """
    
    def __init__(self):
        """Initialize the bootstrap system"""
        self.env_context = env.get_env_context()
        self.runtime_state = None
        self.core_modules = {}
        
        logger.info(f"Initializing STRATUM_LIGHT in {self.env_context['env']} mode")
    
    def initialize(self) -> bool:
        """
        Initialize the system
        
        Returns:
            True if initialization was successful, False otherwise
        """
        try:
            # Refresh environment on each initialize to honor current os.environ
            self.env_context = env.get_env_context()
            # Configure logging based on environment tier
            configure_logging(self.env_context)
            logger.info("Logging configured")
            
            # Initialize runtime state
            self.runtime_state = RuntimeState(self.env_context)
            logger.info("Runtime state initialized")
            
            # Load core modules
            self._load_core_modules()
            logger.info("Core modules loaded")
            
            # Apply tier-specific initialization
            self._apply_tier_specific_init()
            logger.info(f"Tier-specific initialization applied for {self.env_context['env']}")
            
            logger.info("STRATUM_LIGHT bootstrap complete")
            return True
            
        except Exception as e:
            logger.critical(f"Bootstrap failed: {str(e)}")
            return False
    
    def _load_core_modules(self) -> None:
        """
        Dynamically load core system modules
        
        This implements lazy loading of core modules based on the current
        environment tier and configuration.
        """
        # Define core modules to load
        core_module_paths = [
            "core.analyzer",
            "core.prompt_engine",
            "core.reporter",
            "core.siem",
            "core.deployer"
        ]
        
        # Load each module
        for module_path in core_module_paths:
            try:
                module = importlib.import_module(module_path)
                module_name = module_path.split(".")[-1]
                self.core_modules[module_name] = module
                logger.debug(f"Loaded core module: {module_name}")
            except ImportError as e:
                if self.env_context['tier'] == EnvironmentTier.PRODUCTION:
                    # In production, all core modules are required
                    logger.critical(f"Failed to load required core module {module_path}: {str(e)}")
                    raise
                else:
                    # In development/staging, log warning but continue
                    logger.warning(f"Failed to load core module {module_path}: {str(e)}")
    
    def _apply_tier_specific_init(self) -> None:
        """Apply tier-specific initialization logic"""
        tier = self.env_context['tier']
        
        if tier == EnvironmentTier.DEVELOPMENT:
            # Development-specific initialization
            logger.info("Applying development-specific initialization")
            self._init_development()
            
        elif tier == EnvironmentTier.STAGING:
            # Staging-specific initialization
            logger.info("Applying staging-specific initialization")
            self._init_staging()
            
        elif tier == EnvironmentTier.PRODUCTION:
            # Production-specific initialization
            logger.info("Applying production-specific initialization")
            self._init_production()
    
    def _init_development(self) -> None:
        """Development-specific initialization"""
        # Enable debug features
        self.runtime_state.set_feature("debug_mode", True)
        self.runtime_state.set_feature("verbose_logging", True)
        self.runtime_state.set_feature("mock_endpoints", True)
        
        # Set development-specific configuration
        if "analyzer" in self.core_modules:
            # Configure analyzer for development (e.g., use local models)
            pass
            
        if "reporter" in self.core_modules:
            # Configure reporter for development (e.g., use local storage)
            pass
    
    def _init_staging(self) -> None:
        """Staging-specific initialization"""
        # Enable staging features
        self.runtime_state.set_feature("debug_mode", env.get("debug", False))
        self.runtime_state.set_feature("verbose_logging", False)
        self.runtime_state.set_feature("mock_endpoints", False)
        self.runtime_state.set_feature("audit_mode", True)
        
        # Validate cloud credentials
        self._validate_cloud_credentials()
        
        # Set staging-specific configuration
        if "reporter" in self.core_modules:
            # Configure reporter for staging (e.g., use staging endpoints)
            pass
    
    def _init_production(self) -> None:
        """Production-specific initialization"""
        # Enable production features
        self.runtime_state.set_feature("debug_mode", False)
        self.runtime_state.set_feature("verbose_logging", False)
        self.runtime_state.set_feature("mock_endpoints", False)
        self.runtime_state.set_feature("audit_mode", True)
        self.runtime_state.set_feature("high_security", True)
        
        # Validate cloud credentials
        self._validate_cloud_credentials()
        
        # Validate critical endpoints
        self._validate_critical_endpoints()
        
        # Set production-specific configuration
        if "reporter" in self.core_modules:
            # Configure reporter for production (e.g., use production endpoints)
            pass
    
    def _validate_cloud_credentials(self) -> None:
        """Validate cloud credentials"""
        cloud = self.env_context.get("cloud", {})
        
        # Check AWS credentials
        if cloud.get("aws") is None:
            logger.warning("AWS credentials not configured")
        
        # Check Azure credentials
        if cloud.get("azure") is None:
            logger.warning("Azure credentials not configured")
        
        # Check GCP credentials
        if cloud.get("gcp") is None:
            logger.warning("GCP credentials not configured")
    
    def _validate_critical_endpoints(self) -> None:
        """Validate critical endpoints"""
        # Check SIEM endpoint
        siem_endpoint = self.env_context.get("siem_endpoint")
        if not siem_endpoint:
            logger.critical("SIEM endpoint not configured")
            raise ValueError("SIEM endpoint is required in production")
        
        # Check bounty endpoints
        bounty_key = self.env_context.get("bounty_key")
        if not bounty_key:
            logger.critical("Bounty key not configured")
            raise ValueError("Bounty key is required in production")
    
    def get_runtime_state(self) -> RuntimeState:
        """Get the runtime state"""
        if self.runtime_state is None:
            raise RuntimeError("Runtime state not initialized")
        return self.runtime_state
    
    def get_core_module(self, name: str) -> Any:
        """
        Get a core module by name
        
        Args:
            name: Module name
            
        Returns:
            Module instance
            
        Raises:
            KeyError: If module not found
        """
        if name not in self.core_modules:
            raise KeyError(f"Core module {name} not found")
        return self.core_modules[name]

_bootstrap_instance: Optional[StratumBootstrap] = None

def _get_bootstrap() -> StratumBootstrap:
    global _bootstrap_instance
    if _bootstrap_instance is None:
        _bootstrap_instance = StratumBootstrap()
    return _bootstrap_instance

def initialize() -> bool:
    """
    Initialize the STRATUM_LIGHT system
    
    Returns:
        True if initialization was successful, False otherwise
    """
    return _get_bootstrap().initialize()

def get_runtime_state() -> RuntimeState:
    """
    Get the runtime state
    
    Returns:
        Runtime state instance
    """
    return _get_bootstrap().get_runtime_state()

def get_core_module(name: str) -> Any:
    """
    Get a core module by name
    
    Args:
        name: Module name
        
    Returns:
        Module instance
    """
    return _get_bootstrap().get_core_module(name)

# Main entry point
if __name__ == "__main__":
    if initialize():
        logger.info("STRATUM_LIGHT initialized successfully")
        
        # Get runtime state
        runtime = get_runtime_state()
        logger.info(f"Runtime features: {runtime.get_all_features()}")
        
        # Example: Access core modules
        try:
            analyzer = get_core_module("analyzer")
            logger.info("Analyzer module loaded")
        except KeyError:
            logger.warning("Analyzer module not available")
    else:
        logger.critical("STRATUM_LIGHT initialization failed")
        sys.exit(1)
