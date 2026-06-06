#!/usr/bin/env python3
"""
STRATUM_LIGHT Services Controller

This module provides the controller for service-related API endpoints,
including service listing, details, and control operations.
"""

import os
import sys
import logging
import json
import time
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import traceback
import asyncio

# Import core modules
try:
    from product.core.services.registry import ServiceRegistry, ServiceState
    from product.core.services.graph_executor import GraphExecutor
    from product.core.services.base_service import BaseService
except ImportError:
    # Fallback for standalone testing
    class ServiceRegistry: pass
    class ServiceState: pass
    class GraphExecutor: pass
    class BaseService: pass

# Set up logger
logger = logging.getLogger(__name__)

class ServicesController:
    """
    Controller for service-related API endpoints.
    
    This controller provides endpoints for service listing,
    details, and control operations.
    """
    
    def __init__(self, registry: ServiceRegistry, executor: GraphExecutor):
        """
        Initialize the services controller.
        
        Args:
            registry: Service registry instance
            executor: Graph executor instance
        """
        self.registry = registry
        self.executor = executor
    
    async def list_services(self) -> Dict[str, Any]:
        """
        List all services.
        
        Returns:
            Service list response dictionary
        """
        try:
            services_list = []
            
            if self.registry:
                services = self.registry.get_all_services()
                
                for name, service in services.items():
                    services_list.append({
                        "name": name,
                        "state": service.state.name if hasattr(service, "state") else "UNKNOWN",
                        "type": service.__class__.__name__,
                        "dependencies": service.dependencies if hasattr(service, "dependencies") else [],
                        "health": service.get_health() if hasattr(service, "get_health") else "unknown"
                    })
            
            return {
                "success": True,
                "services": services_list,
                "count": len(services_list),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to list services: {str(e)}")
            logger.error(traceback.format_exc())
            raise
    
    async def get_service_detail(self, service_name: str) -> Dict[str, Any]:
        """
        Get service details.
        
        Args:
            service_name: Name of the service
            
        Returns:
            Service detail response dictionary
        """
        try:
            if not self.registry:
                raise ValueError("Service registry not available")
            
            service = self.registry.get_service(service_name)
            if not service:
                raise ValueError(f"Service '{service_name}' not found")
            
            # Get service details
            details = {
                "name": service_name,
                "type": service.__class__.__name__,
                "state": service.state.name if hasattr(service, "state") else "UNKNOWN",
                "dependencies": service.dependencies if hasattr(service, "dependencies") else [],
                "dependents": self.registry.get_dependents(service_name),
                "health": service.get_health() if hasattr(service, "get_health") else "unknown",
                "metrics": service.get_metrics() if hasattr(service, "get_metrics") else {},
                "config": service.get_config() if hasattr(service, "get_config") else {},
                "lifecycle": {
                    "initialized": service.is_initialized() if hasattr(service, "is_initialized") else False,
                    "warmed_up": service.is_warmed_up() if hasattr(service, "is_warmed_up") else False,
                    "executing": service.is_executing() if hasattr(service, "is_executing") else False,
                    "error": service.get_last_error() if hasattr(service, "get_last_error") else None,
                    "last_execution": service.get_last_execution_time() if hasattr(service, "get_last_execution_time") else None,
                    "execution_count": service.get_execution_count() if hasattr(service, "get_execution_count") else 0
                }
            }
            
            return {
                "success": True,
                "service": details,
                "timestamp": datetime.now().isoformat()
            }
        except ValueError as e:
            logger.warning(f"Service detail request failed: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to get service detail: {str(e)}")
            logger.error(traceback.format_exc())
            raise
    
    async def control_service(self, service_name: str, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Control a service.
        
        Args:
            service_name: Name of the service
            request: Service control request
            
        Returns:
            Service control response dictionary
        """
        try:
            if not self.registry:
                raise ValueError("Service registry not available")
            
            service = self.registry.get_service(service_name)
            if not service:
                raise ValueError(f"Service '{service_name}' not found")
            
            # Get action from request
            action = request.get("action", "").lower()
            if not action:
                raise ValueError("No action specified")
            
            # Execute action
            result = None
            
            if action == "initialize":
                if hasattr(service, "initialize"):
                    await asyncio.to_thread(service.initialize)
                    result = "Service initialized"
                else:
                    raise ValueError("Service does not support initialization")
            
            elif action == "warmup":
                if hasattr(service, "warm_up"):
                    await asyncio.to_thread(service.warm_up)
                    result = "Service warmed up"
                else:
                    raise ValueError("Service does not support warm-up")
            
            elif action == "execute":
                if hasattr(service, "execute"):
                    result = await asyncio.to_thread(service.execute)
                    result = f"Service executed: {result}"
                else:
                    raise ValueError("Service does not support execution")
            
            elif action == "shutdown":
                if hasattr(service, "shutdown"):
                    await asyncio.to_thread(service.shutdown)
                    result = "Service shut down"
                else:
                    raise ValueError("Service does not support shutdown")
            
            elif action == "restart":
                # Shutdown and initialize
                if hasattr(service, "shutdown") and hasattr(service, "initialize"):
                    await asyncio.to_thread(service.shutdown)
                    await asyncio.to_thread(service.initialize)
                    result = "Service restarted"
                else:
                    raise ValueError("Service does not support restart")
            
            else:
                raise ValueError(f"Unknown action: {action}")
            
            return {
                "success": True,
                "service": service_name,
                "action": action,
                "result": result,
                "timestamp": datetime.now().isoformat()
            }
        except ValueError as e:
            logger.warning(f"Service control request failed: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to control service: {str(e)}")
            logger.error(traceback.format_exc())
            raise
