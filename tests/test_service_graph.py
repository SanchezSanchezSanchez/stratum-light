#!/usr/bin/env python3
# Tests for STRATUM_LIGHT Core Service Lattice

import os
import sys
import unittest
import logging
import threading
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
import json
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s|%(levelname)s|%(name)s|%(message)s')
logger = logging.getLogger(__name__)

# Import service modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from core.services.registry import (
    ServiceRegistry, ServiceState, ServiceDependencyType,
    ServiceRegistryError, get_registry, CyclicDependencyError
)
from core.services.base_service import BaseService, ServiceError, SimpleService
from core.services.graph_executor import (
    GraphExecutor, ExecutionPlan, ExecutionResult,
    GraphExecutorError, get_executor
)
from core.services.example_services import (
    DataIngestService, TelemetryService, ControlLoopService
)

class TestServiceRegistry(unittest.TestCase):
    """Tests for ServiceRegistry"""
    
    def setUp(self):
        """Set up test environment"""
        # Create a new registry for each test
        self.registry = ServiceRegistry()
        
        # Reset registry singleton
        ServiceRegistry._instance = None
        ServiceRegistry._lock = threading.RLock()
    
    def test_singleton(self):
        """Test registry singleton pattern"""
        registry1 = get_registry()
        registry2 = get_registry()
        self.assertIs(registry1, registry2)
    
    def test_register_service(self):
        """Test service registration"""
        # Register a service
        service_info = self.registry.register_service(
            name="test_service",
            service_class=SimpleService,
            dependencies={"dep1": ServiceDependencyType.REQUIRED},
            metadata={"key": "value"}
        )
        
        # Check service info
        self.assertEqual(service_info.name, "test_service")
        self.assertEqual(service_info.service_class, SimpleService)
        self.assertEqual(service_info.dependencies, {"dep1": ServiceDependencyType.REQUIRED})
        self.assertEqual(service_info.metadata, {"key": "value"})
        self.assertEqual(service_info.state, ServiceState.REGISTERED)
        
        # Check registry state
        self.assertIn("test_service", self.registry.get_all_services())
        
        # Test duplicate registration
        with self.assertRaises(ServiceRegistryError):
            self.registry.register_service(
                name="test_service",
                service_class=SimpleService
            )
    
    def test_unregister_service(self):
        """Test service unregistration"""
        # Register a service
        self.registry.register_service(
            name="test_service",
            service_class=SimpleService
        )
        
        # Unregister the service
        self.registry.unregister_service("test_service")
        
        # Check registry state
        self.assertNotIn("test_service", self.registry.get_all_services())
        
        # Test unregistering non-existent service
        with self.assertRaises(ServiceRegistryError):
            self.registry.unregister_service("non_existent_service")
    
    def test_get_service_info(self):
        """Test getting service info"""
        # Register a service
        self.registry.register_service(
            name="test_service",
            service_class=SimpleService
        )
        
        # Get service info
        service_info = self.registry.get_service_info("test_service")
        self.assertEqual(service_info.name, "test_service")
        self.assertEqual(service_info.service_class, SimpleService)
        
        # Test getting non-existent service
        with self.assertRaises(ServiceRegistryError):
            self.registry.get_service_info("non_existent_service")
    
    def test_update_service_state(self):
        """Test updating service state"""
        # Register a service
        self.registry.register_service(
            name="test_service",
            service_class=SimpleService
        )
        
        # Update service state
        self.registry.update_service_state("test_service", ServiceState.INITIALIZED)
        
        # Check service state
        service_info = self.registry.get_service_info("test_service")
        self.assertEqual(service_info.state, ServiceState.INITIALIZED)
        
        # Test updating non-existent service
        with self.assertRaises(ServiceRegistryError):
            self.registry.update_service_state("non_existent_service", ServiceState.INITIALIZED)
    
    def test_dependency_cycle_detection(self):
        """Test dependency cycle detection"""
        # Register services with a cycle
        self.registry.register_service(
            name="service1",
            service_class=SimpleService,
            dependencies={"service3": ServiceDependencyType.REQUIRED}
        )
        self.registry.register_service(
            name="service2",
            service_class=SimpleService,
            dependencies={"service1": ServiceDependencyType.REQUIRED}
        )
        self.registry.register_service(
            name="service3",
            service_class=SimpleService,
            dependencies={"service2": ServiceDependencyType.REQUIRED}
        )
        
        # Check for cycle
        cycle = self.registry.check_dependency_cycle()
        self.assertIsNotNone(cycle)
        
        # Test execution order with cycle
        with self.assertRaises(CyclicDependencyError):
            self.registry.resolve_execution_order()
    
    def test_execution_order(self):
        """Test execution order resolution"""
        # Register services without a cycle
        self.registry.register_service(
            name="service1",
            service_class=SimpleService
        )
        self.registry.register_service(
            name="service2",
            service_class=SimpleService,
            dependencies={"service1": ServiceDependencyType.REQUIRED}
        )
        self.registry.register_service(
            name="service3",
            service_class=SimpleService,
            dependencies={"service1": ServiceDependencyType.REQUIRED}
        )
        self.registry.register_service(
            name="service4",
            service_class=SimpleService,
            dependencies={
                "service2": ServiceDependencyType.REQUIRED,
                "service3": ServiceDependencyType.REQUIRED
            }
        )
        
        # Resolve execution order
        execution_order = self.registry.resolve_execution_order()
        
        # Check execution order
        self.assertEqual(len(execution_order), 3)  # 3 layers
        self.assertIn("service1", execution_order[0])  # service1 in first layer
        self.assertIn("service2", execution_order[1])  # service2 in second layer
        self.assertIn("service3", execution_order[1])  # service3 in second layer
        self.assertIn("service4", execution_order[2])  # service4 in third layer
    
    def test_observers(self):
        """Test service state change observers"""
        # Create observer
        observer_called = False
        observed_service = None
        observed_old_state = None
        observed_new_state = None
        
        def observer(service_name, old_state, new_state):
            nonlocal observer_called, observed_service, observed_old_state, observed_new_state
            observer_called = True
            observed_service = service_name
            observed_old_state = old_state
            observed_new_state = new_state
        
        # Register observer
        self.registry.add_observer(observer)
        
        # Register a service
        self.registry.register_service(
            name="test_service",
            service_class=SimpleService
        )
        
        # Update service state
        self.registry.update_service_state("test_service", ServiceState.INITIALIZED)
        
        # Check observer was called
        self.assertTrue(observer_called)
        self.assertEqual(observed_service, "test_service")
        self.assertEqual(observed_old_state, ServiceState.REGISTERED)
        self.assertEqual(observed_new_state, ServiceState.INITIALIZED)
        
        # Remove observer
        self.registry.remove_observer(observer)
        
        # Reset observer state
        observer_called = False
        
        # Update service state again
        self.registry.update_service_state("test_service", ServiceState.READY)
        
        # Check observer was not called
        self.assertFalse(observer_called)

class TestBaseService(unittest.TestCase):
    """Tests for BaseService"""
    
    def setUp(self):
        """Set up test environment"""
        # Reset registry singleton
        ServiceRegistry._instance = None
        ServiceRegistry._lock = threading.RLock()
        
        # Get registry
        self.registry = get_registry()
    
    def test_service_lifecycle(self):
        """Test service lifecycle"""
        # Create service
        service = SimpleService("test_service")
        
        # Check initial state
        self.assertEqual(service.get_state(), ServiceState.REGISTERED)
        
        # Initialize service
        success = service.initialize()
        self.assertTrue(success)
        self.assertEqual(service.get_state(), ServiceState.INITIALIZED)
        
        # Warm up service
        success = service.warm_up()
        self.assertTrue(success)
        self.assertEqual(service.get_state(), ServiceState.READY)
        
        # Execute service
        result = service.execute_once()
        self.assertIsNotNone(result)
        self.assertEqual(service.get_state(), ServiceState.READY)
        
        # Shutdown service
        success = service.stop_and_shutdown()
        self.assertTrue(success)
        self.assertEqual(service.get_state(), ServiceState.STOPPED)
    
    def test_service_dependencies(self):
        """Test service dependencies"""
        # Create services
        service1 = SimpleService("service1")
        service2 = SimpleService(
            "service2",
            dependencies={"service1": ServiceDependencyType.REQUIRED}
        )
        
        # Check dependencies
        self.assertEqual(service2.get_dependencies(), {"service1": ServiceDependencyType.REQUIRED})
        
        # Add dependency
        service2.add_dependency("service3", ServiceDependencyType.OPTIONAL)
        self.assertEqual(
            service2.get_dependencies(),
            {
                "service1": ServiceDependencyType.REQUIRED,
                "service3": ServiceDependencyType.OPTIONAL
            }
        )
        
        # Remove dependency
        service2.remove_dependency("service3")
        self.assertEqual(service2.get_dependencies(), {"service1": ServiceDependencyType.REQUIRED})
    
    def test_service_continuous_execution(self):
        """Test service continuous execution"""
        # Create service
        service = SimpleService("test_service")
        
        # Initialize and warm up
        service.initialize()
        service.warm_up()
        
        # Start continuous execution
        service.execute_continuous(interval=0.1)
        
        # Wait for a few executions
        time.sleep(0.5)
        
        # Check execution count
        self.assertGreater(service._execution_count, 1)
        
        # Pause execution
        service.pause()
        execution_count = service._execution_count
        time.sleep(0.3)
        
        # Check execution count didn't change
        self.assertEqual(service._execution_count, execution_count)
        
        # Resume execution
        service.resume()
        time.sleep(0.3)
        
        # Check execution count increased
        self.assertGreater(service._execution_count, execution_count)
        
        # Stop execution
        service.stop()
        execution_count = service._execution_count
        time.sleep(0.3)
        
        # Check execution count didn't change
        self.assertEqual(service._execution_count, execution_count)
        
        # Shutdown service
        service.stop_and_shutdown()
    
    def test_service_reload(self):
        """Test service reload"""
        # Create service
        service = SimpleService("test_service")
        
        # Initialize and warm up
        service.initialize()
        service.warm_up()
        
        # Execute once
        service.execute_once()
        
        # Reload service
        success = service.reload()
        self.assertTrue(success)
        self.assertEqual(service.get_state(), ServiceState.READY)
        
        # Execute again
        result = service.execute_once()
        self.assertIsNotNone(result)
        
        # Shutdown service
        service.stop_and_shutdown()

class TestGraphExecutor(unittest.TestCase):
    """Tests for GraphExecutor"""
    
    def setUp(self):
        """Set up test environment"""
        # Reset registry singleton
        ServiceRegistry._instance = None
        ServiceRegistry._lock = threading.RLock()
        
        # Get registry
        self.registry = get_registry()
        
        # Create executor
        self.executor = GraphExecutor(self.registry)
    
    def test_execution_plan(self):
        """Test execution plan creation"""
        # Register services
        self.registry.register_service(
            name="service1",
            service_class=SimpleService
        )
        self.registry.register_service(
            name="service2",
            service_class=SimpleService,
            dependencies={"service1": ServiceDependencyType.REQUIRED}
        )
        self.registry.register_service(
            name="service3",
            service_class=SimpleService,
            dependencies={"service1": ServiceDependencyType.REQUIRED}
        )
        
        # Create execution plan
        plan = self.executor.create_execution_plan()
        
        # Check plan
        self.assertEqual(plan.layer_count, 2)
        self.assertEqual(plan.total_services, 3)
        self.assertIn("service1", plan.layers[0])
        self.assertIn("service2", plan.layers[1])
        self.assertIn("service3", plan.layers[1])
        
        # Check service layer
        self.assertEqual(plan.get_service_layer("service1"), 0)
        self.assertEqual(plan.get_service_layer("service2"), 1)
        self.assertEqual(plan.get_service_layer("service3"), 1)
        
        # Check services before/after
        self.assertEqual(plan.get_services_before("service2"), ["service1"])
        self.assertEqual(plan.get_services_after("service1"), ["service2", "service3"])
    
    def test_initialize_services(self):
        """Test service initialization"""
        # Create services
        service1 = SimpleService("service1")
        service2 = SimpleService(
            "service2",
            dependencies={"service1": ServiceDependencyType.REQUIRED}
        )
        
        # Set service instances in registry
        self.registry.set_service_instance("service1", service1)
        self.registry.set_service_instance("service2", service2)
        
        # Initialize services
        result = self.executor.initialize_services()
        
        # Check result
        self.assertTrue(result.success)
        self.assertEqual(result.total_services, 2)
        self.assertEqual(len(result.successful_services), 2)
        self.assertEqual(len(result.failed_services), 0)
        
        # Check service states
        self.assertEqual(service1.get_state(), ServiceState.INITIALIZED)
        self.assertEqual(service2.get_state(), ServiceState.INITIALIZED)
    
    def test_warm_up_services(self):
        """Test service warm-up"""
        # Create services
        service1 = SimpleService("service1")
        service2 = SimpleService(
            "service2",
            dependencies={"service1": ServiceDependencyType.REQUIRED}
        )
        
        # Set service instances in registry
        self.registry.set_service_instance("service1", service1)
        self.registry.set_service_instance("service2", service2)
        
        # Initialize services
        self.executor.initialize_services()
        
        # Warm up services
        result = self.executor.warm_up_services()
        
        # Check result
        self.assertTrue(result.success)
        self.assertEqual(result.total_services, 2)
        self.assertEqual(len(result.successful_services), 2)
        self.assertEqual(len(result.failed_services), 0)
        
        # Check service states
        self.assertEqual(service1.get_state(), ServiceState.READY)
        self.assertEqual(service2.get_state(), ServiceState.READY)
    
    def test_start_services(self):
        """Test service start"""
        # Create services
        service1 = SimpleService("service1")
        service2 = SimpleService(
            "service2",
            dependencies={"service1": ServiceDependencyType.REQUIRED}
        )
        
        # Set service instances in registry
        self.registry.set_service_instance("service1", service1)
        self.registry.set_service_instance("service2", service2)
        
        # Start services
        result = self.executor.start_services()
        
        # Check result
        self.assertTrue(result.success)
        self.assertEqual(result.total_services, 2)
        self.assertEqual(len(result.successful_services), 2)
        self.assertEqual(len(result.failed_services), 0)
        
        # Check service states
        self.assertEqual(service1.get_state(), ServiceState.READY)
        self.assertEqual(service2.get_state(), ServiceState.READY)
    
    def test_execute_services(self):
        """Test service execution"""
        # Create services
        service1 = SimpleService("service1")
        service2 = SimpleService(
            "service2",
            dependencies={"service1": ServiceDependencyType.REQUIRED}
        )
        
        # Set service instances in registry
        self.registry.set_service_instance("service1", service1)
        self.registry.set_service_instance("service2", service2)
        
        # Start services
        self.executor.start_services()
        
        # Execute services
        result = self.executor.execute_services()
        
        # Check result
        self.assertTrue(result.success)
        self.assertEqual(result.total_services, 2)
        self.assertEqual(len(result.successful_services), 2)
        self.assertEqual(len(result.failed_services), 0)
        
        # Check execution results
        for service_name, execution_result in result.successful_services.items():
            self.assertIsNotNone(execution_result)
    
    def test_shutdown_services(self):
        """Test service shutdown"""
        # Create services
        service1 = SimpleService("service1")
        service2 = SimpleService(
            "service2",
            dependencies={"service1": ServiceDependencyType.REQUIRED}
        )
        
        # Set service instances in registry
        self.registry.set_service_instance("service1", service1)
        self.registry.set_service_instance("service2", service2)
        
        # Start services
        self.executor.start_services()
        
        # Shutdown services
        result = self.executor.shutdown_services()
        
        # Check result
        self.assertTrue(result.success)
        self.assertEqual(result.total_services, 2)
        self.assertEqual(len(result.successful_services), 2)
        self.assertEqual(len(result.failed_services), 0)
        
        # Check service states
        self.assertEqual(service1.get_state(), ServiceState.STOPPED)
        self.assertEqual(service2.get_state(), ServiceState.STOPPED)
    
    def test_parallel_execution(self):
        """Test parallel service execution"""
        # Create services
        services = []
        for i in range(5):
            service = SimpleService(f"service{i}")
            services.append(service)
            self.registry.set_service_instance(f"service{i}", service)
        
        # Set max workers
        self.executor.set_max_workers(3)
        self.assertEqual(self.executor.get_max_workers(), 3)
        
        # Start services in parallel
        start_time = time.time()
        result = self.executor.start_services(parallel=True)
        duration = time.time() - start_time
        
        # Check result
        self.assertTrue(result.success)
        self.assertEqual(result.total_services, 5)
        
        # Check service states
        for service in services:
            self.assertEqual(service.get_state(), ServiceState.READY)

class TestExampleServices(unittest.TestCase):
    """Tests for example services"""
    
    def setUp(self):
        """Set up test environment"""
        # Reset registry singleton
        ServiceRegistry._instance = None
        ServiceRegistry._lock = threading.RLock()
        
        # Get registry
        self.registry = get_registry()
        
        # Create executor
        self.executor = GraphExecutor(self.registry)
    
    def test_data_ingest_service(self):
        """Test DataIngestService"""
        # Create service
        service = DataIngestService()
        
        # Initialize and warm up
        success = service.initialize()
        self.assertTrue(success)
        
        success = service.warm_up()
        self.assertTrue(success)
        
        # Execute once
        result = service.execute_once()
        self.assertIsNotNone(result)
        
        # Check queue
        queue_size = service.get_queue_size()
        self.assertGreaterEqual(queue_size, 0)
        
        # Get data stats
        stats = service.get_data_stats()
        self.assertIn("ingested", stats)
        self.assertIn("processed", stats)
        
        # Shutdown service
        success = service.stop_and_shutdown()
        self.assertTrue(success)
    
    def test_telemetry_service(self):
        """Test TelemetryService"""
        # Create data ingest service first
        data_ingest = DataIngestService()
        data_ingest.initialize()
        data_ingest.warm_up()
        
        # Create telemetry service
        service = TelemetryService()
        
        # Initialize and warm up
        success = service.initialize()
        self.assertTrue(success)
        
        success = service.warm_up()
        self.assertTrue(success)
        
        # Execute once
        result = service.execute_once()
        self.assertIsNotNone(result)
        
        # Get telemetry data
        telemetry_data = service.get_telemetry_data()
        self.assertIsInstance(telemetry_data, list)
        
        # Get telemetry stats
        stats = service.get_telemetry_stats()
        self.assertIn("collected", stats)
        self.assertIn("sent", stats)
        
        # Shutdown services
        service.stop_and_shutdown()
        data_ingest.stop_and_shutdown()
    
    def test_control_loop_service(self):
        """Test ControlLoopService"""
        # Create data ingest and telemetry services first
        data_ingest = DataIngestService()
        data_ingest.initialize()
        data_ingest.warm_up()
        
        telemetry = TelemetryService()
        telemetry.initialize()
        telemetry.warm_up()
        
        # Create control loop service
        service = ControlLoopService()
        
        # Initialize and warm up
        success = service.initialize()
        self.assertTrue(success)
        
        success = service.warm_up()
        self.assertTrue(success)
        
        # Execute once
        result = service.execute_once()
        self.assertIsNotNone(result)
        
        # Get control stats
        stats = service.get_control_stats()
        self.assertIn("evaluations", stats)
        self.assertIn("actions_triggered", stats)
        
        # Get control rules
        rules = service.get_control_rules()
        self.assertIsInstance(rules, list)
        self.assertGreater(len(rules), 0)
        
        # Shutdown services
        service.stop_and_shutdown()
        telemetry.stop_and_shutdown()
        data_ingest.stop_and_shutdown()
    
    def test_service_integration(self):
        """Test integration of all example services"""
        # Create services
        data_ingest = DataIngestService()
        telemetry = TelemetryService()
        control_loop = ControlLoopService()
        
        # Set service instances in registry
        self.registry.set_service_instance("data_ingest", data_ingest)
        self.registry.set_service_instance("telemetry", telemetry)
        self.registry.set_service_instance("control_loop", control_loop)
        
        # Start all services
        result = self.executor.start_services()
        self.assertTrue(result.success)
        
        # Execute all services
        result = self.executor.execute_services()
        self.assertTrue(result.success)
        
        # Start continuous execution
        data_ingest.start_continuous_ingest(interval=0.1)
        telemetry.start_continuous_telemetry(interval=0.2)
        control_loop.start_continuous_control(interval=0.3)
        
        # Wait for a few executions
        time.sleep(1.0)
        
        # Check data flow
        self.assertGreater(data_ingest.get_data_stats()["processed"], 0)
        self.assertGreater(len(telemetry.get_telemetry_data()), 0)
        self.assertGreater(control_loop.get_control_stats()["evaluations"], 0)
        
        # Shutdown all services
        result = self.executor.shutdown_services()
        self.assertTrue(result.success)

if __name__ == "__main__":
    unittest.main()
