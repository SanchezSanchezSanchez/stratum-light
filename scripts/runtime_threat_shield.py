#!/usr/bin/env python3
"""
STRATUM_LIGHT Runtime Threat Shield

This module provides real-time monitoring and protection for the API and CLI layers
of STRATUM_LIGHT, detecting and preventing runtime threats including:
- Anomalous API call patterns
- Command injection attempts
- Privilege escalation
- Resource exhaustion attacks
- Unauthorized access attempts

The Runtime Threat Shield integrates with BehaviorSentinel and FaultGovernor
to provide comprehensive protection across the application.
"""

import os
import time
import json
import logging
import hashlib
import threading
import traceback
from typing import Dict, List, Any, Optional, Callable, Tuple, Set
from functools import wraps
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("/var/log/stratum_light/threat_shield.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("threat_shield")

class RuntimeThreatShield:
    """
    Runtime Threat Shield for STRATUM_LIGHT.
    
    Provides real-time monitoring and protection for API and CLI interfaces.
    """
    
    def __init__(self, config: Dict = None):
        """
        Initialize the Runtime Threat Shield.
        
        Args:
            config: Configuration dictionary (optional)
        """
        self.config = config or self._load_default_config()
        self.active = True
        self.threat_registry = {}
        self.request_history = {}
        self.blocked_ips = set()
        self.suspicious_ips = {}
        self.api_call_patterns = {}
        self.command_history = {}
        self.resource_usage = {}
        self.last_cleanup = time.time()
        
        # Initialize monitoring thread
        self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitor_thread.start()
        
        logger.info("Runtime Threat Shield initialized")
    
    def _load_default_config(self) -> Dict:
        """
        Load default configuration.
        
        Returns:
            Default configuration dictionary
        """
        return {
            "rate_limits": {
                "api_requests_per_minute": 60,
                "cli_commands_per_minute": 30,
                "failed_auth_attempts_per_minute": 5
            },
            "thresholds": {
                "suspicious_activity_score": 70,
                "blocking_score": 90,
                "resource_usage_percent": 80
            },
            "timeouts": {
                "suspicious_ip_timeout_minutes": 30,
                "blocked_ip_timeout_minutes": 60,
                "history_retention_minutes": 60
            },
            "patterns": {
                "command_injection": [
                    r";\s*\w+",
                    r"\|\s*\w+",
                    r"`.*`",
                    r"\$\(.*\)"
                ],
                "path_traversal": [
                    r"\.\.\/",
                    r"\.\.\\",
                    r"%2e%2e%2f",
                    r"%252e%252e%252f"
                ],
                "sql_injection": [
                    r"'\s*OR\s*'1'='1",
                    r"--\s",
                    r";\s*DROP\s+TABLE",
                    r"UNION\s+SELECT"
                ]
            }
        }
    
    def protect_api_endpoint(self, func: Callable) -> Callable:
        """
        Decorator to protect API endpoints.
        
        Args:
            func: API endpoint function to protect
            
        Returns:
            Protected function
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Extract request information
            request = kwargs.get('request') or (args[0] if args else None)
            if not request:
                logger.warning("No request object found in API call")
                return func(*args, **kwargs)
            
            # Get client IP
            client_ip = self._extract_client_ip(request)
            
            # Check if IP is blocked
            if client_ip in self.blocked_ips:
                logger.warning(f"Blocked request from banned IP: {client_ip}")
                return self._generate_blocked_response()
            
            # Record request for rate limiting
            self._record_api_request(client_ip, request)
            
            # Check for rate limiting
            if self._is_rate_limited(client_ip, "api"):
                logger.warning(f"Rate limited API request from IP: {client_ip}")
                self._increase_suspicion_score(client_ip, 20, "Rate limit exceeded")
                return self._generate_rate_limited_response()
            
            # Check for suspicious patterns
            threat_score, threat_type = self._analyze_api_request(request)
            if threat_score > self.config["thresholds"]["suspicious_activity_score"]:
                logger.warning(f"Suspicious API request detected: {threat_type} from {client_ip}")
                self._increase_suspicion_score(client_ip, threat_score, threat_type)
                
                if threat_score > self.config["thresholds"]["blocking_score"]:
                    logger.error(f"Blocking high-threat API request: {threat_type} from {client_ip}")
                    self.blocked_ips.add(client_ip)
                    return self._generate_blocked_response()
            
            # Execute the endpoint function with monitoring
            try:
                start_time = time.time()
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                # Check for anomalous response time
                if execution_time > 5.0:  # Threshold for slow responses
                    logger.warning(f"Slow API response: {execution_time:.2f}s for {request.path}")
                    self._record_resource_usage(client_ip, "response_time", execution_time)
                
                return result
            except Exception as e:
                logger.error(f"Exception in protected API endpoint: {str(e)}")
                self._record_exception(client_ip, str(e), traceback.format_exc())
                raise
        
        return wrapper
    
    def protect_cli_command(self, func: Callable) -> Callable:
        """
        Decorator to protect CLI commands.
        
        Args:
            func: CLI command function to protect
            
        Returns:
            Protected function
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Extract command information
            command_name = func.__name__
            command_args = str(args) + str(kwargs)
            user_id = os.environ.get("USER") or "unknown"
            
            # Record command for rate limiting
            self._record_cli_command(user_id, command_name, command_args)
            
            # Check for rate limiting
            if self._is_rate_limited(user_id, "cli"):
                logger.warning(f"Rate limited CLI command from user: {user_id}")
                print("Error: Command rate limit exceeded. Please try again later.")
                return None
            
            # Check for suspicious patterns
            threat_score, threat_type = self._analyze_cli_command(command_name, command_args)
            if threat_score > self.config["thresholds"]["suspicious_activity_score"]:
                logger.warning(f"Suspicious CLI command detected: {threat_type} from {user_id}")
                
                if threat_score > self.config["thresholds"]["blocking_score"]:
                    logger.error(f"Blocking high-threat CLI command: {threat_type} from {user_id}")
                    print("Error: Command blocked due to security concerns.")
                    return None
            
            # Execute the command function with monitoring
            try:
                start_time = time.time()
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                # Check for anomalous execution time
                if execution_time > 10.0:  # Threshold for slow commands
                    logger.warning(f"Slow CLI command: {execution_time:.2f}s for {command_name}")
                    self._record_resource_usage(user_id, "execution_time", execution_time)
                
                return result
            except Exception as e:
                logger.error(f"Exception in protected CLI command: {str(e)}")
                self._record_exception(user_id, str(e), traceback.format_exc())
                raise
        
        return wrapper
    
    def _extract_client_ip(self, request) -> str:
        """
        Extract client IP from request.
        
        Args:
            request: HTTP request object
            
        Returns:
            Client IP address
        """
        # Try common headers for proxied requests
        for header in ["X-Forwarded-For", "X-Real-IP"]:
            if hasattr(request, "headers") and header in request.headers:
                return request.headers[header].split(",")[0].strip()
        
        # Fall back to direct IP
        if hasattr(request, "client") and hasattr(request.client, "host"):
            return request.client.host
        
        # Last resort
        return "unknown"
    
    def _record_api_request(self, client_ip: str, request) -> None:
        """
        Record API request for rate limiting and pattern analysis.
        
        Args:
            client_ip: Client IP address
            request: HTTP request object
        """
        current_time = time.time()
        
        # Initialize history for this IP if not exists
        if client_ip not in self.request_history:
            self.request_history[client_ip] = []
        
        # Record request details
        request_info = {
            "timestamp": current_time,
            "path": getattr(request, "path", "unknown"),
            "method": getattr(request, "method", "unknown"),
            "query_params": getattr(request, "query_params", {}),
            "headers": getattr(request, "headers", {})
        }
        
        # Add request to history
        self.request_history[client_ip].append(request_info)
        
        # Update API call patterns
        path = request_info["path"]
        if path not in self.api_call_patterns:
            self.api_call_patterns[path] = {"count": 0, "ips": set()}
        
        self.api_call_patterns[path]["count"] += 1
        self.api_call_patterns[path]["ips"].add(client_ip)
    
    def _record_cli_command(self, user_id: str, command_name: str, command_args: str) -> None:
        """
        Record CLI command for rate limiting and pattern analysis.
        
        Args:
            user_id: User identifier
            command_name: Name of the command
            command_args: Command arguments
        """
        current_time = time.time()
        
        # Initialize history for this user if not exists
        if user_id not in self.command_history:
            self.command_history[user_id] = []
        
        # Record command details
        command_info = {
            "timestamp": current_time,
            "command": command_name,
            "args": command_args
        }
        
        # Add command to history
        self.command_history[user_id].append(command_info)
    
    def _is_rate_limited(self, identifier: str, request_type: str) -> bool:
        """
        Check if a client is being rate limited.
        
        Args:
            identifier: Client identifier (IP or user ID)
            request_type: Type of request ("api" or "cli")
            
        Returns:
            True if rate limited, False otherwise
        """
        current_time = time.time()
        one_minute_ago = current_time - 60
        
        if request_type == "api":
            if identifier not in self.request_history:
                return False
            
            # Count requests in the last minute
            recent_requests = [r for r in self.request_history[identifier] 
                              if r["timestamp"] > one_minute_ago]
            
            return len(recent_requests) > self.config["rate_limits"]["api_requests_per_minute"]
        
        elif request_type == "cli":
            if identifier not in self.command_history:
                return False
            
            # Count commands in the last minute
            recent_commands = [c for c in self.command_history[identifier] 
                              if c["timestamp"] > one_minute_ago]
            
            return len(recent_commands) > self.config["rate_limits"]["cli_commands_per_minute"]
        
        return False
    
    def _analyze_api_request(self, request) -> Tuple[int, str]:
        """
        Analyze API request for suspicious patterns.
        
        Args:
            request: HTTP request object
            
        Returns:
            Tuple of (threat_score, threat_type)
        """
        threat_score = 0
        threat_type = "none"
        
        # Check for command injection in query parameters
        if hasattr(request, "query_params"):
            for param, value in request.query_params.items():
                for pattern in self.config["patterns"]["command_injection"]:
                    if re.search(pattern, str(value)):
                        threat_score += 40
                        threat_type = "command_injection"
                        break
        
        # Check for path traversal
        if hasattr(request, "path"):
            for pattern in self.config["patterns"]["path_traversal"]:
                if re.search(pattern, request.path):
                    threat_score += 50
                    threat_type = "path_traversal"
                    break
        
        # Check for SQL injection in body
        if hasattr(request, "json"):
            json_str = json.dumps(request.json)
            for pattern in self.config["patterns"]["sql_injection"]:
                if re.search(pattern, json_str):
                    threat_score += 60
                    threat_type = "sql_injection"
                    break
        
        # Check for suspicious headers
        if hasattr(request, "headers"):
            # User-Agent anomalies
            user_agent = request.headers.get("User-Agent", "")
            if not user_agent or user_agent.lower() in ["", "curl", "wget", "python-requests"]:
                threat_score += 10
                threat_type = "suspicious_user_agent"
            
            # Content-Type mismatches
            content_type = request.headers.get("Content-Type", "")
            if hasattr(request, "method") and request.method == "POST" and "application/json" not in content_type:
                threat_score += 5
                threat_type = "content_type_mismatch"
        
        return threat_score, threat_type
    
    def _analyze_cli_command(self, command_name: str, command_args: str) -> Tuple[int, str]:
        """
        Analyze CLI command for suspicious patterns.
        
        Args:
            command_name: Name of the command
            command_args: Command arguments
            
        Returns:
            Tuple of (threat_score, threat_type)
        """
        threat_score = 0
        threat_type = "none"
        
        # Check for command injection
        for pattern in self.config["patterns"]["command_injection"]:
            if re.search(pattern, command_args):
                threat_score += 50
                threat_type = "command_injection"
                break
        
        # Check for path traversal
        for pattern in self.config["patterns"]["path_traversal"]:
            if re.search(pattern, command_args):
                threat_score += 40
                threat_type = "path_traversal"
                break

        # Simple privilege escalation detection
        if "sudo" in command_args or "rm -rf /" in command_args:
            threat_score += 60
            threat_type = "privilege_escalation"

        return threat_score, threat_type

    def _increase_suspicion_score(self, identifier: str, amount: int, reason: str) -> None:
        score = self.suspicious_ips.get(identifier, {"score": 0, "reasons": []})
        score["score"] += amount
        score["reasons"].append({"timestamp": time.time(), "reason": reason})
        self.suspicious_ips[identifier] = score

    def _record_resource_usage(self, identifier: str, metric: str, value: float) -> None:
        if identifier not in self.resource_usage:
            self.resource_usage[identifier] = {}
        self.resource_usage[identifier][metric] = value

    def _record_exception(self, identifier: str, message: str, tb: str) -> None:
        self.threat_registry.setdefault(identifier, []).append({
            "timestamp": time.time(),
            "message": message,
            "traceback": tb,
        })

    def _generate_blocked_response(self) -> Dict[str, Any]:
        return {"status": "blocked"}

    def _generate_rate_limited_response(self) -> Dict[str, Any]:
        return {"status": "rate_limited"}

    def _monitoring_loop(self) -> None:
        while self.active:
            self._cleanup_history()
            time.sleep(5)

    def _cleanup_history(self) -> None:
        cutoff = time.time() - (self.config["timeouts"]["history_retention_minutes"] * 60)
        for history in (self.request_history, self.command_history):
            for key in list(history.keys()):
                history[key] = [h for h in history[key] if h["timestamp"] > cutoff]
