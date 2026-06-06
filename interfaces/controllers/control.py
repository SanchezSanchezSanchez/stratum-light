#!/usr/bin/env python3
"""
STRATUM_LIGHT Control Controller

This module provides the controller for system control actions,
allowing external agents to trigger system-wide operations.
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

class ControlController:
    """
    Controller for system control actions.
    
    This controller provides endpoints for executing system-wide
    control actions and operations.
    """
    
    def __init__(self, registry: ServiceRegistry, executor: GraphExecutor):
        """
        Initialize the control controller.
        
        Args:
            registry: Service registry instance
            executor: Graph executor instance
        """
        self.registry = registry
        self.executor = executor
        self.available_actions = {
            "start_all": self._start_all,
            "stop_all": self._stop_all,
            "restart_all": self._restart_all,
            "execute_graph": self._execute_graph,
            "health_check": self._health_check,
            "emergency_shutdown": self._emergency_shutdown
        }
    
    async def list_actions(self) -> Dict[str, List[str]]:
        """
        List available control actions.
        
        Returns:
            Dictionary of available actions
        """
        return {
            "actions": list(self.available_actions.keys())
        }
    
    async def execute_action(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a control action.
        
        Args:
            request: Control action request
            
        Returns:
            Control action response dictionary
        """
        try:
            # Get action from request
            action = request.get("action", "").lower()
            if not action:
                raise ValueError("No action specified")
            
            # Check if action exists
            if action not in self.available_actions:
                raise ValueError(f"Unknown action: {action}")
            
            # Get parameters
            params = request.get("parameters", {})
            
            # Execute action
            logger.info(f"Executing control action: {action}")
            result = await self.available_actions[action](params)
            
            return {
                "success": True,
                "action": action,
                "result": result,
                "timestamp": datetime.now().isoformat()
            }
        except ValueError as e:
            logger.warning(f"Control action request failed: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to execute control action: {str(e)}")
            logger.error(traceback.format_exc())
            raise
    
    async def _start_all(self, params: Dict[str, Any]) -> str:
        """
        Start all services.
        
        Args:
            params: Action parameters
            
        Returns:
            Result message
        """
        if not self.executor:
            raise ValueError("Graph executor not available")
        
        # Execute graph with initialization and warm-up
        result = await asyncio.to_thread(
            self.executor.execute_graph,
            initialize=True,
            warm_up=True
        )
        
        return f"Started {len(result.succeeded)} services, {len(result.failed)} failed"
    
    async def _stop_all(self, params: Dict[str, Any]) -> str:
        """
        Stop all services.
        
        Args:
            params: Action parameters
            
        Returns:
            Result message
        """
        if not self.registry:
            raise ValueError("Service registry not available")
        
        # Shutdown all services in reverse dependency order
        services = self.registry.get_all_services()
        shutdown_count = 0
        
        # Get execution order and reverse it for shutdown
        if self.executor:
            execution_plan = self.executor.build_execution_plan()
            service_names = [s.name for s in reversed(execution_plan)]
        else:
            service_names = list(services.keys())
        
        # Shutdown services
        for name in service_names:
            if name in services:
                service = services[name]
                if hasattr(service, "shutdown"):
                    try:
                        await asyncio.to_thread(service.shutdown)
                        shutdown_count += 1
                    except Exception as e:
                        logger.error(f"Failed to shutdown service {name}: {str(e)}")
        
        return f"Stopped {shutdown_count} services"
    
    async def _restart_all(self, params: Dict[str, Any]) -> str:
        """
        Restart all services.
        
        Args:
            params: Action parameters
            
        Returns:
            Result message
        """
        # Stop all services
        stop_result = await self._stop_all(params)
        
        # Wait for a moment to ensure clean shutdown
        await asyncio.sleep(1)
        
        # Start all services
        start_result = await self._start_all(params)
        
        return f"Restart complete: {stop_result}, {start_result}"
    
    async def _execute_graph(self, params: Dict[str, Any]) -> str:
        """
        Execute the service graph.
        
        Args:
            params: Action parameters
            
        Returns:
            Result message
        """
        if not self.executor:
            raise ValueError("Graph executor not available")
        
        # Get execution parameters
        initialize = params.get("initialize", False)
        warm_up = params.get("warm_up", False)
        
        # Execute graph
        result = await asyncio.to_thread(
            self.executor.execute_graph,
            initialize=initialize,
            warm_up=warm_up
        )
        
        return f"Executed {len(result.succeeded)} services, {len(result.failed)} failed"
    
    async def _health_check(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform a health check on all services.
        
        Args:
            params: Action parameters
            
        Returns:
            Health check results
        """
        if not self.registry:
            raise ValueError("Service registry not available")
        
        # Check health of all services
        services = self.registry.get_all_services()
        health_results = {}
        
        for name, service in services.items():
            if hasattr(service, "get_health"):
                try:
                    health = service.get_health()
                    health_results[name] = health
                except Exception as e:
                    health_results[name] = f"Error: {str(e)}"
            else:
                health_results[name] = "Health check not supported"
        
        # Calculate overall health
        healthy_count = sum(1 for h in health_results.values() if h == "healthy")
        total_count = len(health_results)
        
        return {
            "overall": "healthy" if healthy_count == total_count else "degraded",
            "healthy_count": healthy_count,
            "total_count": total_count,
            "services": health_results
        }
    
    async def _emergency_shutdown(self, params: Dict[str, Any]) -> str:
        """
        Perform an emergency shutdown.
        
        Args:
            params: Action parameters
            
        Returns:
            Result message
        """
        # Log emergency shutdown
        logger.warning("Emergency shutdown initiated")
        
        # Stop all services
        await self._stop_all(params)
        
        # Additional emergency actions could be performed here
        # such as saving state, notifying administrators, etc.
        
        return "Emergency shutdown completed"
