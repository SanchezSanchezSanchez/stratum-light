#!/usr/bin/env python3
"""
STRATUM_LIGHT Deployment Entrypoint

This script serves as the main entrypoint for STRATUM_LIGHT in containerized environments.
It initializes the system based on command-line arguments and environment configuration.
"""

import os
import sys
import argparse
import logging
from pathlib import Path

# Set up basic logging before importing other modules
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(os.environ.get("LOG_DIR", "logs"), "stratum.log"))
    ]
)

logger = logging.getLogger("stratum_bootstrap")

def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="STRATUM_LIGHT Deployment Entrypoint")
    
    # Mode selection arguments
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--api", action="store_true", help="Run in API mode")
    mode_group.add_argument("--cli", action="store_true", help="Run in CLI mode")
    mode_group.add_argument("--telemetry", action="store_true", help="Run in telemetry mode")
    
    # Optional arguments
    parser.add_argument("--config", type=str, help="Path to config file")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    
    return parser.parse_args()

def setup_environment():
    """Set up the environment for STRATUM_LIGHT."""
    # Create necessary directories
    os.makedirs(os.environ.get("LOG_DIR", "logs"), exist_ok=True)
    os.makedirs(os.environ.get("DATA_DIR", "data"), exist_ok=True)
    os.makedirs(os.environ.get("TELEMETRY_DIR", "telemetry"), exist_ok=True)
    
    # Set Python path
    sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
    
    # Check for required environment variables
    required_vars = ["ENVIRONMENT", "LIGHT_CONFIG_KEY"]
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please check your .env file or environment configuration")
        sys.exit(1)
    
    logger.info(f"Environment set up successfully in {os.environ.get('ENVIRONMENT')} mode")

def run_api_mode():
    """Run STRATUM_LIGHT in API mode."""
    try:
        from server import run_server
        
        host = os.environ.get("API_HOST", "0.0.0.0")
        port = int(os.environ.get("API_PORT", 8000))
        
        logger.info(f"Starting API server on {host}:{port}")
        run_server(host=host, port=port)
    except ImportError as e:
        logger.error(f"Failed to import server module: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error starting API server: {e}")
        sys.exit(1)

def run_cli_mode():
    """Run STRATUM_LIGHT in CLI mode."""
    try:
        from cli.main import main as cli_main
        
        logger.info("Starting CLI mode")
        cli_main()
    except ImportError as e:
        logger.error(f"Failed to import CLI module: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error in CLI mode: {e}")
        sys.exit(1)

def run_telemetry_mode():
    """Run STRATUM_LIGHT in telemetry mode."""
    try:
        from monitoring.telemetry_integration import start_telemetry_service
        
        logger.info("Starting telemetry service")
        start_telemetry_service()
    except ImportError as e:
        logger.error(f"Failed to import telemetry module: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error in telemetry mode: {e}")
        sys.exit(1)

def main():
    """Main entrypoint function."""
    args = parse_args()
    
    # Set debug mode if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        os.environ["LOG_LEVEL"] = "DEBUG"
        logger.debug("Debug mode enabled")
    
    # Set up environment
    setup_environment()
    
    # Import bootstrap module
    try:
        from bootstrap import bootstrap_system
        
        # Bootstrap the system
        logger.info("Bootstrapping STRATUM_LIGHT system")
        bootstrap_system(config_path=args.config)
        
        # Run in the selected mode
        if args.api:
            run_api_mode()
        elif args.cli:
            run_cli_mode()
        elif args.telemetry:
            run_telemetry_mode()
    except ImportError as e:
        logger.error(f"Failed to import bootstrap module: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error bootstrapping system: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
