#!/usr/bin/env python3
"""
STRATUM_LIGHT API Schema Definitions

This module provides Pydantic models for API request and response schemas,
ensuring proper validation and documentation of the API interface.
"""

import os
import sys
import logging
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, validator

# Set up logger
logger = logging.getLogger(__name__)

# Base response models
class BaseResponse(BaseModel):
    """Base model for all API responses."""
    success: bool = Field(..., description="Whether the request was successful")
    timestamp: str = Field(..., description="ISO-formatted timestamp of the response")

    @validator("timestamp")
    def _validate_timestamp(cls, v: str) -> str:  # type: ignore
        return validate_iso_timestamp(v)

class ErrorResponse(BaseResponse):
    """Error response model."""
    success: bool = Field(False, description="Always false for error responses")
    error: str = Field(..., description="Error message")
    error_type: str = Field(..., description="Type of error")
    request_id: Optional[str] = Field(None, description="Request ID for tracing")

class SuccessResponse(BaseResponse):
    """Simple success response model."""
    success: bool = Field(True, description="Always true for success responses")
    message: str = Field(..., description="Success message")

# System info models
class SystemInfoResponse(BaseResponse):
    """System information response model."""
    system_name: str = Field(..., description="Name of the system")
    version: str = Field(..., description="System version")
    environment: str = Field(..., description="Environment tier (development, staging, production)")
    uptime: float = Field(..., description="System uptime in seconds")
    start_time: str = Field(..., description="ISO-formatted system start time")
    services_count: int = Field(..., description="Total number of services")
    services_ready: int = Field(..., description="Number of ready services")

# Runtime state models
class RuntimeStateResponse(BaseResponse):
    """Runtime state response model."""
    state: Dict[str, Any] = Field(..., description="Runtime state dictionary")

# Service models
class ServiceState(str, Enum):
    """Service state enumeration."""
    UNINITIALIZED = "UNINITIALIZED"
    INITIALIZING = "INITIALIZING"
    INITIALIZED = "INITIALIZED"
    WARMING_UP = "WARMING_UP"
    READY = "READY"
    EXECUTING = "EXECUTING"
    ERROR = "ERROR"
    SHUTDOWN = "SHUTDOWN"

class ServiceSummary(BaseModel):
    """Service summary model."""
    name: str = Field(..., description="Service name")
    state: str = Field(..., description="Service state")
    type: str = Field(..., description="Service type/class")
    dependencies: List[str] = Field(default_factory=list, description="Service dependencies")
    health: str = Field(..., description="Service health status")

class ServiceDetail(ServiceSummary):
    """Service detail model."""
    dependents: List[str] = Field(default_factory=list, description="Services that depend on this service")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Service metrics")
    config: Dict[str, Any] = Field(default_factory=dict, description="Service configuration")
    lifecycle: Dict[str, Any] = Field(default_factory=dict, description="Service lifecycle information")

class ServiceListResponse(BaseResponse):
    """Service list response model."""
    services: List[ServiceSummary] = Field(..., description="List of services")
    count: int = Field(..., description="Number of services")

class ServiceDetailResponse(BaseResponse):
    """Service detail response model."""
    service: ServiceDetail = Field(..., description="Service details")

class ServiceControlRequest(BaseModel):
    """Service control request model."""
    action: str = Field(..., description="Action to perform (initialize, warmup, execute, shutdown, restart)")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Action parameters")

class ServiceControlResponse(BaseResponse):
    """Service control response model."""
    service: str = Field(..., description="Service name")
    action: str = Field(..., description="Action performed")
    result: Any = Field(..., description="Action result")

# Control models
class ControlActionRequest(BaseModel):
    """Control action request model."""
    action: str = Field(..., description="Action to perform")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Action parameters")

class ControlActionResponse(BaseResponse):
    """Control action response model."""
    action: str = Field(..., description="Action performed")
    result: Any = Field(..., description="Action result")

# Metrics models
class MetricsResponse(BaseResponse):
    """Metrics response model."""
    metrics: Dict[str, Any] = Field(..., description="Metrics data")
    service: Optional[str] = Field(None, description="Service name (if service-specific)")

# Logs models
class LogEntry(BaseModel):
    """Log entry model."""
    timestamp: str = Field(..., description="ISO-formatted timestamp")
    level: str = Field(..., description="Log level")
    logger: str = Field(..., description="Logger name")
    message: str = Field(..., description="Log message")
    service: Optional[str] = Field(None, description="Service name")
    trace_id: Optional[str] = Field(None, description="Trace ID")
    exception: Optional[Dict[str, Any]] = Field(None, description="Exception information")

class LogsResponse(BaseResponse):
    """Logs response model."""
    logs: List[LogEntry] = Field(..., description="List of log entries")
    count: int = Field(..., description="Number of log entries")

# Validators and helpers
def validate_iso_timestamp(timestamp: str) -> str:
    """Validate ISO-formatted timestamp."""
    try:
        datetime.fromisoformat(timestamp)
        return timestamp
    except ValueError:
        raise ValueError(f"Invalid ISO timestamp format: {timestamp}")

