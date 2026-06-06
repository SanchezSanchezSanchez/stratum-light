#!/usr/bin/env python3
"""
STRATUM_LIGHT Metrics Controller

This module provides the controller for metrics-related API endpoints,
allowing external agents to retrieve system and service metrics.
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
import platform
import psutil

# Import core modules
try:
    from product.core.services.registry import ServiceRegistry, ServiceState
except ImportError:
    # Fallback for standalone testing
    class ServiceRegistry: pass
    class ServiceState: pass

# Set up logger
logger = logging.getLogger(__name__)

class MetricsController:
    """
    Controller for metrics-related API endpoints.
    
    This controller provides endpoints for retrieving system
    and service-specific metrics.
    """
    
    def __init__(self, registry: ServiceRegistry):
        """
        Initialize the metrics controller.
        
        Args:
            registry: Service registry instance
        """
        self.registry = registry
        self.system_metrics_cache = {}
        self.system_metrics_cache_time = 0
        self.system_metrics_cache_ttl = 5  # seconds
    
    async def get_metrics(self) -> Dict[str, Any]:
        """
        Get system metrics.
        
        Returns:
            Metrics response dictionary
        """
        try:
            # Get system metrics
            system_metrics = await self._get_system_metrics()
            
            # Get service metrics
            service_metrics = await self._get_all_service_metrics()
            
            # Combine metrics
            metrics = {
                "system": system_metrics,
                "services": service_metrics
            }
            
            return {
                "success": True,
                "metrics": metrics,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to get metrics: {str(e)}")
            logger.error(traceback.format_exc())
            raise
    
    async def get_service_metrics(self, service_name: str) -> Dict[str, Any]:
        """
        Get service-specific metrics.
        
        Args:
            service_name: Name of the service
            
        Returns:
            Metrics response dictionary
        """
        try:
            if not self.registry:
                raise ValueError("Service registry not available")
            
            service = self.registry.get_service(service_name)
            if not service:
                raise ValueError(f"Service '{service_name}' not found")
            
            # Get service metrics
            metrics = {}
            
            if hasattr(service, "get_metrics"):
                metrics = await asyncio.to_thread(service.get_metrics)
            
            # Add service state
            if hasattr(service, "state"):
                metrics["state"] = service.state.name
            
            # Add execution metrics if available
            if hasattr(service, "get_execution_count"):
                metrics["execution_count"] = service.get_execution_count()
            
            if hasattr(service, "get_last_execution_time"):
                last_time = service.get_last_execution_time()
                if last_time:
                    metrics["last_execution_time"] = last_time.isoformat()
            
            if hasattr(service, "get_average_execution_time"):
                metrics["average_execution_time"] = service.get_average_execution_time()
            
            return {
                "success": True,
                "metrics": metrics,
                "service": service_name,
                "timestamp": datetime.now().isoformat()
            }
        except ValueError as e:
            logger.warning(f"Service metrics request failed: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to get service metrics: {str(e)}")
            logger.error(traceback.format_exc())
            raise
    
    async def _get_system_metrics(self) -> Dict[str, Any]:
        """
        Get system metrics.
        
        Returns:
            System metrics dictionary
        """
        # Check cache
        now = time.time()
        if now - self.system_metrics_cache_time < self.system_metrics_cache_ttl:
            return self.system_metrics_cache
        
        # Collect system metrics
        try:
            # Use psutil to get system metrics
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            metrics = {
                "cpu": {
                    "percent": cpu_percent,
                    "count": psutil.cpu_count(),
                    "frequency": psutil.cpu_freq().current if psutil.cpu_freq() else None
                },
                "memory": {
                    "total": memory.total,
                    "available": memory.available,
                    "used": memory.used,
                    "percent": memory.percent
                },
                "disk": {
                    "total": disk.total,
                    "used": disk.used,
                    "free": disk.free,
                    "percent": disk.percent
                },
                "network": {
                    "connections": len(psutil.net_connections())
                },
                "system": {
                    "platform": platform.system(),
                    "platform_release": platform.release(),
                    "platform_version": platform.version(),
                    "python_version": platform.python_version(),
                    "hostname": platform.node(),
                    "uptime": time.time() - psutil.boot_time()
                }
            }
            
            # Update cache
            self.system_metrics_cache = metrics
            self.system_metrics_cache_time = now
            
            return metrics
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {str(e)}")
            logger.error(traceback.format_exc())
            
            # Return empty metrics on error
            return {
                "error": str(e)
            }
    
    async def _get_all_service_metrics(self) -> Dict[str, Any]:
        """
        Get metrics for all services.
        
        Returns:
            Dictionary of service metrics
        """
        if not self.registry:
            return {}
        
        services = self.registry.get_all_services()
        metrics = {}
        
        for name, service in services.items():
            try:
                if hasattr(service, "get_metrics"):
                    service_metrics = await asyncio.to_thread(service.get_metrics)
                    metrics[name] = service_metrics
                else:
                    metrics[name] = {"state": service.state.name if hasattr(service, "state") else "UNKNOWN"}
            except Exception as e:
                logger.error(f"Failed to get metrics for service {name}: {str(e)}")
                metrics[name] = {"error": str(e)}
        
        return metrics
