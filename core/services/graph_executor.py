#!/usr/bin/env python3
# Graph Executor Module for STRATUM_LIGHT Core Service Lattice

import os
import sys
import logging
import threading
import time
import uuid
from enum import Enum
from typing import Dict, List, Set, Any, Optional, Callable, Type, Union, Tuple
from datetime import datetime
import json
import traceback
import concurrent.futures
from collections import defaultdict

# Import service registry and base service (use shimmed core.* first for identity)
try:
    from core.services.registry import (
        ServiceRegistry, ServiceState, ServiceDependencyType,
        ServiceRegistryError, get_registry, CyclicDependencyError
    )
    from core.services.base_service import BaseService, ServiceError
except ImportError:
    # For standalone testing
    class ServiceRegistry: pass
    class ServiceState(Enum):
        UNREGISTERED = "unregistered"
        REGISTERED = "registered"
        INITIALIZING = "initializing"
        INITIALIZED = "initialized"
        WARMING_UP = "warming_up"
        READY = "ready"
        EXECUTING = "executing"
        PAUSED = "paused"
        STOPPING = "stopping"
        STOPPED = "stopped"
        FAILED = "failed"
        RELOADING = "reloading"
    class ServiceDependencyType(Enum):
        REQUIRED = "required"
        OPTIONAL = "optional"
        RUNTIME = "runtime"
        SOFT = "soft"
    class ServiceRegistryError(Exception): pass
    class CyclicDependencyError(ServiceRegistryError): pass
    class BaseService: pass
    class ServiceError(Exception): pass
    def get_registry(): return None

# Set up logger
logger = logging.getLogger(__name__)

class GraphExecutorError(Exception):
    """Base exception for graph executor errors"""
    pass

class ExecutionPlan:
    """
    Execution plan for services
    
    This class represents a plan for executing services in the correct order
    based on their dependencies.
    """
    
    def __init__(self, layers: List[List[str]]):
        """
        Initialize execution plan
        
        Args:
            layers: List of lists of service names, where each inner list
                   contains services that can be executed in parallel
        """
        self.layers = layers
        self.total_services = sum(len(layer) for layer in layers)
        self.layer_count = len(layers)
    
    def get_service_layer(self, service_name: str) -> Optional[int]:
        """
        Get the layer index for a service
        
        Args:
            service_name: Service name
            
        Returns:
            Layer index, or None if service not found
        """
        for i, layer in enumerate(self.layers):
            if service_name in layer:
                return i
        return None
    
    def get_services_before(self, service_name: str) -> List[str]:
        """
        Get all services that must be executed before the specified service
        
        Args:
            service_name: Service name
            
        Returns:
            List of service names
        """
        layer_index = self.get_service_layer(service_name)
        if layer_index is None:
            return []
        
        # Get all services in previous layers
        result = []
        for i in range(layer_index):
            result.extend(self.layers[i])
        
        return result
    
    def get_services_after(self, service_name: str) -> List[str]:
        """
        Get all services that must be executed after the specified service
        
        Args:
            service_name: Service name
            
        Returns:
            List of service names
        """
        layer_index = self.get_service_layer(service_name)
        if layer_index is None:
            return []
        
        # Get all services in subsequent layers
        result = []
        for i in range(layer_index + 1, len(self.layers)):
            result.extend(self.layers[i])
        
        return result
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert execution plan to dictionary
        
        Returns:
            Dictionary representation of execution plan
        """
        return {
            "layers": self.layers,
            "total_services": self.total_services,
            "layer_count": self.layer_count
        }
    
    def to_json(self, indent: Optional[int] = None) -> str:
        """
        Convert execution plan to JSON
        
        Args:
            indent: JSON indentation
            
        Returns:
            JSON representation of execution plan
        """
        return json.dumps(self.to_dict(), indent=indent)
    
    def __str__(self) -> str:
        """String representation of execution plan"""
        result = f"Execution Plan ({self.layer_count} layers, {self.total_services} services):\n"
        for i, layer in enumerate(self.layers):
            result += f"  Layer {i+1}: {', '.join(layer)}\n"
        return result

class ExecutionResult:
    """
    Result of service execution
    
    This class represents the result of executing a service or a group of services.
    """
    
    def __init__(self):
        """Initialize execution result"""
        self.successful_services: Dict[str, Any] = {}
        self.failed_services: Dict[str, Exception] = {}
        self.skipped_services: Set[str] = set()
        self.execution_times: Dict[str, float] = {}
        self.start_time = datetime.now()
        self.end_time = None
    
    def add_success(self, service_name: str, result: Any = None, execution_time: float = None) -> None:
        """
        Add successful service execution
        
        Args:
            service_name: Service name
            result: Execution result
            execution_time: Execution time in seconds
        """
        self.successful_services[service_name] = result
        if execution_time is not None:
            self.execution_times[service_name] = execution_time
    
    def add_failure(self, service_name: str, error: Exception, execution_time: float = None) -> None:
        """
        Add failed service execution
        
        Args:
            service_name: Service name
            error: Exception that occurred
            execution_time: Execution time in seconds
        """
        self.failed_services[service_name] = error
        if execution_time is not None:
            self.execution_times[service_name] = execution_time
    
    def add_skipped(self, service_name: str) -> None:
        """
        Add skipped service
        
        Args:
            service_name: Service name
        """
        self.skipped_services.add(service_name)
    
    def complete(self) -> None:
        """Mark execution as complete"""
        self.end_time = datetime.now()
    
    @property
    def duration(self) -> float:
        """
        Get execution duration in seconds
        
        Returns:
            Execution duration in seconds
        """
        if self.end_time is None:
            return (datetime.now() - self.start_time).total_seconds()
        return (self.end_time - self.start_time).total_seconds()
    
    @property
    def success(self) -> bool:
        """
        Check if execution was successful
        
        Returns:
            True if all services executed successfully, False otherwise
        """
        return len(self.failed_services) == 0
    
    @property
    def total_services(self) -> int:
        """
        Get total number of services
        
        Returns:
            Total number of services
        """
        return len(self.successful_services) + len(self.failed_services) + len(self.skipped_services)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert execution result to dictionary
        
        Returns:
            Dictionary representation of execution result
        """
        return {
            "success": self.success,
            "total_services": self.total_services,
            "successful_services": len(self.successful_services),
            "failed_services": len(self.failed_services),
            "skipped_services": len(self.skipped_services),
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration": self.duration,
            "execution_times": self.execution_times,
            "failures": {
                name: str(error) for name, error in self.failed_services.items()
            }
        }
    
    def to_json(self, indent: Optional[int] = None) -> str:
        """
        Convert execution result to JSON
        
        Args:
            indent: JSON indentation
            
        Returns:
            JSON representation of execution result
        """
        return json.dumps(self.to_dict(), indent=indent, default=str)
    
    def __str__(self) -> str:
        """String representation of execution result"""
        status = "SUCCESS" if self.success else "FAILURE"
        result = f"Execution Result: {status}\n"
        result += f"  Duration: {self.duration:.2f}s\n"
        result += f"  Total Services: {self.total_services}\n"
        result += f"  Successful: {len(self.successful_services)}\n"
        result += f"  Failed: {len(self.failed_services)}\n"
        result += f"  Skipped: {len(self.skipped_services)}\n"
        
        if self.failed_services:
            result += "  Failures:\n"
            for name, error in self.failed_services.items():
                result += f"    {name}: {str(error)}\n"
        
        return result

class GraphExecutor:
    """
    Graph Executor for STRATUM_LIGHT Core Service Lattice
    
    This class is responsible for executing services in the correct order
    based on their dependencies.
    """
    
    def __init__(self, registry: Optional[ServiceRegistry] = None):
        """
        Initialize graph executor
        
        Args:
            registry: Service registry, or None to use the global registry
        """
        self.registry = registry or get_registry()
        if not self.registry:
            raise GraphExecutorError("Service registry not available")
        
        self._lock = threading.RLock()
        self._execution_history: List[ExecutionResult] = []
        self._current_execution: Optional[ExecutionResult] = None
        self._max_workers = os.cpu_count() or 4
        
        logger.info(f"Graph executor initialized with {self._max_workers} workers")
    
    def create_execution_plan(self, services: Optional[List[str]] = None) -> ExecutionPlan:
        """
        Create execution plan for services
        
        Args:
            services: List of service names to include in the plan,
                     or None to include all registered services
            
        Returns:
            ExecutionPlan object
            
        Raises:
            CyclicDependencyError: If a dependency cycle is found
            ServiceNotFoundError: If a service is not found
        """
        # Resolve execution order from registry
        layers = self.registry.resolve_execution_order()
        
        # Filter services if specified
        if services:
            filtered_layers = []
            for layer in layers:
                filtered_layer = [s for s in layer if s in services]
                if filtered_layer:
                    filtered_layers.append(filtered_layer)
            layers = filtered_layers
        
        return ExecutionPlan(layers)
    
    def initialize_services(self, services: Optional[List[str]] = None, parallel: bool = True) -> ExecutionResult:
        """
        Initialize services
        
        Args:
            services: List of service names to initialize,
                     or None to initialize all registered services
            parallel: Whether to initialize services in parallel
            
        Returns:
            ExecutionResult object
        """
        # Create execution plan
        try:
            plan = self.create_execution_plan(services)
        except Exception as e:
            logger.error(f"Failed to create execution plan: {str(e)}")
            result = ExecutionResult()
            result.complete()
            return result
        
        # Initialize services layer by layer
        result = ExecutionResult()
        self._current_execution = result
        
        try:
            for layer in plan.layers:
                if parallel and len(layer) > 1:
                    # Initialize services in this layer in parallel
                    self._initialize_services_parallel(layer, result)
                else:
                    # Initialize services in this layer sequentially
                    for service_name in layer:
                        self._initialize_service(service_name, result)
        finally:
            result.complete()
            self._execution_history.append(result)
            self._current_execution = None
        
        return result
    
    def _initialize_services_parallel(self, services: List[str], result: ExecutionResult) -> None:
        """
        Initialize services in parallel
        
        Args:
            services: List of service names to initialize
            result: ExecutionResult object to update
        """
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(services), self._max_workers)) as executor:
            # Submit initialization tasks
            futures = {
                executor.submit(self._initialize_service, service_name, result): service_name
                for service_name in services
            }
            
            # Wait for all tasks to complete
            for future in concurrent.futures.as_completed(futures):
                service_name = futures[future]
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Error initializing service '{service_name}' in parallel: {str(e)}")
    
    def _initialize_service(self, service_name: str, result: ExecutionResult) -> bool:
        """
        Initialize a single service
        
        Args:
            service_name: Service name
            result: ExecutionResult object to update
            
        Returns:
            True if initialization was successful, False otherwise
        """
        try:
            # Get service info
            service_info = self.registry.get_service_info(service_name)
            
            # Get service instance and prefer instance state for accuracy
            service = service_info.instance
            current_state = None
            try:
                current_state = service.get_state()  # type: ignore[attr-defined]
            except Exception:
                current_state = service_info.state
            
            # Skip if already initialized or in progress
            if current_state in [
                ServiceState.INITIALIZING, ServiceState.INITIALIZED,
                ServiceState.WARMING_UP, ServiceState.READY,
                ServiceState.EXECUTING
            ]:
                result.add_skipped(service_name)
                return True
            
            if not service:
                raise GraphExecutorError(f"Service '{service_name}' instance not available")
            
            # Initialize service
            start_time = time.time()
            success = service.initialize()
            execution_time = time.time() - start_time
            
            if success:
                result.add_success(service_name, None, execution_time)
                return True
            else:
                result.add_failure(service_name, GraphExecutorError(f"Service '{service_name}' initialization failed"), execution_time)
                return False
        except Exception as e:
            logger.error(f"Error initializing service '{service_name}': {str(e)}")
            logger.error(traceback.format_exc())
            result.add_failure(service_name, e)
            return False
    
    def warm_up_services(self, services: Optional[List[str]] = None, parallel: bool = True) -> ExecutionResult:
        """
        Warm up services
        
        Args:
            services: List of service names to warm up,
                     or None to warm up all initialized services
            parallel: Whether to warm up services in parallel
            
        Returns:
            ExecutionResult object
        """
        # Get services to warm up
        if services is None:
            # Consider all registered services; individual state checks will skip as needed
            services = list(self.registry.get_all_services().keys())
        
        # Create execution plan
        try:
            plan = self.create_execution_plan(services)
        except Exception as e:
            logger.error(f"Failed to create execution plan: {str(e)}")
            result = ExecutionResult()
            result.complete()
            return result
        
        # Warm up services layer by layer
        result = ExecutionResult()
        self._current_execution = result
        
        try:
            for layer in plan.layers:
                if parallel and len(layer) > 1:
                    # Warm up services in this layer in parallel
                    self._warm_up_services_parallel(layer, result)
                else:
                    # Warm up services in this layer sequentially
                    for service_name in layer:
                        self._warm_up_service(service_name, result)
        finally:
            result.complete()
            self._execution_history.append(result)
            self._current_execution = None
        
        return result
    
    def _warm_up_services_parallel(self, services: List[str], result: ExecutionResult) -> None:
        """
        Warm up services in parallel
        
        Args:
            services: List of service names to warm up
            result: ExecutionResult object to update
        """
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(services), self._max_workers)) as executor:
            # Submit warm-up tasks
            futures = {
                executor.submit(self._warm_up_service, service_name, result): service_name
                for service_name in services
            }
            
            # Wait for all tasks to complete
            for future in concurrent.futures.as_completed(futures):
                service_name = futures[future]
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Error warming up service '{service_name}' in parallel: {str(e)}")
    
    def _warm_up_service(self, service_name: str, result: ExecutionResult) -> bool:
        """
        Warm up a single service
        
        Args:
            service_name: Service name
            result: ExecutionResult object to update
            
        Returns:
            True if warm-up was successful, False otherwise
        """
        try:
            # Get service info
            service_info = self.registry.get_service_info(service_name)
            
            # Get service instance and prefer instance state
            service = service_info.instance
            current_state = None
            try:
                current_state = service.get_state()  # type: ignore[attr-defined]
            except Exception:
                current_state = service_info.state
            
            # If already ready, nothing to do
            if current_state == ServiceState.READY:
                result.add_skipped(service_name)
                return True
            
            if not service:
                raise GraphExecutorError(f"Service '{service_name}' instance not available")
            
            # Warm up service
            start_time = time.time()
            success = service.warm_up()
            execution_time = time.time() - start_time
            
            if success:
                result.add_success(service_name, None, execution_time)
                return True
            else:
                result.add_failure(service_name, GraphExecutorError(f"Service '{service_name}' warm-up failed"), execution_time)
                return False
        except Exception as e:
            logger.error(f"Error warming up service '{service_name}': {str(e)}")
            logger.error(traceback.format_exc())
            result.add_failure(service_name, e)
            return False
    
    def start_services(self, services: Optional[List[str]] = None, parallel: bool = True) -> ExecutionResult:
        """
        Start services (initialize and warm up)
        
        Args:
            services: List of service names to start,
                     or None to start all registered services
            parallel: Whether to start services in parallel
            
        Returns:
            ExecutionResult object
        """
        # Create execution plan
        try:
            plan = self.create_execution_plan(services)
        except Exception as e:
            logger.error(f"Failed to create execution plan: {str(e)}")
            result = ExecutionResult()
            result.complete()
            return result
        
        # Start services layer by layer
        result = ExecutionResult()
        self._current_execution = result
        
        try:
            for layer in plan.layers:
                if parallel and len(layer) > 1:
                    # Start services in this layer in parallel
                    self._start_services_parallel(layer, result)
                else:
                    # Start services in this layer sequentially
                    for service_name in layer:
                        self._start_service(service_name, result)
        finally:
            result.complete()
            self._execution_history.append(result)
            self._current_execution = None
        
        return result
    
    def _start_services_parallel(self, services: List[str], result: ExecutionResult) -> None:
        """
        Start services in parallel
        
        Args:
            services: List of service names to start
            result: ExecutionResult object to update
        """
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(services), self._max_workers)) as executor:
            # Submit start tasks
            futures = {
                executor.submit(self._start_service, service_name, result): service_name
                for service_name in services
            }
            
            # Wait for all tasks to complete
            for future in concurrent.futures.as_completed(futures):
                service_name = futures[future]
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Error starting service '{service_name}' in parallel: {str(e)}")
    
    def _start_service(self, service_name: str, result: ExecutionResult) -> bool:
        """
        Start a single service
        
        Args:
            service_name: Service name
            result: ExecutionResult object to update
            
        Returns:
            True if start was successful, False otherwise
        """
        try:
            # Get service info
            service_info = self.registry.get_service_info(service_name)
            
            # Skip if already ready or executing
            if service_info.state in [ServiceState.READY, ServiceState.EXECUTING]:
                result.add_skipped(service_name)
                return True
            
            # Get service instance
            service = service_info.instance
            if not service:
                raise GraphExecutorError(f"Service '{service_name}' instance not available")
            
            # Start service
            start_time = time.time()
            success = service.start()
            execution_time = time.time() - start_time
            
            if success:
                result.add_success(service_name, None, execution_time)
                return True
            else:
                result.add_failure(service_name, GraphExecutorError(f"Service '{service_name}' start failed"), execution_time)
                return False
        except Exception as e:
            logger.error(f"Error starting service '{service_name}': {str(e)}")
            logger.error(traceback.format_exc())
            result.add_failure(service_name, e)
            return False
    
    def execute_services(self, services: Optional[List[str]] = None, parallel: bool = False) -> ExecutionResult:
        """
        Execute services
        
        Args:
            services: List of service names to execute,
                     or None to execute all ready services
            parallel: Whether to execute services in parallel
            
        Returns:
            ExecutionResult object
        """
        # Get services to execute
        if services is None:
            # Consider all registered services; individual state checks will skip as needed
            services = list(self.registry.get_all_services().keys())
        
        # Create execution plan
        try:
            plan = self.create_execution_plan(services)
        except Exception as e:
            logger.error(f"Failed to create execution plan: {str(e)}")
            result = ExecutionResult()
            result.complete()
            return result
        
        # Execute services layer by layer
        result = ExecutionResult()
        self._current_execution = result
        
        try:
            for layer in plan.layers:
                if parallel and len(layer) > 1:
                    # Execute services in this layer in parallel
                    self._execute_services_parallel(layer, result)
                else:
                    # Execute services in this layer sequentially
                    for service_name in layer:
                        self._execute_service(service_name, result)
        finally:
            result.complete()
            self._execution_history.append(result)
            self._current_execution = None
        
        return result
    
    def _execute_services_parallel(self, services: List[str], result: ExecutionResult) -> None:
        """
        Execute services in parallel
        
        Args:
            services: List of service names to execute
            result: ExecutionResult object to update
        """
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(services), self._max_workers)) as executor:
            # Submit execution tasks
            futures = {
                executor.submit(self._execute_service, service_name, result): service_name
                for service_name in services
            }
            
            # Wait for all tasks to complete
            for future in concurrent.futures.as_completed(futures):
                service_name = futures[future]
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Error executing service '{service_name}' in parallel: {str(e)}")
    
    def _execute_service(self, service_name: str, result: ExecutionResult) -> Any:
        """
        Execute a single service
        
        Args:
            service_name: Service name
            result: ExecutionResult object to update
            
        Returns:
            Service execution result
        """
        try:
            # Get service info
            service_info = self.registry.get_service_info(service_name)
            
            # Get service instance and prefer instance state
            service = service_info.instance
            current_state = None
            try:
                current_state = service.get_state()  # type: ignore[attr-defined]
            except Exception:
                current_state = service_info.state
            
            if not service:
                raise GraphExecutorError(f"Service '{service_name}' instance not available")
            
            # Execute service
            start_time = time.time()
            execution_result = service.execute_once()
            execution_time = time.time() - start_time
            
            result.add_success(service_name, execution_result, execution_time)
            return execution_result
        except Exception as e:
            logger.error(f"Error executing service '{service_name}': {str(e)}")
            logger.error(traceback.format_exc())
            result.add_failure(service_name, e)
            return None
    
    def shutdown_services(self, services: Optional[List[str]] = None, parallel: bool = False) -> ExecutionResult:
        """
        Shut down services
        
        Args:
            services: List of service names to shut down,
                     or None to shut down all services
            parallel: Whether to shut down services in parallel
            
        Returns:
            ExecutionResult object
        """
        # Get all services if not specified
        if services is None:
            services = list(self.registry.get_all_services().keys())
        
        # Create execution plan (reverse order)
        try:
            plan = self.create_execution_plan(services)
            # Reverse layers for shutdown
            plan.layers.reverse()
        except Exception as e:
            logger.error(f"Failed to create execution plan: {str(e)}")
            result = ExecutionResult()
            result.complete()
            return result
        
        # Shut down services layer by layer
        result = ExecutionResult()
        self._current_execution = result
        
        try:
            for layer in plan.layers:
                if parallel and len(layer) > 1:
                    # Shut down services in this layer in parallel
                    self._shutdown_services_parallel(layer, result)
                else:
                    # Shut down services in this layer sequentially
                    for service_name in layer:
                        self._shutdown_service(service_name, result)
        finally:
            result.complete()
            self._execution_history.append(result)
            self._current_execution = None
        
        return result
    
    def _shutdown_services_parallel(self, services: List[str], result: ExecutionResult) -> None:
        """
        Shut down services in parallel
        
        Args:
            services: List of service names to shut down
            result: ExecutionResult object to update
        """
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(services), self._max_workers)) as executor:
            # Submit shutdown tasks
            futures = {
                executor.submit(self._shutdown_service, service_name, result): service_name
                for service_name in services
            }
            
            # Wait for all tasks to complete
            for future in concurrent.futures.as_completed(futures):
                service_name = futures[future]
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Error shutting down service '{service_name}' in parallel: {str(e)}")
    
    def _shutdown_service(self, service_name: str, result: ExecutionResult) -> bool:
        """
        Shut down a single service
        
        Args:
            service_name: Service name
            result: ExecutionResult object to update
            
        Returns:
            True if shutdown was successful, False otherwise
        """
        try:
            # Get service info
            service_info = self.registry.get_service_info(service_name)
            
            # Skip if already stopped
            if service_info.state == ServiceState.STOPPED:
                result.add_skipped(service_name)
                return True
            
            # Get service instance
            service = service_info.instance
            if not service:
                raise GraphExecutorError(f"Service '{service_name}' instance not available")
            
            # Shut down service
            start_time = time.time()
            success = service.stop_and_shutdown()
            execution_time = time.time() - start_time
            
            if success:
                result.add_success(service_name, None, execution_time)
                return True
            else:
                result.add_failure(service_name, GraphExecutorError(f"Service '{service_name}' shutdown failed"), execution_time)
                return False
        except Exception as e:
            logger.error(f"Error shutting down service '{service_name}': {str(e)}")
            logger.error(traceback.format_exc())
            result.add_failure(service_name, e)
            return False
    
    def reload_services(self, services: Optional[List[str]] = None, parallel: bool = False) -> ExecutionResult:
        """
        Reload services
        
        Args:
            services: List of service names to reload,
                     or None to reload all services
            parallel: Whether to reload services in parallel
            
        Returns:
            ExecutionResult object
        """
        # Get all services if not specified
        if services is None:
            services = list(self.registry.get_all_services().keys())
        
        # Create execution plan
        try:
            plan = self.create_execution_plan(services)
        except Exception as e:
            logger.error(f"Failed to create execution plan: {str(e)}")
            result = ExecutionResult()
            result.complete()
            return result
        
        # Reload services layer by layer
        result = ExecutionResult()
        self._current_execution = result
        
        try:
            for layer in plan.layers:
                if parallel and len(layer) > 1:
                    # Reload services in this layer in parallel
                    self._reload_services_parallel(layer, result)
                else:
                    # Reload services in this layer sequentially
                    for service_name in layer:
                        self._reload_service(service_name, result)
        finally:
            result.complete()
            self._execution_history.append(result)
            self._current_execution = None
        
        return result
    
    def _reload_services_parallel(self, services: List[str], result: ExecutionResult) -> None:
        """
        Reload services in parallel
        
        Args:
            services: List of service names to reload
            result: ExecutionResult object to update
        """
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(services), self._max_workers)) as executor:
            # Submit reload tasks
            futures = {
                executor.submit(self._reload_service, service_name, result): service_name
                for service_name in services
            }
            
            # Wait for all tasks to complete
            for future in concurrent.futures.as_completed(futures):
                service_name = futures[future]
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Error reloading service '{service_name}' in parallel: {str(e)}")
    
    def _reload_service(self, service_name: str, result: ExecutionResult) -> bool:
        """
        Reload a single service
        
        Args:
            service_name: Service name
            result: ExecutionResult object to update
            
        Returns:
            True if reload was successful, False otherwise
        """
        try:
            # Get service info
            service_info = self.registry.get_service_info(service_name)
            
            # Get service instance
            service = service_info.instance
            if not service:
                raise GraphExecutorError(f"Service '{service_name}' instance not available")
            
            # Reload service
            start_time = time.time()
            success = service.reload()
            execution_time = time.time() - start_time
            
            if success:
                result.add_success(service_name, None, execution_time)
                return True
            else:
                result.add_failure(service_name, GraphExecutorError(f"Service '{service_name}' reload failed"), execution_time)
                return False
        except Exception as e:
            logger.error(f"Error reloading service '{service_name}': {str(e)}")
            logger.error(traceback.format_exc())
            result.add_failure(service_name, e)
            return False
    
    def get_execution_history(self) -> List[ExecutionResult]:
        """
        Get execution history
        
        Returns:
            List of ExecutionResult objects
        """
        return self._execution_history.copy()
    
    def get_current_execution(self) -> Optional[ExecutionResult]:
        """
        Get current execution
        
        Returns:
            Current ExecutionResult object, or None if no execution is in progress
        """
        return self._current_execution
    
    def set_max_workers(self, max_workers: int) -> None:
        """
        Set maximum number of worker threads
        
        Args:
            max_workers: Maximum number of worker threads
        """
        self._max_workers = max(1, max_workers)
        logger.info(f"Graph executor max workers set to {self._max_workers}")
    
    def get_max_workers(self) -> int:
        """
        Get maximum number of worker threads
        
        Returns:
            Maximum number of worker threads
        """
        return self._max_workers
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert graph executor to dictionary
        
        Returns:
            Dictionary representation of graph executor
        """
        return {
            "max_workers": self._max_workers,
            "execution_history_count": len(self._execution_history),
            "current_execution": self._current_execution.to_dict() if self._current_execution else None
        }
    
    def to_json(self, indent: Optional[int] = None) -> str:
        """
        Convert graph executor to JSON
        
        Args:
            indent: JSON indentation
            
        Returns:
            JSON representation of graph executor
        """
        return json.dumps(self.to_dict(), indent=indent, default=str)

# Create singleton instance
_executor = None

def get_executor() -> GraphExecutor:
    """
    Get graph executor instance
    
    Returns:
        GraphExecutor instance
    """
    global _executor
    if _executor is None:
        _executor = GraphExecutor()
    return _executor

# Example usage
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s|%(levelname)s|%(name)s|%(message)s')
    
    # Create mock registry and services
    from unittest.mock import MagicMock
    
    # Mock registry
    registry = MagicMock()
    registry.resolve_execution_order.return_value = [
        ["service1"],
        ["service2", "service3"],
        ["service4"]
    ]
    
    # Mock services
    services = {}
    for name in ["service1", "service2", "service3", "service4"]:
        service = MagicMock()
        service.name = name
        service.initialize.return_value = True
        service.warm_up.return_value = True
        service.execute_once.return_value = {"result": "success"}
        service.stop_and_shutdown.return_value = True
        
        service_info = MagicMock()
        service_info.name = name
        service_info.instance = service
        service_info.state = ServiceState.REGISTERED
        
        services[name] = (service, service_info)
        
        # Set up registry mock
        registry.get_service_info.side_effect = lambda n: services[n][1]
        registry.get_service_instance.side_effect = lambda n: services[n][0]
    
    # Create graph executor
    executor = GraphExecutor(registry)
    
    # Create execution plan
    plan = executor.create_execution_plan()
    print(f"Execution plan: {plan}")
    
    # Initialize services
    result = executor.initialize_services(parallel=True)
    print(f"Initialization result: {result}")
    
    # Warm up services
    result = executor.warm_up_services(parallel=True)
    print(f"Warm-up result: {result}")
    
    # Execute services
    result = executor.execute_services()
    print(f"Execution result: {result}")
    
    # Shutdown services
    result = executor.shutdown_services()
    print(f"Shutdown result: {result}")
