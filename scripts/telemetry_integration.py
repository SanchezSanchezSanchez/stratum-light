#!/usr/bin/env python3
# Telemetry Integration for STRATUM_LIGHT

import os
import sys
import json
import logging
import time
import yaml
import socket
import threading
from typing import Dict, Any, Optional, List, Callable
from functools import wraps
from datetime import datetime
from contextlib import contextmanager

# Set up logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s|%(levelname)s|%(message)s')
logger = logging.getLogger(__name__)

class TelemetryManager:
    """Manages telemetry integration for STRATUM_LIGHT"""
    
    def __init__(self, config_path: str = "monitoring/monitoring.yml"):
        """
        Initialize the telemetry manager
        
        Args:
            config_path: Path to the monitoring configuration file
        """
        self.config_path = config_path
        self.config = self._load_config()
        self.environment = os.getenv("ENVIRONMENT", "development")
        self.service_name = "stratum_light"
        self.instance_id = socket.gethostname()
        self.deployment_id = os.getenv("CI_COMMIT_SHA", "local")
        
        # Initialize telemetry components
        self.metrics_enabled = self.config.get("telemetry", {}).get("metrics", {}).get("enabled", True)
        self.tracing_enabled = self.config.get("telemetry", {}).get("tracing", {}).get("enabled", True)
        self.logging_enabled = self.config.get("telemetry", {}).get("logging", {}).get("enabled", True)
        
        # Set up prometheus client if metrics are enabled
        if self.metrics_enabled:
            try:
                from prometheus_client import Counter, Histogram, Gauge, multiprocess, CollectorRegistry
                self.registry = CollectorRegistry()
                self.request_counter = Counter(
                    'stratum_http_requests_total',
                    'Total number of HTTP requests',
                    ['method', 'endpoint', 'status', 'environment'],
                    registry=self.registry
                )
                self.request_latency = Histogram(
                    'stratum_http_request_duration_seconds',
                    'HTTP request latency in seconds',
                    ['method', 'endpoint', 'environment'],
                    registry=self.registry
                )
                self.active_requests = Gauge(
                    'stratum_http_requests_active',
                    'Number of active HTTP requests',
                    ['environment'],
                    registry=self.registry
                )
                self.vulnerability_counter = Counter(
                    'stratum_vulnerability_reports_total',
                    'Total number of vulnerability reports',
                    ['model', 'severity', 'environment'],
                    registry=self.registry
                )
                logger.info("Prometheus metrics initialized")
            except ImportError:
                logger.warning("prometheus_client not installed, metrics disabled")
                self.metrics_enabled = False
        
        # Set up OpenTelemetry if tracing is enabled
        if self.tracing_enabled:
            try:
                from opentelemetry import trace
                from opentelemetry.sdk.trace import TracerProvider
                from opentelemetry.sdk.trace.export import BatchSpanProcessor
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
                from opentelemetry.sdk.resources import Resource
                
                resource = Resource.create({
                    "service.name": self.service_name,
                    "service.version": self.config.get("version", "v1.0.0"),
                    "deployment.environment": self.environment,
                    "deployment.id": self.deployment_id
                })
                
                trace.set_tracer_provider(TracerProvider(resource=resource))
                
                # Configure exporter
                endpoint = self.config.get("telemetry", {}).get("tracing", {}).get("endpoint", "http://otel-collector:4317")
                otlp_exporter = OTLPSpanExporter(endpoint=endpoint)
                span_processor = BatchSpanProcessor(otlp_exporter)
                trace.get_tracer_provider().add_span_processor(span_processor)
                
                self.tracer = trace.get_tracer(__name__)
                logger.info(f"OpenTelemetry tracing initialized with endpoint {endpoint}")
            except ImportError:
                logger.warning("opentelemetry packages not installed, tracing disabled")
                self.tracing_enabled = False
        
        # Set up structured logging if enabled
        if self.logging_enabled:
            log_level = self.config.get("telemetry", {}).get("logging", {}).get("level", "INFO")
            log_format = self.config.get("telemetry", {}).get("logging", {}).get("format", "json")
            
            # Configure root logger
            numeric_level = getattr(logging, log_level.upper(), None)
            if not isinstance(numeric_level, int):
                numeric_level = logging.INFO
            
            # Set up JSON formatter if needed
            if log_format.lower() == "json":
                try:
                    import pythonjsonlogger.jsonlogger
                    
                    # Create JSON formatter with standard fields
                    formatter = pythonjsonlogger.jsonlogger.JsonFormatter(
                        '%(asctime)s %(levelname)s %(name)s %(message)s',
                        rename_fields={
                            'levelname': 'level',
                            'asctime': 'timestamp',
                            'name': 'logger'
                        },
                        static_fields={
                            'service': self.service_name,
                            'environment': self.environment,
                            'instance': self.instance_id,
                            'deployment': self.deployment_id
                        }
                    )
                    
                    # Apply formatter to all handlers
                    for handler in logging.root.handlers:
                        handler.setFormatter(formatter)
                    
                    logger.info("JSON logging configured")
                except ImportError:
                    logger.warning("python-json-logger not installed, using default format")
            
            # Set log level
            logging.root.setLevel(numeric_level)
            logger.info(f"Logging configured at {log_level} level")
    
    def _load_config(self) -> Dict:
        """Load monitoring configuration from YAML file"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    # Parse YAML but focus on the telemetry section
                    config = yaml.safe_load(f)
                    
                    # Extract telemetry config from service definition if needed
                    if "services" in config:
                        for service in config["services"].values():
                            if service.get("container_name") == "stratum_api":
                                # Extract environment variables
                                env_vars = service.get("environment", [])
                                telemetry_config = {}
                                
                                # Process environment variables
                                for env in env_vars:
                                    if isinstance(env, str) and "=" in env:
                                        key, value = env.split("=", 1)
                                        if key.startswith("TELEMETRY_"):
                                            clean_key = key[10:].lower()
                                            telemetry_config[clean_key] = value
                                
                                return {
                                    "version": service.get("labels", {}).get("version", "v1.0.0"),
                                    "telemetry": telemetry_config
                                }
                    
                    return config
            else:
                # Create default config
                default_config = {
                    "version": "v1.0.0",
                    "telemetry": {
                        "metrics": {
                            "enabled": True,
                            "provider": "prometheus",
                            "port": 9090
                        },
                        "tracing": {
                            "enabled": True,
                            "provider": "opentelemetry",
                            "exporter": "otlp",
                            "endpoint": "http://localhost:4317",
                            "sampling_ratio": 1.0
                        },
                        "logging": {
                            "enabled": True,
                            "level": "INFO",
                            "format": "json"
                        }
                    }
                }
                
                # Ensure directory exists
                os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
                
                # Write default config
                with open(self.config_path, 'w') as f:
                    yaml.dump(default_config, f)
                
                logger.info(f"Created default monitoring configuration at {self.config_path}")
                return default_config
        except Exception as e:
            logger.error(f"Failed to load monitoring configuration: {str(e)}")
            return {
                "version": "v1.0.0",
                "telemetry": {
                    "metrics": {"enabled": False},
                    "tracing": {"enabled": False},
                    "logging": {"enabled": True, "level": "INFO"}
                }
            }
    
    @contextmanager
    def trace_span(self, name: str, attributes: Dict = None):
        """
        Context manager for creating a trace span
        
        Args:
            name: Name of the span
            attributes: Span attributes
        """
        if not self.tracing_enabled:
            yield
            return
        
        # Merge with default attributes
        all_attributes = {
            "service.name": self.service_name,
            "environment": self.environment,
            "deployment.id": self.deployment_id
        }
        if attributes:
            all_attributes.update(attributes)
        
        # Create and activate span
        with self.tracer.start_as_current_span(name, attributes=all_attributes) as span:
            yield span
    
    def trace_function(self, name: str = None, attributes: Dict = None):
        """
        Decorator for tracing a function
        
        Args:
            name: Name of the span (defaults to function name)
            attributes: Span attributes
        """
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                span_name = name or func.__name__
                with self.trace_span(span_name, attributes):
                    return func(*args, **kwargs)
            return wrapper
        return decorator
    
    def record_request(self, method: str, endpoint: str, status_code: int, duration: float):
        """
        Record an HTTP request metric
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            status_code: HTTP status code
            duration: Request duration in seconds
        """
        if not self.metrics_enabled:
            return
        
        # Increment request counter
        self.request_counter.labels(
            method=method,
            endpoint=endpoint,
            status=status_code,
            environment=self.environment
        ).inc()
        
        # Record request latency
        self.request_latency.labels(
            method=method,
            endpoint=endpoint,
            environment=self.environment
        ).observe(duration)
    
    def record_vulnerability(self, model: str, severity: str):
        """
        Record a vulnerability report metric
        
        Args:
            model: Model name
            severity: Vulnerability severity
        """
        if not self.metrics_enabled:
            return
        
        # Increment vulnerability counter
        self.vulnerability_counter.labels(
            model=model,
            severity=severity,
            environment=self.environment
        ).inc()
    
    @contextmanager
    def track_active_requests(self):
        """Context manager for tracking active requests"""
        if not self.metrics_enabled:
            yield
            return
        
        # Increment active requests
        self.active_requests.labels(environment=self.environment).inc()
        try:
            yield
        finally:
            # Decrement active requests
            self.active_requests.labels(environment=self.environment).dec()
    
    def log_with_context(self, level: str, message: str, **kwargs):
        """
        Log a message with context
        
        Args:
            level: Log level
            message: Log message
            **kwargs: Additional context
        """
        if not self.logging_enabled:
            return
        
        # Add standard context
        context = {
            "service": self.service_name,
            "environment": self.environment,
            "instance": self.instance_id,
            "timestamp": datetime.now().isoformat()
        }
        
        # Add CI context if available
        for env_var in ["CI_COMMIT_SHA", "CI_PIPELINE_ID", "CI_JOB_ID"]:
            value = os.getenv(env_var)
            if value:
                context[env_var.lower()] = value
        
        # Add custom context
        context.update(kwargs)
        
        # Log with context
        log_func = getattr(logger, level.lower(), logger.info)
        if hasattr(log_func, "__self__") and hasattr(log_func.__self__, "makeRecord"):
            # Use extra for standard logging
            log_func(message, extra=context)
        else:
            # Fallback to simple logging with context in message
            log_func(f"{message} | {json.dumps(context)}")

# Create singleton instance
telemetry = TelemetryManager()

# FastAPI middleware for request telemetry
class TelemetryMiddleware:
    """FastAPI middleware for request telemetry"""
    
    def __init__(self, app):
        """
        Initialize the telemetry middleware
        
        Args:
            app: FastAPI app
        """
        self.app = app
        self.telemetry = telemetry
        logger.info("Telemetry middleware initialized")
    
    async def __call__(self, scope, receive, send):
        """Process a request/response cycle with telemetry"""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Extract request details
        method = scope.get("method", "UNKNOWN")
        path = scope.get("path", "/")
        
        # Record start time
        start_time = time.time()
        status_code = 500  # Default in case of error
        
        # Create trace context
        with self.telemetry.trace_span(
            f"{method} {path}",
            {"http.method": method, "http.path": path}
        ) as span:
            # Track active requests
            with self.telemetry.track_active_requests():
                # Create modified send function to capture status code
                async def send_with_metrics(message):
                    nonlocal status_code
                    if message["type"] == "http.response.start":
                        status_code = message.get("status", 500)
                    await send(message)

                await self.app(scope, receive, send_with_metrics)

                duration = time.time() - start_time
                self.telemetry.record_request(method, path, status_code, duration)

        return


def record_event(event_type: str, data: Dict[str, Any]) -> None:
    """Convenience wrapper to log a telemetry event."""
    telemetry.log_with_context("info", f"event:{event_type}", **data)
