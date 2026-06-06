#!/usr/bin/env python3
"""
STRATUM_LIGHT Runtime Controller

This module provides the controller for runtime-related API endpoints,
including system information, runtime state, and logs.
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
except ImportError:
    # Fallback for standalone testing
    class ServiceRegistry: pass
    class ServiceState: pass
    class GraphExecutor: pass

# Set up logger
logger = logging.getLogger(__name__)

class RuntimeController:
    """
    Controller for runtime-related API endpoints.
    
    This controller provides endpoints for system information,
    runtime state, and logs.
    """
    
    def __init__(self, registry: ServiceRegistry, executor: GraphExecutor, runtime_state: Dict[str, Any]):
        """
        Initialize the runtime controller.
        
        Args:
            registry: Service registry instance
            executor: Graph executor instance
            runtime_state: Runtime state dictionary
        """
        self.registry = registry
        self.executor = executor
        self.runtime_state = runtime_state
        self.start_time = datetime.now()
        self.log_buffer = []
        self.max_log_buffer = 1000
        
        # Set up log capture
        self._setup_log_capture()
    
    def _setup_log_capture(self):
        """Set up log capture for API access."""
        class LogCapture(logging.Handler):
            def __init__(self, controller):
                super().__init__()
                self.controller = controller
            
            def emit(self, record):
                try:
                    log_entry = {
                        "timestamp": datetime.fromtimestamp(record.created).isoformat(),
                        "level": record.levelname,
                        "logger": record.name,
                        "message": record.getMessage(),
                        "service": getattr(record, "service", None),
                        "trace_id": getattr(record, "trace_id", None)
                    }
                    
                    # Add exception info if present
                    if record.exc_info:
                        log_entry["exception"] = {
                            "type": record.exc_info[0].__name__,
                            "message": str(record.exc_info[1]),
                            "traceback": self.formatter.formatException(record.exc_info)
                        }
                    
                    # Add to buffer
                    self.controller.add_log_entry(log_entry)
                except Exception as e:
                    # Avoid infinite recursion
                    print(f"Error in log capture: {str(e)}")
        
        # Create and add handler
        handler = LogCapture(self)
        handler.setLevel(logging.INFO)
        logging.getLogger().addHandler(handler)
    
    def add_log_entry(self, entry: Dict[str, Any]):
        """
        Add a log entry to the buffer.
        
        Args:
            entry: Log entry dictionary
        """
        self.log_buffer.append(entry)
        
        # Trim buffer if needed
        if len(self.log_buffer) > self.max_log_buffer:
            self.log_buffer = self.log_buffer[-self.max_log_buffer:]
    
    async def get_system_info(self) -> Dict[str, Any]:
        """
        Get system information.
        
        Returns:
            System information dictionary
        """
        try:
            # Get service counts
            services_count = 0
            services_ready = 0
            
            if self.registry:
                services = self.registry.get_all_services()
                services_count = len(services)
                services_ready = sum(1 for s in services.values() if s.state == ServiceState.READY)
            
            # Calculate uptime
            uptime_seconds = (datetime.now() - self.start_time).total_seconds()
            
            return {
                "success": True,
                "system_name": "STRATUM_LIGHT",
                "version": self.runtime_state.get("version", "1.0.0"),
                "environment": self.runtime_state.get("environment", {}).get("tier", "unknown"),
                "uptime": uptime_seconds,
                "start_time": self.start_time.isoformat(),
                "services_count": services_count,
                "services_ready": services_ready,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to get system info: {str(e)}")
            logger.error(traceback.format_exc())
            raise
    
    async def get_runtime_state(self) -> Dict[str, Any]:
        """
        Get runtime state.
        
        Returns:
            Runtime state dictionary
        """
        try:
            # Get runtime state
            state = self.runtime_state.copy() if self.runtime_state else {}
            
            # Add registry and executor state if available
            if self.registry:
                state["registry"] = {
                    "services_count": len(self.registry.get_all_services()),
                    "has_dependency_cycle": self.registry.check_dependency_cycle() is not None
                }
            
            if self.executor:
                state["executor"] = {
                    "max_workers": self.executor.get_max_workers(),
                    "is_executing": self.executor.is_executing()
                }
            
            return {
                "success": True,
                "state": state,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to get runtime state: {str(e)}")
            logger.error(traceback.format_exc())
            raise
    
    async def reload_runtime(self) -> Dict[str, Any]:
        """
        Reload runtime configuration.
        
        Returns:
            Success response dictionary
        """
        try:
            # Reload runtime configuration
            # This would typically involve reloading environment variables,
            # configuration files, etc.
            logger.info("Reloading runtime configuration")
            
            # Simulate reload delay
            await asyncio.sleep(0.5)
            
            # Update runtime state
            if "reload_count" in self.runtime_state:
                self.runtime_state["reload_count"] += 1
            else:
                self.runtime_state["reload_count"] = 1
            
            self.runtime_state["last_reload"] = datetime.now().isoformat()
            
            return {
                "success": True,
                "message": "Runtime configuration reloaded successfully",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to reload runtime configuration: {str(e)}")
            logger.error(traceback.format_exc())
            raise
    
    async def get_logs(self, limit: int = 100, service: Optional[str] = None, level: Optional[str] = None) -> Dict[str, Any]:
        """
        Get system logs.
        
        Args:
            limit: Maximum number of logs to return
            service: Filter logs by service name
            level: Filter logs by level
            
        Returns:
            Logs response dictionary
        """
        try:
            # Filter logs
            filtered_logs = self.log_buffer
            
            if service:
                filtered_logs = [log for log in filtered_logs if log.get("service") == service]
            
            if level:
                filtered_logs = [log for log in filtered_logs if log.get("level") == level.upper()]
            
            # Sort logs by timestamp (newest first)
            filtered_logs = sorted(filtered_logs, key=lambda x: x.get("timestamp", ""), reverse=True)
            
            # Limit logs
            filtered_logs = filtered_logs[:limit]
            
            return {
                "success": True,
                "logs": filtered_logs,
                "count": len(filtered_logs),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to get logs: {str(e)}")
            logger.error(traceback.format_exc())
            raise
