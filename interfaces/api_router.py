#!/usr/bin/env python3
"""
STRATUM_LIGHT API Router

This module provides the main API router for the STRATUM_LIGHT system,
exposing endpoints for system state, service control, metrics, and more.
"""

import os
import sys
import logging
import json
import time
from typing import Dict, List, Any, Optional, Union, Callable
from datetime import datetime
import traceback
import uuid

# FastAPI imports
from fastapi import FastAPI, APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi.openapi.utils import get_openapi

# Import schema definitions
try:
    from product.interfaces.schema import (
        SystemInfoResponse, ServiceListResponse, ServiceDetailResponse,
        ServiceControlRequest, ServiceControlResponse, RuntimeStateResponse,
        MetricsResponse, ControlActionRequest, ControlActionResponse,
        ErrorResponse, SuccessResponse, LogsResponse
    )
except ImportError:
    # Will be implemented in schema.py
    pass

# Import controllers
try:
    from product.interfaces.controllers.runtime import RuntimeController
    from product.interfaces.controllers.services import ServicesController
    from product.interfaces.controllers.control import ControlController
    from product.interfaces.controllers.metrics import MetricsController
except ImportError:
    # Will be implemented in controller modules
    pass

# Import core modules
try:
    from product.core.services.registry import get_registry, ServiceRegistry, ServiceState
    from product.core.services.graph_executor import get_executor, GraphExecutor
    from product.bootstrap.runtime import get_runtime_state
    from product.configs.environment import get_environment
except ImportError:
    # Fallback for standalone testing
    def get_registry(): return None
    def get_executor(): return None
    def get_runtime_state(): return {"status": "unknown"}
    def get_environment(): return {"tier": "development"}
    class ServiceRegistry: pass
    class ServiceState: pass
    class GraphExecutor: pass

# Set up logger
logger = logging.getLogger(__name__)

class APIRouterFactory:
    """
    Factory class for creating the STRATUM_LIGHT API router.
    
    This class creates and configures the FastAPI application and routers
    for the STRATUM_LIGHT system interface.
    """
    
    def __init__(self):
        """
        Initialize the API router factory."""
        self.app = None
        self.router = None
        self.controllers = {}
        self.registry = get_registry()
        self.executor = get_executor()
        self.runtime_state = get_runtime_state()
        self.environment = get_environment()
        self.api_version = "v1"
        self.request_id_header = "X-Request-ID"
    
    def create_app(self, title: str = "STRATUM_LIGHT API", 
                  description: str = "API for STRATUM_LIGHT system control and monitoring",
                  version: str = "1.0.0") -> FastAPI:
        """
        Create and configure the FastAPI application.
        
        Args:
            title: API title for OpenAPI docs
            description: API description for OpenAPI docs
            version: API version string
            
        Returns:
            Configured FastAPI application
        """
        # Create FastAPI app
        self.app = FastAPI(
            title=title,
            description=description,
            version=version,
            docs_url="/docs",
            redoc_url="/redoc",
            openapi_url=f"/openapi.json"
        )
        
        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # In production, restrict this to specific origins
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Add request ID middleware
        @self.app.middleware("http")
        async def add_request_id(request: Request, call_next):
            # Get or generate request ID
            request_id = request.headers.get(self.request_id_header)
            if not request_id:
                request_id = str(uuid.uuid4())
            
            # Add request ID to request state
            request.state.request_id = request_id
            
            # Process request
            start_time = time.time()
            response = await call_next(request)
            process_time = time.time() - start_time
            
            # Add request ID and timing headers to response
            response.headers[self.request_id_header] = request_id
            response.headers["X-Process-Time"] = str(process_time)
            
            return response
        
        # Add exception handler
        @self.app.exception_handler(Exception)
        async def global_exception_handler(request: Request, exc: Exception):
            # Log exception
            logger.error(f"Unhandled exception: {str(exc)}")
            logger.error(traceback.format_exc())
            
            # Return error response
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            if isinstance(exc, HTTPException):
                status_code = exc.status_code
            
            return JSONResponse(
                status_code=status_code,
                content=jsonable_encoder(ErrorResponse(
                    success=False,
                    error=str(exc),
                    error_type=exc.__class__.__name__,
                    request_id=getattr(request.state, "request_id", None),
                    timestamp=datetime.now().isoformat()
                ))
            )
        
        # Create main router
        self.router = APIRouter(prefix=f"/api/{self.api_version}")
        
        # Initialize controllers
        self._init_controllers()
        
        # Register routes
        self._register_routes()
        
        # Include router in app
        self.app.include_router(self.router)
        
        # Add root endpoint
        @self.app.get("/", tags=["Root"])
        async def root():
            """Root endpoint returning API information."""
            return {
                "name": "STRATUM_LIGHT API",
                "version": version,
                "api_version": self.api_version,
                "docs_url": "/docs",
                "redoc_url": "/redoc",
                "openapi_url": "/openapi.json",
                "environment": self.environment.get("tier", "unknown"),
                "timestamp": datetime.now().isoformat()
            }
        
        # Customize OpenAPI schema
        def custom_openapi():
            if self.app.openapi_schema:
                return self.app.openapi_schema
            
            openapi_schema = get_openapi(
                title=title,
                version=version,
                description=description,
                routes=self.app.routes,
            )
            
            # Add custom info
            openapi_schema["info"]["x-environment"] = self.environment.get("tier", "unknown")
            openapi_schema["info"]["x-generated-at"] = datetime.now().isoformat()
            
            self.app.openapi_schema = openapi_schema
            return self.app.openapi_schema
        
        self.app.openapi = custom_openapi
        
        return self.app
    
    def _init_controllers(self):
        """
        Initialize API controllers."""
        try:
            # Initialize controllers with dependencies
            self.controllers = {
                "runtime": RuntimeController(self.registry, self.executor, self.runtime_state),
                "services": ServicesController(self.registry, self.executor),
                "control": ControlController(self.registry, self.executor),
                "metrics": MetricsController(self.registry)
            }
            logger.info(f"Initialized {len(self.controllers)} API controllers")
        except Exception as e:
            logger.error(f"Failed to initialize API controllers: {str(e)}")
            logger.error(traceback.format_exc())
            # Create empty controllers for testing
            self.controllers = {
                "runtime": None,
                "services": None,
                "control": None,
                "metrics": None
            }
    
    def _register_routes(self):
        """
        Register API routes from controllers."""
        if not self.router:
            logger.error("Cannot register routes: router not initialized")
            return
        
        # System info endpoint
        @self.router.get("/system", response_model=SystemInfoResponse, tags=["System"])
        async def get_system_info():
            """Get system information."""
            if self.controllers["runtime"]:
                return await self.controllers["runtime"].get_system_info()
            
            # Fallback for testing
            return {
                "success": True,
                "system_name": "STRATUM_LIGHT",
                "version": "1.0.0",
                "environment": self.environment.get("tier", "unknown"),
                "uptime": 0,
                "start_time": datetime.now().isoformat(),
                "services_count": 0,
                "services_ready": 0,
                "timestamp": datetime.now().isoformat()
            }
        
        # Runtime state endpoints
        @self.router.get("/runtime", response_model=RuntimeStateResponse, tags=["Runtime"])
        async def get_runtime_state():
            """Get runtime state."""
            if self.controllers["runtime"]:
                return await self.controllers["runtime"].get_runtime_state()
            
            # Fallback for testing
            return {
                "success": True,
                "state": {
                    "status": "unknown",
                    "initialized": False,
                    "ready": False
                },
                "timestamp": datetime.now().isoformat()
            }
        
        @self.router.post("/runtime/reload", response_model=SuccessResponse, tags=["Runtime"])
        async def reload_runtime():
            """Reload runtime configuration."""
            if self.controllers["runtime"]:
                return await self.controllers["runtime"].reload_runtime()
            
            # Fallback for testing
            return {
                "success": True,
                "message": "Runtime reload simulated",
                "timestamp": datetime.now().isoformat()
            }
        
        # Services endpoints
        @self.router.get("/services", response_model=ServiceListResponse, tags=["Services"])
        async def list_services():
            """List all services."""
            if self.controllers["services"]:
                return await self.controllers["services"].list_services()
            
            # Fallback for testing
            return {
                "success": True,
                "services": [],
                "count": 0,
                "timestamp": datetime.now().isoformat()
            }
        
        @self.router.get("/services/{service_name}", response_model=ServiceDetailResponse, tags=["Services"])
        async def get_service_detail(service_name: str):
            """Get service details."""
            if self.controllers["services"]:
                return await self.controllers["services"].get_service_detail(service_name)
            
            # Fallback for testing
            raise HTTPException(status_code=404, detail=f"Service \'{service_name}\' not found")
        
        @self.router.post("/services/{service_name}/control", response_model=ServiceControlResponse, tags=["Services"])
        async def control_service(service_name: str, request: ServiceControlRequest):
            """Control a service."""
            if self.controllers["services"]:
                return await self.controllers["services"].control_service(service_name, request)
            
            # Fallback for testing
            raise HTTPException(status_code=404, detail=f"Service \'{service_name}\' not found")
        
        # Control endpoints
        @self.router.post("/control/action", response_model=ControlActionResponse, tags=["Control"])
        async def execute_control_action(request: ControlActionRequest):
            """Execute a control action."""
            if self.controllers["control"]:
                return await self.controllers["control"].execute_action(request)
            
            # Fallback for testing
            return {
                "success": True,
                "action": request.action,
                "result": "Action simulated",
                "timestamp": datetime.now().isoformat()
            }
        
        @self.router.get("/control/actions", response_model=Dict[str, List[str]], tags=["Control"])
        async def list_control_actions():
            """List available control actions."""
            if self.controllers["control"]:
                return await self.controllers["control"].list_actions()
            
            # Fallback for testing
            return {
                "actions": ["start", "stop", "restart", "reload"]
            }
        
        # Metrics endpoints
        @self.router.get("/metrics", response_model=MetricsResponse, tags=["Metrics"])
        async def get_metrics():
            """Get system metrics."""
            if self.controllers["metrics"]:
                return await self.controllers["metrics"].get_metrics()
            
            # Fallback for testing
            return {
                "success": True,
                "metrics": {},
                "timestamp": datetime.now().isoformat()
            }
        
        @self.router.get("/metrics/{service_name}", response_model=MetricsResponse, tags=["Metrics"])
        async def get_service_metrics(service_name: str):
            """Get service-specific metrics."""
            if self.controllers["metrics"]:
                return await self.controllers["metrics"].get_service_metrics(service_name)
            
            # Fallback for testing
            raise HTTPException(status_code=404, detail=f"Service \'{service_name}\' not found")
        
        # Logs endpoint
        @self.router.get("/logs", response_model=LogsResponse, tags=["Logs"])
        async def get_logs(limit: int = 100, service: Optional[str] = None, level: Optional[str] = None):
            """Get system logs."""
            if self.controllers["runtime"]:
                return await self.controllers["runtime"].get_logs(limit, service, level)
            
            # Fallback for testing
            return {
                "success": True,
                "logs": [],
                "count": 0,
                "timestamp": datetime.now().isoformat()
            }
        
        logger.info("Registered API routes")

def create_api_app() -> FastAPI:
    """
    Create and configure the STRATUM_LIGHT API application.
    
    Returns:
        Configured FastAPI application
    """
    factory = APIRouterFactory()
    return factory.create_app()

# For direct execution
if __name__ == "__main__":
    import uvicorn
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    
    # Create app
    app = create_api_app()
    
    # Run server
    uvicorn.run(app, host="0.0.0.0", port=8000)


