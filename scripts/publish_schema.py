#!/usr/bin/env python3
# API Schema Auto-Publisher for STRATUM_LIGHT

import os
import json
import argparse
import logging
from pathlib import Path

# Set up logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s|%(levelname)s|%(message)s')
logger = logging.getLogger(__name__)

def publish_schema(output_dir: str = "public", filename: str = "openapi.json"):
    """
    Extracts and publishes the OpenAPI schema from the API module
    
    Args:
        output_dir: Directory to save the schema file
        filename: Name of the schema file
    """
    try:
        # Import the FastAPI app
        from api.routes import app
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate the full path
        output_path = os.path.join(output_dir, filename)
        
        # Get the OpenAPI schema
        schema = app.openapi()
        
        # Write the schema to file
        with open(output_path, 'w') as f:
            json.dump(schema, f, indent=2)
            
        logger.info(f"OpenAPI schema published to {output_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to publish schema: {str(e)}")
        return False

def main():
    """Main entry point for the schema publisher"""
    parser = argparse.ArgumentParser(description="STRATUM_LIGHT OpenAPI Schema Publisher")
    parser.add_argument("--output-dir", default="public", help="Directory to save the schema file")
    parser.add_argument("--filename", default="openapi.json", help="Name of the schema file")
    
    args = parser.parse_args()
    
    if publish_schema(args.output_dir, args.filename):
        logger.info("Schema publication successful")
        return 0
    else:
        logger.error("Schema publication failed")
        return 1

if __name__ == "__main__":
    exit(main())
