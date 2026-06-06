#!/usr/bin/env python3
# Example Services for STRATUM_LIGHT Core Service Lattice

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
import random
import queue

# Import service registry and base service
try:
    from product.core.services.registry import (
        ServiceRegistry, ServiceState, ServiceDependencyType,
        ServiceRegistryError, get_registry
    )
    from product.core.services.base_service import BaseService, ServiceError
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
    class BaseService: pass
    class ServiceError(Exception): pass
    def get_registry(): return None

# Set up logger
logger = logging.getLogger(__name__)

class DataIngestService(BaseService):
    """
    Data Ingestion Service
    
    This service is responsible for ingesting data from various sources
    and making it available to other services.
    """
    
    def __init__(self, name: str = "data_ingest", dependencies: Dict[str, ServiceDependencyType] = None, metadata: Dict[str, Any] = None):
        """
        Initialize data ingest service
        
        Args:
            name: Service name
            dependencies: Dictionary of service dependencies
            metadata: Additional service metadata
        """
        # Set default metadata
        metadata = metadata or {}
        metadata.update({
            "description": "Data Ingestion Service",
            "data_sources": ["api", "file", "stream"],
            "version": "1.0.0"
        })
        
        super().__init__(name, dependencies, metadata)
        
        # Initialize service-specific attributes
        self._data_queue = queue.Queue()
        self._data_sources = {}
        self._data_processors = {}
        self._data_stats = {
            "ingested": 0,
            "processed": 0,
            "dropped": 0,
            "last_ingest_time": None
        }
        self._running = False
        self._ingest_thread = None
        self._ingest_interval = 1.0  # seconds
    
    def init(self) -> bool:
        """
        Initialize the service
        
        Returns:
            True if initialization was successful, False otherwise
        """
        logger.info(f"Initializing {self.name} service")
        
        try:
            # Register data sources
            self._register_data_sources()
            
            # Register data processors
            self._register_data_processors()
            
            logger.info(f"{self.name} service initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize {self.name} service: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    def _register_data_sources(self) -> None:
        """Register data sources"""
        self._data_sources = {
            "api": self._ingest_from_api,
            "file": self._ingest_from_file,
            "stream": self._ingest_from_stream
        }
        logger.info(f"Registered {len(self._data_sources)} data sources")
    
    def _register_data_processors(self) -> None:
        """Register data processors"""
        self._data_processors = {
            "normalize": self._normalize_data,
            "validate": self._validate_data,
            "transform": self._transform_data
        }
        logger.info(f"Registered {len(self._data_processors)} data processors")
    
    def warmup(self) -> bool:
        """
        Warm up the service
        
        Returns:
            True if warm-up was successful, False otherwise
        """
        logger.info(f"Warming up {self.name} service")
        
        try:
            # Test data sources
            for source_name, source_func in self._data_sources.items():
                test_data = source_func(test_mode=True)
                if test_data:
                    logger.info(f"Data source '{source_name}' is available")
                else:
                    logger.warning(f"Data source '{source_name}' is not available")
            
            # Test data processors
            test_data = {"value": 42, "timestamp": datetime.now().isoformat(), "source": "test"}
            for processor_name, processor_func in self._data_processors.items():
                processed_data = processor_func(test_data)
                if processed_data:
                    logger.info(f"Data processor '{processor_name}' is working")
                else:
                    logger.warning(f"Data processor '{processor_name}' is not working")
            
            logger.info(f"{self.name} service warmed up successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to warm up {self.name} service: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    def execute(self) -> Dict[str, Any]:
        """
        Execute the service
        
        Returns:
            Dictionary with execution results
        """
        logger.debug(f"Executing {self.name} service")
        
        try:
            # Ingest data from all sources
            ingested_data = []
            for source_name, source_func in self._data_sources.items():
                data = source_func()
                if data:
                    ingested_data.append(data)
                    self._data_stats["ingested"] += 1
            
            # Process ingested data
            processed_data = []
            for data in ingested_data:
                try:
                    # Apply all processors
                    for processor_name, processor_func in self._data_processors.items():
                        data = processor_func(data)
                    
                    processed_data.append(data)
                    self._data_stats["processed"] += 1
                except Exception as e:
                    logger.error(f"Failed to process data: {str(e)}")
                    self._data_stats["dropped"] += 1
            
            # Add processed data to queue
            for data in processed_data:
                self._data_queue.put(data)
            
            # Update stats
            self._data_stats["last_ingest_time"] = datetime.now().isoformat()
            
            # Update health metrics
            self.update_health_metrics(
                status="healthy",
                metrics={
                    "queue_size": self._data_queue.qsize(),
                    "data_stats": self._data_stats
                }
            )
            
            return {
                "ingested": len(ingested_data),
                "processed": len(processed_data),
                "queue_size": self._data_queue.qsize()
            }
        except Exception as e:
            logger.error(f"Failed to execute {self.name} service: {str(e)}")
            logger.error(traceback.format_exc())
            
            # Update health metrics
            self.update_health_metrics(
                status="error",
                metrics={
                    "last_error": str(e),
                    "queue_size": self._data_queue.qsize(),
                    "data_stats": self._data_stats
                }
            )
            
            raise
    
    def shutdown(self) -> bool:
        """
        Shut down the service
        
        Returns:
            True if shutdown was successful, False otherwise
        """
        logger.info(f"Shutting down {self.name} service")
        
        try:
            # Stop ingest thread if running
            self._running = False
            if self._ingest_thread and self._ingest_thread.is_alive():
                self._ingest_thread.join(timeout=5.0)
            
            # Clear data queue
            while not self._data_queue.empty():
                self._data_queue.get_nowait()
            
            logger.info(f"{self.name} service shut down successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to shut down {self.name} service: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    def _ingest_from_api(self, test_mode: bool = False) -> Optional[Dict[str, Any]]:
        """
        Ingest data from API
        
        Args:
            test_mode: Whether to run in test mode
            
        Returns:
            Ingested data, or None if no data is available
        """
        if test_mode:
            return {"source": "api", "test": True}
        
        # Simulate API data ingestion
        if random.random() < 0.8:  # 80% chance of data
            return {
                "source": "api",
                "timestamp": datetime.now().isoformat(),
                "value": random.uniform(0, 100),
                "id": str(uuid.uuid4())
            }
        return None
    
    def _ingest_from_file(self, test_mode: bool = False) -> Optional[Dict[str, Any]]:
        """
        Ingest data from file
        
        Args:
            test_mode: Whether to run in test mode
            
        Returns:
            Ingested data, or None if no data is available
        """
        if test_mode:
            return {"source": "file", "test": True}
        
        # Simulate file data ingestion
        if random.random() < 0.5:  # 50% chance of data
            return {
                "source": "file",
                "timestamp": datetime.now().isoformat(),
                "value": random.randint(0, 100),
                "filename": f"data_{random.randint(1, 100)}.json"
            }
        return None
    
    def _ingest_from_stream(self, test_mode: bool = False) -> Optional[Dict[str, Any]]:
        """
        Ingest data from stream
        
        Args:
            test_mode: Whether to run in test mode
            
        Returns:
            Ingested data, or None if no data is available
        """
        if test_mode:
            return {"source": "stream", "test": True}
        
        # Simulate stream data ingestion
        if random.random() < 0.3:  # 30% chance of data
            return {
                "source": "stream",
                "timestamp": datetime.now().isoformat(),
                "value": [random.random() for _ in range(5)],
                "stream_id": f"stream_{random.randint(1, 10)}"
            }
        return None
    
    def _normalize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize data
        
        Args:
            data: Data to normalize
            
        Returns:
            Normalized data
        """
        # Ensure all data has required fields
        normalized = data.copy()
        
        if "timestamp" not in normalized:
            normalized["timestamp"] = datetime.now().isoformat()
        
        if "id" not in normalized:
            normalized["id"] = str(uuid.uuid4())
        
        return normalized
    
    def _validate_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate data
        
        Args:
            data: Data to validate
            
        Returns:
            Validated data
            
        Raises:
            ValueError: If data is invalid
        """
        # Check required fields
        required_fields = ["source", "timestamp"]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")
        
        # Validate timestamp format
        try:
            datetime.fromisoformat(data["timestamp"])
        except ValueError:
            raise ValueError(f"Invalid timestamp format: {data['timestamp']}")
        
        return data
    
    def _transform_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform data
        
        Args:
            data: Data to transform
            
        Returns:
            Transformed data
        """
        # Add metadata
        transformed = data.copy()
        transformed["processed_by"] = self.name
        transformed["processed_at"] = datetime.now().isoformat()
        
        # Transform value if present
        if "value" in transformed:
            if isinstance(transformed["value"], (int, float)):
                transformed["value_squared"] = transformed["value"] ** 2
            elif isinstance(transformed["value"], list):
                transformed["value_sum"] = sum(transformed["value"])
        
        return transformed
    
    def start_continuous_ingest(self, interval: float = 1.0) -> None:
        """
        Start continuous data ingestion
        
        Args:
            interval: Ingestion interval in seconds
        """
        if self._running:
            logger.warning(f"{self.name} service is already running continuous ingestion")
            return
        
        self._running = True
        self._ingest_interval = interval
        
        self._ingest_thread = threading.Thread(
            target=self._continuous_ingest_loop,
            daemon=True
        )
        self._ingest_thread.start()
        
        logger.info(f"{self.name} service started continuous ingestion with interval {interval}s")
    
    def _continuous_ingest_loop(self) -> None:
        """Continuous ingestion loop"""
        while self._running:
            try:
                self.execute_once()
            except Exception as e:
                logger.error(f"Error in continuous ingestion: {str(e)}")
            
            time.sleep(self._ingest_interval)
    
    def stop_continuous_ingest(self) -> None:
        """Stop continuous data ingestion"""
        if not self._running:
            logger.warning(f"{self.name} service is not running continuous ingestion")
            return
        
        self._running = False
        if self._ingest_thread and self._ingest_thread.is_alive():
            self._ingest_thread.join(timeout=5.0)
        
        logger.info(f"{self.name} service stopped continuous ingestion")
    
    def get_data(self, timeout: float = 0.1) -> Optional[Dict[str, Any]]:
        """
        Get data from the queue
        
        Args:
            timeout: Timeout in seconds
            
        Returns:
            Data from the queue, or None if queue is empty
        """
        try:
            return self._data_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def get_queue_size(self) -> int:
        """
        Get queue size
        
        Returns:
            Queue size
        """
        return self._data_queue.qsize()
    
    def get_data_stats(self) -> Dict[str, Any]:
        """
        Get data statistics
        
        Returns:
            Dictionary with data statistics
        """
        return self._data_stats.copy()

class TelemetryService(BaseService):
    """
    Telemetry Service
    
    This service is responsible for collecting telemetry data
    from other services and sending it to external systems.
    """
    
    def __init__(self, name: str = "telemetry", dependencies: Dict[str, ServiceDependencyType] = None, metadata: Dict[str, Any] = None):
        """
        Initialize telemetry service
        
        Args:
            name: Service name
            dependencies: Dictionary of service dependencies
            metadata: Additional service metadata
        """
        # Set default dependencies
        dependencies = dependencies or {}
        dependencies.update({
            "data_ingest": ServiceDependencyType.REQUIRED
        })
        
        # Set default metadata
        metadata = metadata or {}
        metadata.update({
            "description": "Telemetry Service",
            "telemetry_targets": ["console", "file", "remote"],
            "version": "1.0.0"
        })
        
        super().__init__(name, dependencies, metadata)
        
        # Initialize service-specific attributes
        self._telemetry_data = []
        self._telemetry_targets = {}
        self._telemetry_stats = {
            "collected": 0,
            "sent": 0,
            "failed": 0,
            "last_send_time": None
        }
        self._running = False
        self._telemetry_thread = None
        self._telemetry_interval = 5.0  # seconds
        self._max_buffer_size = 1000
    
    def init(self) -> bool:
        """
        Initialize the service
        
        Returns:
            True if initialization was successful, False otherwise
        """
        logger.info(f"Initializing {self.name} service")
        
        try:
            # Register telemetry targets
            self._register_telemetry_targets()
            
            logger.info(f"{self.name} service initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize {self.name} service: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    def _register_telemetry_targets(self) -> None:
        """Register telemetry targets"""
        self._telemetry_targets = {
            "console": self._send_to_console,
            "file": self._send_to_file,
            "remote": self._send_to_remote
        }
        logger.info(f"Registered {len(self._telemetry_targets)} telemetry targets")
    
    def warmup(self) -> bool:
        """
        Warm up the service
        
        Returns:
            True if warm-up was successful, False otherwise
        """
        logger.info(f"Warming up {self.name} service")
        
        try:
            # Test telemetry targets
            test_data = {
                "service": "test",
                "timestamp": datetime.now().isoformat(),
                "metrics": {"test": True}
            }
            
            for target_name, target_func in self._telemetry_targets.items():
                success = target_func(test_data, test_mode=True)
                if success:
                    logger.info(f"Telemetry target '{target_name}' is available")
                else:
                    logger.warning(f"Telemetry target '{target_name}' is not available")
            
            # Test data ingest service connection
            try:
                data_ingest = self.get_dependency_service("data_ingest")
                logger.info(f"Connected to data ingest service: {data_ingest.name}")
            except Exception as e:
                logger.warning(f"Failed to connect to data ingest service: {str(e)}")
            
            logger.info(f"{self.name} service warmed up successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to warm up {self.name} service: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    def execute(self) -> Dict[str, Any]:
        """
        Execute the service
        
        Returns:
            Dictionary with execution results
        """
        logger.debug(f"Executing {self.name} service")
        
        try:
            # Collect telemetry data from data ingest service
            collected_data = self._collect_telemetry_data()
            
            # Send telemetry data to all targets
            sent_count = 0
            failed_count = 0
            
            for data in collected_data:
                for target_name, target_func in self._telemetry_targets.items():
                    try:
                        success = target_func(data)
                        if success:
                            sent_count += 1
                        else:
                            failed_count += 1
                    except Exception as e:
                        logger.error(f"Failed to send telemetry to {target_name}: {str(e)}")
                        failed_count += 1
            
            # Update stats
            self._telemetry_stats["collected"] += len(collected_data)
            self._telemetry_stats["sent"] += sent_count
            self._telemetry_stats["failed"] += failed_count
            self._telemetry_stats["last_send_time"] = datetime.now().isoformat()
            
            # Update health metrics
            self.update_health_metrics(
                status="healthy",
                metrics={
                    "buffer_size": len(self._telemetry_data),
                    "telemetry_stats": self._telemetry_stats
                }
            )
            
            return {
                "collected": len(collected_data),
                "sent": sent_count,
                "failed": failed_count,
                "buffer_size": len(self._telemetry_data)
            }
        except Exception as e:
            logger.error(f"Failed to execute {self.name} service: {str(e)}")
            logger.error(traceback.format_exc())
            
            # Update health metrics
            self.update_health_metrics(
                status="error",
                metrics={
                    "last_error": str(e),
                    "buffer_size": len(self._telemetry_data),
                    "telemetry_stats": self._telemetry_stats
                }
            )
            
            raise
    
    def shutdown(self) -> bool:
        """
        Shut down the service
        
        Returns:
            True if shutdown was successful, False otherwise
        """
        logger.info(f"Shutting down {self.name} service")
        
        try:
            # Stop telemetry thread if running
            self._running = False
            if self._telemetry_thread and self._telemetry_thread.is_alive():
                self._telemetry_thread.join(timeout=5.0)
            
            # Send remaining telemetry data
            if self._telemetry_data:
                logger.info(f"Sending {len(self._telemetry_data)} remaining telemetry data points")
                for data in self._telemetry_data:
                    for target_name, target_func in self._telemetry_targets.items():
                        try:
                            target_func(data)
                        except Exception as e:
                            logger.error(f"Failed to send telemetry to {target_name}: {str(e)}")
            
            # Clear telemetry data
            self._telemetry_data = []
            
            logger.info(f"{self.name} service shut down successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to shut down {self.name} service: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    def _collect_telemetry_data(self) -> List[Dict[str, Any]]:
        """
        Collect telemetry data from data ingest service
        
        Returns:
            List of telemetry data points
        """
        collected_data = []
        
        try:
            # Get data ingest service
            data_ingest = self.get_dependency_service("data_ingest")
            
            # Get data from data ingest service
            while True:
                data = data_ingest.get_data(timeout=0.1)
                if data is None:
                    break
                
                # Add telemetry metadata
                data["telemetry_timestamp"] = datetime.now().isoformat()
                data["telemetry_id"] = str(uuid.uuid4())
                
                # Add to collected data
                collected_data.append(data)
                
                # Add to telemetry buffer
                self._telemetry_data.append(data)
                
                # Limit buffer size
                if len(self._telemetry_data) > self._max_buffer_size:
                    self._telemetry_data = self._telemetry_data[-self._max_buffer_size:]
        except Exception as e:
            logger.error(f"Failed to collect telemetry data: {str(e)}")
        
        return collected_data
    
    def _send_to_console(self, data: Dict[str, Any], test_mode: bool = False) -> bool:
        """
        Send telemetry data to console
        
        Args:
            data: Telemetry data
            test_mode: Whether to run in test mode
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if test_mode:
                logger.debug(f"Test telemetry data: {data}")
            else:
                logger.debug(f"Telemetry data: {json.dumps(data)}")
            return True
        except Exception as e:
            logger.error(f"Failed to send telemetry to console: {str(e)}")
            return False
    
    def _send_to_file(self, data: Dict[str, Any], test_mode: bool = False) -> bool:
        """
        Send telemetry data to file
        
        Args:
            data: Telemetry data
            test_mode: Whether to run in test mode
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if test_mode:
                return True
            
            # Simulate file write
            if random.random() < 0.9:  # 90% success rate
                return True
            else:
                logger.warning("Simulated file write failure")
                return False
        except Exception as e:
            logger.error(f"Failed to send telemetry to file: {str(e)}")
            return False
    
    def _send_to_remote(self, data: Dict[str, Any], test_mode: bool = False) -> bool:
        """
        Send telemetry data to remote system
        
        Args:
            data: Telemetry data
            test_mode: Whether to run in test mode
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if test_mode:
                return True
            
            # Simulate remote send
            if random.random() < 0.8:  # 80% success rate
                return True
            else:
                logger.warning("Simulated remote send failure")
                return False
        except Exception as e:
            logger.error(f"Failed to send telemetry to remote: {str(e)}")
            return False
    
    def start_continuous_telemetry(self, interval: float = 5.0) -> None:
        """
        Start continuous telemetry collection and sending
        
        Args:
            interval: Telemetry interval in seconds
        """
        if self._running:
            logger.warning(f"{self.name} service is already running continuous telemetry")
            return
        
        self._running = True
        self._telemetry_interval = interval
        
        self._telemetry_thread = threading.Thread(
            target=self._continuous_telemetry_loop,
            daemon=True
        )
        self._telemetry_thread.start()
        
        logger.info(f"{self.name} service started continuous telemetry with interval {interval}s")
    
    def _continuous_telemetry_loop(self) -> None:
        """Continuous telemetry loop"""
        while self._running:
            try:
                self.execute_once()
            except Exception as e:
                logger.error(f"Error in continuous telemetry: {str(e)}")
            
            time.sleep(self._telemetry_interval)
    
    def stop_continuous_telemetry(self) -> None:
        """Stop continuous telemetry collection and sending"""
        if not self._running:
            logger.warning(f"{self.name} service is not running continuous telemetry")
            return
        
        self._running = False
        if self._telemetry_thread and self._telemetry_thread.is_alive():
            self._telemetry_thread.join(timeout=5.0)
        
        logger.info(f"{self.name} service stopped continuous telemetry")
    
    def get_telemetry_data(self) -> List[Dict[str, Any]]:
        """
        Get telemetry data
        
        Returns:
            List of telemetry data points
        """
        return self._telemetry_data.copy()
    
    def get_telemetry_stats(self) -> Dict[str, Any]:
        """
        Get telemetry statistics
        
        Returns:
            Dictionary with telemetry statistics
        """
        return self._telemetry_stats.copy()

class ControlLoopService(BaseService):
    """
    Control Loop Service
    
    This service is responsible for implementing a control loop
    that processes telemetry data and takes actions based on it.
    """
    
    def __init__(self, name: str = "control_loop", dependencies: Dict[str, ServiceDependencyType] = None, metadata: Dict[str, Any] = None):
        """
        Initialize control loop service
        
        Args:
            name: Service name
            dependencies: Dictionary of service dependencies
            metadata: Additional service metadata
        """
        # Set default dependencies
        dependencies = dependencies or {}
        dependencies.update({
            "telemetry": ServiceDependencyType.REQUIRED,
            "data_ingest": ServiceDependencyType.RUNTIME
        })
        
        # Set default metadata
        metadata = metadata or {}
        metadata.update({
            "description": "Control Loop Service",
            "control_actions": ["alert", "adjust", "restart"],
            "version": "1.0.0"
        })
        
        super().__init__(name, dependencies, metadata)
        
        # Initialize service-specific attributes
        self._control_actions = {}
        self._control_rules = []
        self._control_stats = {
            "evaluations": 0,
            "actions_triggered": 0,
            "last_evaluation_time": None
        }
        self._running = False
        self._control_thread = None
        self._control_interval = 10.0  # seconds
        self._last_telemetry_data = []
    
    def init(self) -> bool:
        """
        Initialize the service
        
        Returns:
            True if initialization was successful, False otherwise
        """
        logger.info(f"Initializing {self.name} service")
        
        try:
            # Register control actions
            self._register_control_actions()
            
            # Register control rules
            self._register_control_rules()
            
            logger.info(f"{self.name} service initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize {self.name} service: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    def _register_control_actions(self) -> None:
        """Register control actions"""
        self._control_actions = {
            "alert": self._action_alert,
            "adjust": self._action_adjust,
            "restart": self._action_restart
        }
        logger.info(f"Registered {len(self._control_actions)} control actions")
    
    def _register_control_rules(self) -> None:
        """Register control rules"""
        self._control_rules = [
            {
                "name": "high_value_alert",
                "condition": lambda data: data.get("value", 0) > 80,
                "action": "alert",
                "params": {"level": "warning", "message": "High value detected"}
            },
            {
                "name": "very_high_value_alert",
                "condition": lambda data: data.get("value", 0) > 95,
                "action": "alert",
                "params": {"level": "critical", "message": "Very high value detected"}
            },
            {
                "name": "low_value_adjust",
                "condition": lambda data: data.get("value", 100) < 20,
                "action": "adjust",
                "params": {"adjustment": 10}
            },
            {
                "name": "error_restart",
                "condition": lambda data: "error" in data,
                "action": "restart",
                "params": {"service": "data_ingest"}
            }
        ]
        logger.info(f"Registered {len(self._control_rules)} control rules")
    
    def warmup(self) -> bool:
        """
        Warm up the service
        
        Returns:
            True if warm-up was successful, False otherwise
        """
        logger.info(f"Warming up {self.name} service")
        
        try:
            # Test control actions
            test_data = {"test": True}
            for action_name, action_func in self._control_actions.items():
                success = action_func(test_data, test_mode=True)
                if success:
                    logger.info(f"Control action '{action_name}' is available")
                else:
                    logger.warning(f"Control action '{action_name}' is not available")
            
            # Test telemetry service connection
            try:
                telemetry = self.get_dependency_service("telemetry")
                logger.info(f"Connected to telemetry service: {telemetry.name}")
            except Exception as e:
                logger.warning(f"Failed to connect to telemetry service: {str(e)}")
            
            # Test data ingest service connection
            try:
                data_ingest = self.get_dependency_service("data_ingest")
                logger.info(f"Connected to data ingest service: {data_ingest.name}")
            except Exception as e:
                logger.warning(f"Failed to connect to data ingest service: {str(e)}")
            
            logger.info(f"{self.name} service warmed up successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to warm up {self.name} service: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    def execute(self) -> Dict[str, Any]:
        """
        Execute the service
        
        Returns:
            Dictionary with execution results
        """
        logger.debug(f"Executing {self.name} service")
        
        try:
            # Get telemetry data
            telemetry_data = self._get_telemetry_data()
            
            # Evaluate control rules
            actions_triggered = 0
            for data in telemetry_data:
                for rule in self._control_rules:
                    try:
                        # Check if rule condition is met
                        if rule["condition"](data):
                            # Execute action
                            action_name = rule["action"]
                            action_func = self._control_actions.get(action_name)
                            
                            if action_func:
                                params = rule["params"].copy()
                                params["rule"] = rule["name"]
                                params["data"] = data
                                
                                success = action_func(params)
                                if success:
                                    actions_triggered += 1
                                    logger.info(f"Rule '{rule['name']}' triggered action '{action_name}'")
                    except Exception as e:
                        logger.error(f"Failed to evaluate rule '{rule['name']}': {str(e)}")
            
            # Update stats
            self._control_stats["evaluations"] += len(telemetry_data) * len(self._control_rules)
            self._control_stats["actions_triggered"] += actions_triggered
            self._control_stats["last_evaluation_time"] = datetime.now().isoformat()
            
            # Update health metrics
            self.update_health_metrics(
                status="healthy",
                metrics={
                    "telemetry_count": len(telemetry_data),
                    "control_stats": self._control_stats
                }
            )
            
            return {
                "telemetry_count": len(telemetry_data),
                "rules_evaluated": len(telemetry_data) * len(self._control_rules),
                "actions_triggered": actions_triggered
            }
        except Exception as e:
            logger.error(f"Failed to execute {self.name} service: {str(e)}")
            logger.error(traceback.format_exc())
            
            # Update health metrics
            self.update_health_metrics(
                status="error",
                metrics={
                    "last_error": str(e),
                    "control_stats": self._control_stats
                }
            )
            
            raise
    
    def shutdown(self) -> bool:
        """
        Shut down the service
        
        Returns:
            True if shutdown was successful, False otherwise
        """
        logger.info(f"Shutting down {self.name} service")
        
        try:
            # Stop control thread if running
            self._running = False
            if self._control_thread and self._control_thread.is_alive():
                self._control_thread.join(timeout=5.0)
            
            logger.info(f"{self.name} service shut down successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to shut down {self.name} service: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    def _get_telemetry_data(self) -> List[Dict[str, Any]]:
        """
        Get telemetry data from telemetry service
        
        Returns:
            List of telemetry data points
        """
        try:
            # Get telemetry service
            telemetry = self.get_dependency_service("telemetry")
            
            # Get telemetry data
            telemetry_data = telemetry.get_telemetry_data()
            
            # Filter out data we've already processed
            new_data = []
            for data in telemetry_data:
                if data not in self._last_telemetry_data:
                    new_data.append(data)
            
            # Update last telemetry data
            self._last_telemetry_data = telemetry_data
            
            return new_data
        except Exception as e:
            logger.error(f"Failed to get telemetry data: {str(e)}")
            return []
    
    def _action_alert(self, params: Dict[str, Any], test_mode: bool = False) -> bool:
        """
        Alert action
        
        Args:
            params: Action parameters
            test_mode: Whether to run in test mode
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if test_mode:
                return True
            
            level = params.get("level", "info")
            message = params.get("message", "Alert triggered")
            data = params.get("data", {})
            
            logger.log(
                logging.getLevelName(level.upper()),
                f"ALERT: {message} - {json.dumps(data)}"
            )
            
            return True
        except Exception as e:
            logger.error(f"Failed to execute alert action: {str(e)}")
            return False
    
    def _action_adjust(self, params: Dict[str, Any], test_mode: bool = False) -> bool:
        """
        Adjust action
        
        Args:
            params: Action parameters
            test_mode: Whether to run in test mode
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if test_mode:
                return True
            
            adjustment = params.get("adjustment", 0)
            data = params.get("data", {})
            
            logger.info(f"ADJUST: Applying adjustment of {adjustment} to {json.dumps(data)}")
            
            # Simulate adjustment
            if random.random() < 0.9:  # 90% success rate
                return True
            else:
                logger.warning("Simulated adjustment failure")
                return False
        except Exception as e:
            logger.error(f"Failed to execute adjust action: {str(e)}")
            return False
    
    def _action_restart(self, params: Dict[str, Any], test_mode: bool = False) -> bool:
        """
        Restart action
        
        Args:
            params: Action parameters
            test_mode: Whether to run in test mode
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if test_mode:
                return True
            
            service_name = params.get("service")
            if not service_name:
                logger.error("No service specified for restart action")
                return False
            
            logger.info(f"RESTART: Attempting to restart service '{service_name}'")
            
            try:
                # Get service
                service = self.get_dependency_service(service_name)
                
                # Reload service
                success = service.reload()
                
                if success:
                    logger.info(f"Successfully restarted service '{service_name}'")
                    return True
                else:
                    logger.error(f"Failed to restart service '{service_name}'")
                    return False
            except Exception as e:
                logger.error(f"Failed to restart service '{service_name}': {str(e)}")
                return False
        except Exception as e:
            logger.error(f"Failed to execute restart action: {str(e)}")
            return False
    
    def start_continuous_control(self, interval: float = 10.0) -> None:
        """
        Start continuous control loop
        
        Args:
            interval: Control interval in seconds
        """
        if self._running:
            logger.warning(f"{self.name} service is already running continuous control")
            return
        
        self._running = True
        self._control_interval = interval
        
        self._control_thread = threading.Thread(
            target=self._continuous_control_loop,
            daemon=True
        )
        self._control_thread.start()
        
        logger.info(f"{self.name} service started continuous control with interval {interval}s")
    
    def _continuous_control_loop(self) -> None:
        """Continuous control loop"""
        while self._running:
            try:
                self.execute_once()
            except Exception as e:
                logger.error(f"Error in continuous control: {str(e)}")
            
            time.sleep(self._control_interval)
    
    def stop_continuous_control(self) -> None:
        """Stop continuous control loop"""
        if not self._running:
            logger.warning(f"{self.name} service is not running continuous control")
            return
        
        self._running = False
        if self._control_thread and self._control_thread.is_alive():
            self._control_thread.join(timeout=5.0)
        
        logger.info(f"{self.name} service stopped continuous control")
    
    def get_control_stats(self) -> Dict[str, Any]:
        """
        Get control statistics
        
        Returns:
            Dictionary with control statistics
        """
        return self._control_stats.copy()
    
    def get_control_rules(self) -> List[Dict[str, Any]]:
        """
        Get control rules
        
        Returns:
            List of control rules
        """
        return [
            {
                "name": rule["name"],
                "action": rule["action"],
                "params": {k: v for k, v in rule["params"].items() if k != "condition"}
            }
            for rule in self._control_rules
        ]

# Example usage
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s|%(levelname)s|%(name)s|%(message)s')
    
    # Create registry
    registry = get_registry()
    
    # Create services
    data_ingest = DataIngestService()
    telemetry = TelemetryService()
    control_loop = ControlLoopService()
    
    # Initialize services
    data_ingest.initialize()
    data_ingest.warm_up()
    
    telemetry.initialize()
    telemetry.warm_up()
    
    control_loop.initialize()
    control_loop.warm_up()
    
    # Start continuous execution
    data_ingest.start_continuous_ingest(interval=1.0)
    telemetry.start_continuous_telemetry(interval=2.0)
    control_loop.start_continuous_control(interval=5.0)
    
    # Run for a while
    try:
        for _ in range(10):
            time.sleep(1)
            print(f"Data ingest queue size: {data_ingest.get_queue_size()}")
            print(f"Telemetry data count: {len(telemetry.get_telemetry_data())}")
            print(f"Control stats: {control_loop.get_control_stats()}")
            print("-" * 50)
    finally:
        # Stop and shutdown
        control_loop.stop_continuous_control()
        telemetry.stop_continuous_telemetry()
        data_ingest.stop_continuous_ingest()
        
        control_loop.stop_and_shutdown()
        telemetry.stop_and_shutdown()
        data_ingest.stop_and_shutdown()
