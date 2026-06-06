#!/usr/bin/env python3
# Service Registry Module for STRATUM_LIGHT Core Service Lattice

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
import weakref

# Set up logger
logger = logging.getLogger(__name__)

class ServiceState(Enum):
    """Enumeration of possible service states"""
    UNREGISTERED = "unregistered"  # Service is defined but not registered
    REGISTERED = "registered"      # Service is registered but not initialized
    INITIALIZING = "initializing"  # Service is being initialized
    INITIALIZED = "initialized"    # Service is initialized but not warmed up
    WARMING_UP = "warming_up"      # Service is warming up
    READY = "ready"               # Service is warmed up and ready to execute
    EXECUTING = "executing"        # Service is currently executing
    PAUSED = "paused"              # Service execution is paused
    STOPPING = "stopping"          # Service is being stopped
    STOPPED = "stopped"            # Service is stopped
    FAILED = "failed"              # Service has failed
    RELOADING = "reloading"        # Service is being reloaded

class ServiceDependencyType(Enum):
    """Enumeration of service dependency types"""
    REQUIRED = "required"          # Service must be READY before dependent can initialize
    OPTIONAL = "optional"          # Service should be READY but not required
    RUNTIME = "runtime"            # Service must be READY before dependent can execute
    SOFT = "soft"                  # Service is used if available, but not required

class ServiceRegistryError(Exception):
    """Base exception for service registry errors"""
    pass

class DependencyError(ServiceRegistryError):
    """Exception raised for dependency resolution errors"""
    pass

class CyclicDependencyError(DependencyError):
    """Exception raised for cyclic dependencies"""
    pass

class ServiceNotFoundError(ServiceRegistryError):
    """Exception raised when a service is not found"""
    pass

class ServiceAlreadyRegisteredError(ServiceRegistryError):
    """Exception raised when a service is already registered"""
    pass

class ServiceInfo:
    """Information about a registered service"""
    
    def __init__(
        self, 
        name: str, 
        service_class: Type,
        instance=None,
        dependencies: Dict[str, ServiceDependencyType] = None,
        state: ServiceState = ServiceState.REGISTERED,
        metadata: Dict[str, Any] = None
    ):
        """
        Initialize service information
        
        Args:
            name: Service name
            service_class: Service class
            instance: Service instance (if created)
            dependencies: Dictionary of service dependencies
            state: Current service state
            metadata: Additional service metadata
        """
        self.name = name
        self.service_class = service_class
        self.instance = instance
        self.dependencies = dependencies or {}
        self.state = state
        self.metadata = metadata or {}
        self.registration_time = datetime.now()
        self.last_state_change = datetime.now()
        self.state_history = [(self.state, self.last_state_change)]
        self.error = None
        self.service_id = str(uuid.uuid4())
        
    def update_state(self, state: ServiceState, error: Optional[Exception] = None) -> None:
        """
        Update service state
        
        Args:
            state: New service state
            error: Optional error if state is FAILED
        """
        self.state = state
        self.last_state_change = datetime.now()
        self.state_history.append((state, self.last_state_change))
        
        if error:
            self.error = str(error)
        elif state != ServiceState.FAILED:
            self.error = None
    
    def add_dependency(self, service_name: str, dependency_type: ServiceDependencyType) -> None:
        """
        Add a dependency to the service
        
        Args:
            service_name: Name of the dependency service
            dependency_type: Type of dependency
        """
        self.dependencies[service_name] = dependency_type
    
    def remove_dependency(self, service_name: str) -> None:
        """
        Remove a dependency from the service
        
        Args:
            service_name: Name of the dependency service
        """
        if service_name in self.dependencies:
            del self.dependencies[service_name]
    
    def get_required_dependencies(self) -> List[str]:
        """
        Get list of required dependencies
        
        Returns:
            List of required dependency service names
        """
        return [
            name for name, dep_type in self.dependencies.items()
            if dep_type in [ServiceDependencyType.REQUIRED, ServiceDependencyType.RUNTIME]
        ]
    
    def get_optional_dependencies(self) -> List[str]:
        """
        Get list of optional dependencies
        
        Returns:
            List of optional dependency service names
        """
        return [
            name for name, dep_type in self.dependencies.items()
            if dep_type in [ServiceDependencyType.OPTIONAL, ServiceDependencyType.SOFT]
        ]
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert service info to dictionary
        
        Returns:
            Dictionary representation of service info
        """
        return {
            "name": self.name,
            "service_id": self.service_id,
            "class": self.service_class.__name__,
            "state": self.state.value,
            "dependencies": {
                name: dep_type.value for name, dep_type in self.dependencies.items()
            },
            "registration_time": self.registration_time.isoformat(),
            "last_state_change": self.last_state_change.isoformat(),
            "state_history": [
                {"state": state.value, "timestamp": timestamp.isoformat()}
                for state, timestamp in self.state_history
            ],
            "error": self.error,
            "metadata": self.metadata
        }

class ServiceRegistry:
    """
    Central registry for STRATUM_LIGHT services
    
    This class manages service registration, dependency resolution,
    and service lifecycle tracking.
    """
    
    _instance = None
    _lock = threading.RLock()
    
    def __new__(cls):
        """Ensure singleton instance"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ServiceRegistry, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        """Initialize service registry"""
        with self._lock:
            if self._initialized:
                return
            
            self._services: Dict[str, ServiceInfo] = {}
            self._dependencies_graph: Dict[str, Set[str]] = {}
            self._reverse_dependencies: Dict[str, Set[str]] = {}
            # Preserve registration order for deterministic planning
            self._registration_order: Dict[str, int] = {}
            self._initialized = True
            self._observers: List[Callable[[str, ServiceState, ServiceState], None]] = []
            
            logger.info("Service registry initialized")
    
    def register_service(
        self, 
        name: str, 
        service_class: Type,
        dependencies: Dict[str, ServiceDependencyType] = None,
        metadata: Dict[str, Any] = None
    ) -> ServiceInfo:
        """
        Register a service with the registry
        
        Args:
            name: Service name
            service_class: Service class
            dependencies: Dictionary of service dependencies
            metadata: Additional service metadata
            
        Returns:
            ServiceInfo object for the registered service
            
        Raises:
            ServiceAlreadyRegisteredError: If service is already registered
        """
        with self._lock:
            if name in self._services:
                raise ServiceAlreadyRegisteredError(f"Service '{name}' is already registered")
            
            # Create service info
            service_info = ServiceInfo(
                name=name,
                service_class=service_class,
                dependencies=dependencies,
                metadata=metadata
            )
            
            # Add to registry
            self._services[name] = service_info
            if name not in self._registration_order:
                self._registration_order[name] = len(self._registration_order)
            
            # Update dependency graph
            self._update_dependency_graph(name, dependencies or {})

            # Ensure reverse mapping of dependents has entry
            if name not in self._reverse_dependencies:
                self._reverse_dependencies[name] = set()
            
            logger.info(f"Service '{name}' registered")
            return service_info
    
    def _update_dependency_graph(self, service_name: str, dependencies: Dict[str, ServiceDependencyType]) -> None:
        """
        Update dependency graph with new service
        
        Args:
            service_name: Service name
            dependencies: Dictionary of service dependencies
        """
        # Initialize dependency sets
        if service_name not in self._dependencies_graph:
            self._dependencies_graph[service_name] = set()
        
        # Add dependencies
        for dep_name in dependencies:
            self._dependencies_graph[service_name].add(dep_name)
            
            # Update reverse dependencies
            if dep_name not in self._reverse_dependencies:
                self._reverse_dependencies[dep_name] = set()
            self._reverse_dependencies[dep_name].add(service_name)
    
    def unregister_service(self, name: str) -> None:
        """
        Unregister a service from the registry
        
        Args:
            name: Service name
            
        Raises:
            ServiceNotFoundError: If service is not found
        """
        with self._lock:
            if name not in self._services:
                raise ServiceNotFoundError(f"Service '{name}' not found")
            
            # Remove from registry
            service_info = self._services.pop(name)
            
            # Update dependency graph
            if name in self._dependencies_graph:
                del self._dependencies_graph[name]
            
            # Update reverse dependencies
            for dep_name, dependents in self._reverse_dependencies.items():
                if name in dependents:
                    dependents.remove(name)
            
            if name in self._reverse_dependencies:
                del self._reverse_dependencies[name]
            
            logger.info(f"Service '{name}' unregistered")
    
    def get_service_info(self, name: str) -> ServiceInfo:
        """
        Get information about a registered service
        
        Args:
            name: Service name
            
        Returns:
            ServiceInfo object for the service
            
        Raises:
            ServiceNotFoundError: If service is not found
        """
        with self._lock:
            if name not in self._services:
                raise ServiceNotFoundError(f"Service '{name}' not found")
            
            return self._services[name]
    
    def get_service_instance(self, name: str) -> Any:
        """
        Get service instance
        
        Args:
            name: Service name
            
        Returns:
            Service instance
            
        Raises:
            ServiceNotFoundError: If service is not found
            ValueError: If service instance is not created
        """
        with self._lock:
            service_info = self.get_service_info(name)
            
            if service_info.instance is None:
                raise ValueError(f"Service '{name}' instance is not created")
            
            return service_info.instance
    
    def set_service_instance(self, name: str, instance: Any) -> None:
        """
        Set service instance
        
        Args:
            name: Service name
            instance: Service instance
            
        Raises:
            ServiceNotFoundError: If service is not found
        """
        with self._lock:
            # Auto-register service if not present, using instance class and its dependencies if available
            if name not in self._services:
                deps = getattr(instance, "dependencies", {}) if instance is not None else {}
                self.register_service(name=name, service_class=instance.__class__ if instance else type(None), dependencies=deps)
            service_info = self.get_service_info(name)
            service_info.instance = instance
    
    def update_service_state(self, name: str, state: ServiceState, error: Optional[Exception] = None) -> None:
        """
        Update service state
        
        Args:
            name: Service name
            state: New service state
            error: Optional error if state is FAILED
            
        Raises:
            ServiceNotFoundError: If service is not found
        """
        with self._lock:
            service_info = self.get_service_info(name)
            old_state = service_info.state
            service_info.update_state(state, error)
            
            # Notify observers
            for observer in self._observers:
                try:
                    observer(name, old_state, state)
                except Exception as e:
                    logger.error(f"Error notifying observer for service '{name}': {str(e)}")
            
            logger.info(f"Service '{name}' state changed from {old_state.value} to {state.value}")
    
    def get_service_state(self, name: str) -> ServiceState:
        """
        Get service state
        
        Args:
            name: Service name
            
        Returns:
            Current service state
            
        Raises:
            ServiceNotFoundError: If service is not found
        """
        with self._lock:
            service_info = self.get_service_info(name)
            return service_info.state
    
    def get_services_by_state(self, state: ServiceState) -> List[str]:
        """
        Get list of services in the specified state
        
        Args:
            state: Service state
            
        Returns:
            List of service names
        """
        with self._lock:
            return [
                name for name, info in self._services.items()
                if info.state == state
            ]
    
    def get_all_services(self) -> Dict[str, ServiceInfo]:
        """
        Get all registered services
        
        Returns:
            Dictionary of service names to ServiceInfo objects
        """
        with self._lock:
            return self._services.copy()
    
    def get_service_dependencies(self, name: str) -> Dict[str, ServiceDependencyType]:
        """
        Get service dependencies
        
        Args:
            name: Service name
            
        Returns:
            Dictionary of dependency service names to dependency types
            
        Raises:
            ServiceNotFoundError: If service is not found
        """
        with self._lock:
            service_info = self.get_service_info(name)
            return service_info.dependencies.copy()
    
    def get_service_dependents(self, name: str) -> List[str]:
        """
        Get services that depend on the specified service
        
        Args:
            name: Service name
            
        Returns:
            List of dependent service names
        """
        with self._lock:
            return list(self._reverse_dependencies.get(name, set()))
    
    def check_dependency_cycle(self) -> Optional[List[str]]:
        """
        Check for dependency cycles in the service graph
        
        Returns:
            List of services in the cycle, or None if no cycle is found
        """
        with self._lock:
            # Use Tarjan's algorithm to find cycles
            visited = set()
            temp_visited = set()
            cycles = []
            
            def visit(node, path):
                if node in temp_visited:
                    # Found a cycle
                    cycle_start = path.index(node)
                    cycles.append(path[cycle_start:] + [node])
                    return
                
                if node in visited:
                    return
                
                temp_visited.add(node)
                path.append(node)
                
                for neighbor in self._dependencies_graph.get(node, set()):
                    if neighbor in self._services:
                        visit(neighbor, path.copy())
                
                temp_visited.remove(node)
                visited.add(node)
            
            for node in self._dependencies_graph:
                if node not in visited and node not in temp_visited:
                    visit(node, [])
            
            return cycles[0] if cycles else None
    
    def resolve_execution_order(self) -> List[List[str]]:
        """
        Resolve service execution order based on dependencies
        
        Returns:
            List of lists of service names, where each inner list
            contains services that can be executed in parallel
            
        Raises:
            CyclicDependencyError: If a dependency cycle is found
        """
        with self._lock:
            # Check for cycles
            cycle = self.check_dependency_cycle()
            if cycle:
                raise CyclicDependencyError(f"Dependency cycle detected: {' -> '.join(cycle)}")
            
            # Kahn's algorithm to ensure root (no deps) are first layer
            # Build in-degree map for registered services only
            in_degree = {name: 0 for name in self._services.keys()}
            for svc, deps in self._dependencies_graph.items():
                if svc in in_degree:
                    for dep in deps:
                        if dep in in_degree:
                            in_degree[svc] += 1

            # Start with nodes that have no incoming edges
            queue = [name for name, deg in in_degree.items() if deg == 0]
            # Sort initial queue by registration order
            queue.sort(key=lambda n: self._registration_order.get(n, 0))
            layers: List[List[str]] = []

            visited = set()
            while queue:
                current_layer: List[str] = []
                next_queue: List[str] = []
                for node in queue:
                    if node in visited:
                        continue
                    visited.add(node)
                    current_layer.append(node)
                    for dependent in sorted(self._reverse_dependencies.get(node, set()), key=lambda n: self._registration_order.get(n, 0)):
                        if dependent in in_degree:
                            in_degree[dependent] -= 1
                            if in_degree[dependent] == 0:
                                next_queue.append(dependent)
                if current_layer:
                    # Sort layer deterministically by registration order
                    current_layer.sort(key=lambda n: self._registration_order.get(n, 0))
                    layers.append(current_layer)
                # Deduplicate and sort next queue deterministically
                queue = sorted(list(dict.fromkeys(next_queue)), key=lambda n: self._registration_order.get(n, 0))

            # Any remaining nodes (due to unregistered deps) append them deterministically
            remaining = [name for name in self._services.keys() if name not in {s for layer in layers for s in layer}]
            if remaining:
                remaining.sort(key=lambda n: self._registration_order.get(n, 0))
                layers.append(remaining)

            return layers
    
    def add_observer(self, observer: Callable[[str, ServiceState, ServiceState], None]) -> None:
        """
        Add an observer for service state changes
        
        Args:
            observer: Observer function that takes service name, old state, and new state
        """
        with self._lock:
            self._observers.append(observer)
    
    def remove_observer(self, observer: Callable[[str, ServiceState, ServiceState], None]) -> None:
        """
        Remove an observer
        
        Args:
            observer: Observer function to remove
        """
        with self._lock:
            if observer in self._observers:
                self._observers.remove(observer)
    
    def get_registry_status(self) -> Dict[str, Any]:
        """
        Get registry status
        
        Returns:
            Dictionary with registry status information
        """
        with self._lock:
            services_by_state = {}
            for state in ServiceState:
                services_by_state[state.value] = self.get_services_by_state(state)
            
            return {
                "total_services": len(self._services),
                "services_by_state": services_by_state,
                "dependency_graph": {
                    name: list(deps) for name, deps in self._dependencies_graph.items()
                },
                "reverse_dependencies": {
                    name: list(deps) for name, deps in self._reverse_dependencies.items()
                }
            }
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert registry to dictionary
        
        Returns:
            Dictionary representation of registry
        """
        with self._lock:
            return {
                "services": {
                    name: info.to_dict() for name, info in self._services.items()
                },
                "status": self.get_registry_status()
            }
    
    def to_json(self, indent: Optional[int] = None) -> str:
        """
        Convert registry to JSON
        
        Args:
            indent: JSON indentation
            
        Returns:
            JSON representation of registry
        """
        return json.dumps(self.to_dict(), indent=indent, default=str)

# Create/get singleton instance via class-level singleton to respect test resets
def get_registry() -> ServiceRegistry:
    """
    Get service registry instance
    
    Returns:
        ServiceRegistry instance
    """
    return ServiceRegistry()

def reset_registry() -> None:
    """Reset the singleton registry state (testing utility)."""
    with ServiceRegistry._lock:  # noqa: SLF001 - test-only utility
        ServiceRegistry._instance = None

# Example usage
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s|%(levelname)s|%(name)s|%(message)s')
    
    # Get registry
    registry = get_registry()
    
    # Define example service class
    class ExampleService:
        pass
    
    # Register services
    registry.register_service("service1", ExampleService)
    registry.register_service("service2", ExampleService, {"service1": ServiceDependencyType.REQUIRED})
    registry.register_service("service3", ExampleService, {"service2": ServiceDependencyType.REQUIRED})
    
    # Update service states
    registry.update_service_state("service1", ServiceState.INITIALIZED)
    registry.update_service_state("service2", ServiceState.INITIALIZED)
    
    # Resolve execution order
    execution_order = registry.resolve_execution_order()
    print(f"Execution order: {execution_order}")
    
    # Print registry status
    print(registry.to_json(indent=2))
