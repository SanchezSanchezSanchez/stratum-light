#!/usr/bin/env python3
"""
STRATUM_LIGHT Server Entrypoint

This module provides the main server entrypoint for the STRATUM_LIGHT system,
bootstrapping the environment and launching the API server.
"""

import os
import sys
import logging
import json
import time
import argparse
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import traceback
import asyncio
import signal
import uvicorn
from contextlib import asynccontextmanager

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Import bootstrap modules
try:
    from product.bootstrap import initialize as bootstrap_initialize, get_runtime_state, get_core_module
    from product.bootstrap.logging import configure_logging
    from product.configs.environment import EnvironmentSchema
    from product.configs.settings import config
except ImportError as e:
    print(f"Failed to import bootstrap modules: {str(e)}")
    print("Make sure you\\\\\\\'re running from the project root directory")
    sys.exit(1)

# Import API modules
try:
    from product.interfaces.api_router import create_api_app
except ImportError as e:
    print(f"Failed to import API modules: {str(e)}")
    print("Make sure you\\\\\\\'re running from the project root directory")
    sys.exit(1)

# Import core modules
try:
    from product.core.services.registry import get_registry, ServiceRegistry
    from product.core.services.graph_executor import get_executor, GraphExecutor
except ImportError:
    print("Failed to import core modules")
    print("Make sure you\\\\\\\'re running from the project root directory")
    sys.exit(1)

# Set up logger
logger = logging.getLogger(__name__)

class ServerManager:
    """
    Manager for the STRATUM_LIGHT server.
    
    This class handles server initialization, startup, and shutdown.
    """
    
    def __init__(self):
        """
        Initialize the server manager.
        """
        self.app = None
        self.registry = None
        self.executor = None
        self.runtime_state = None
        self.environment_schema = EnvironmentSchema() # Instantiate EnvironmentSchema
        self.environment = None
        self.shutdown_event = asyncio.Event()
        self.server_config = {
            "host": "0.0.0.0",
            "port": 8000,
            "log_level": "info",
            "reload": False,
            "workers": 1
        }
    
    async def initialize(self):
        """
        Initialize the server.
        """
        try:
            # Initialize bootstrap
            logger.info("Initializing bootstrap...")
            bootstrap_initialize()
            
            # Get environment and runtime state
            self.environment = self.environment_schema.get_env_context() # Use instance method
            self.runtime_state = get_runtime_state()
            
            # Configure logging based on environment
            log_level = self.environment.get("log_level", "INFO").upper()
            configure_logging(log_level)
            
            # Initialize runtime
            logger.info("Initializing runtime...")
            # Assuming initialize_runtime is now part of bootstrap_initialize or handled by get_runtime_state
            # If not, you might need to find where it\\\\\\\'s defined and import it correctly.
            # For now, let\\\\\\\'s assume get_runtime_state handles the necessary initialization.
            
            # Get registry and executor
            self.registry = get_registry()
            self.executor = get_executor()
            
            # Configure server based on environment
            self._configure_server()
            
            # Create API app
            logger.info("Creating API application...")
            self.app = create_api_app()
            
            # Register shutdown handler
            for sig in (signal.SIGINT, signal.SIGTERM):
                signal.signal(sig, self._signal_handler)
            
            logger.info("Server initialization complete")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize server: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    def _configure_server(self):
        """
        Configure server based on environment.
        """
        # Get server config from environment or config
        server_config = self.environment.get("server", {})
        
        # Update server config
        if "host" in server_config:
            self.server_config["host"] = server_config["host"]
        
        if "port" in server_config:
            self.server_config["port"] = int(server_config["port"])
        
        # Configure based on environment tier
        if self.environment_schema.is_dev(): # Use instance method
            # Development environment
            self.server_config["reload"] = True
            self.server_config["log_level"] = "debug"
            self.server_config["workers"] = 1
        elif self.environment_schema.is_staging(): # Use instance method
            # Staging environment
            self.server_config["reload"] = False
            self.server_config["log_level"] = "info"
            self.server_config["workers"] = 2
        elif self.environment_schema.is_prod(): # Use instance method
            # Production environment
            self.server_config["reload"] = False
            self.server_config["log_level"] = "warning"
            self.server_config["workers"] = 4
        
        logger.info(f"Server configured: {json.dumps(self.server_config)}")
    
    def _signal_handler(self, sig, frame):
        """
        Handle shutdown signals.
        """
        logger.info(f"Received signal {sig}, initiating shutdown...")
        
        # Set shutdown event
        if not self.shutdown_event.is_set():
            loop = asyncio.get_event_loop()
            loop.create_task(self.shutdown())
    
    async def shutdown(self):
        """
        Shutdown the server.
        """
        logger.info("Shutting down server...")
        
        # Set shutdown event
        self.shutdown_event.set()
        
        # Shutdown services
        if self.registry and self.executor:
            try:
                logger.info("Shutting down services...")
                
                # Get services in reverse dependency order
                services = self.registry.get_all_services()
                
                # Build execution plan and reverse it for shutdown
                execution_plan = self.executor.build_execution_plan()
                service_names = [s.name for s in reversed(execution_plan)]
                
                # Shutdown services
                for name in service_names:
                    if name in services:
                        service = services[name]
                        if hasattr(service, "shutdown"):
                            try:
                                logger.info(f"Shutting down service: {name}")
                                service.shutdown()
                            except Exception as e:
                                logger.error(f"Failed to shutdown service {name}: {str(e)}")
            except Exception as e:
                logger.error(f"Error during service shutdown: {str(e)}")
        
        logger.info("Server shutdown complete")
    
    async def start_services(self):
        """
        Start services.
        """
        if not self.registry or not self.executor:
            logger.warning("Cannot start services: registry or executor not available")
            return False
        
        try:
            logger.info("Starting services...")
            
            # Execute graph with initialization and warm-up
            result = self.executor.execute_graph(
                initialize=True,
                warm_up=True
            )
            
            logger.info(f"Started {len(result.succeeded)} services, {len(result.failed)} failed")
            
            if result.failed:
                for name, error in result.failed.items():
                    logger.error(f"Failed to start service {name}: {error}")
            
            return len(result.failed) == 0
        except Exception as e:
            logger.error(f"Failed to start services: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    def run(self):
        """
        Run the server.
        """
        # Initialize event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Initialize server
            if not loop.run_until_complete(self.initialize()):
                logger.error("Server initialization failed")
                return 1
            
            # Start services
            if not loop.run_until_complete(self.start_services()):
                logger.warning("Some services failed to start")
            
            # Start server
            logger.info(f"Starting server on {self.server_config['host']}:{self.server_config['port']}...")
            
            # Create lifespan context
            @asynccontextmanager
            async def lifespan(app):
                # Startup
                logger.info("API server starting...")
                yield
                # Shutdown
                logger.info("API server shutting down...")
                await self.shutdown()
            
            # Set lifespan
            self.app.router.lifespan_context = lifespan
            
            # Run server
            uvicorn.run(
                self.app,
                host=self.server_config["host"],
                port=self.server_config["port"],
                log_level=self.server_config["log_level"],
                reload=self.server_config["reload"],
                workers=self.server_config["workers"]
            )
            
            return 0
        except Exception as e:
            logger.error(f"Server error: {str(e)}")
            logger.error(traceback.format_exc())
            return 1
        finally:
            # Clean up
            loop.close()

def main():
    """
    Main entry point.
    """
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="STRATUM_LIGHT Server")
    parser.add_argument("--host", help="Server host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, help="Server port (default: 8000)")
    parser.add_argument("--log-level", help="Log level (default: info)")
    parser.add_argument("--workers", type=int, help="Number of workers (default: 1)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    args = parser.parse_args()
    
    # Configure basic logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    
    # Create and run server
    server = ServerManager()
    
    # Override server config with command line arguments
    if args.host:
        server.server_config["host"] = args.host
    
    if args.port:
        server.server_config["port"] = args.port
    
    if args.log_level:
        server.server_config["log_level"] = args.log_level
    
    if args.workers:
        server.server_config["workers"] = args.workers
    
    if args.reload:
        server.server_config["reload"] = True
    
    # Run server
    return server.run()

# Define the \\\"app\\\" object for uvicorn to find
# This assumes that create_api_app() can be called directly to get the FastAPI app instance
# If create_api_app() requires initialization or arguments, this will need adjustment.
# For now, we\\\\\\\'ll assume it\\\\\\\'s a simple callable that returns the app.
# If the app is created within ServerManager, we need to expose it differently.
# Let\\\\\\\'s assume for now that `create_api_app()` is the entry point for the FastAPI app.

# The \\\"app\\\" object that uvicorn looks for
# This is a placeholder. The actual FastAPI app instance needs to be exposed here.
# Given the structure, the app is created within ServerManager.initialize().
# We need a way to get that app instance for uvicorn.
# A common pattern is to have a function that returns the app, or to instantiate the app globally.
# Let\\\\\\\'s modify the server.py to expose the app directly for uvicorn.

# To make `app` discoverable by uvicorn, we need to ensure it\\\\\\\'s a top-level object.
# The `create_api_app` function is imported, so we can call it directly.
# However, the `ServerManager` handles the full lifecycle, including app creation.
# A simpler approach for uvicorn is to have a function that returns the app.

# Let\\\\\\\'s assume create_api_app() is the function that returns the FastAPI app.
# If it needs to be initialized by ServerManager, then we need to adjust.

# For now, let\\\\\\\'s try to get the app from ServerManager.initialize() and expose it.
# This might require a slight restructuring or a global variable if the app is not directly returned.

# Let\\\\\\\'s try to make `app` a global variable after initialization.
# This is a common pattern for uvicorn to pick up the app.

# Global variable for the FastAPI app
app = None

@asynccontextmanager
async def lifespan(app_instance):
    global app
    server_manager = ServerManager()
    if not await server_manager.initialize():
        logger.critical("Server initialization failed during lifespan startup.")
        sys.exit(1)
    app = server_manager.app # Assign the created app to the global variable
    logger.info("API server starting...")
    yield
    logger.info("API server shutting down...")
    await server_manager.shutdown()

# This is the entry point for uvicorn
# The `app` object will be set during the lifespan startup.
# Uvicorn will call this `lifespan` function.
# The `app` object needs to be a FastAPI instance.
# Let\\\\\\\'s make `create_api_app` directly callable and assign it to `app`.

# This is the simplest way for uvicorn to find the app.
# If `create_api_app` requires initialization from `ServerManager`, this will fail.
# Let\\\\\\\'s assume `create_api_app` is self-contained for now.

app = create_api_app()

if __name__ == "__main__":
    sys.exit(main())


