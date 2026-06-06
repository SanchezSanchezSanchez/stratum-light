#!/usr/bin/env python3
# SIEM Integration Module for STRATUM_LIGHT

import logging
import requests
import json
from datetime import datetime
from typing import Dict, Any, Optional

# Set up logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s|%(levelname)s|%(message)s')
logger = logging.getLogger(__name__)

# Import configuration
from config.settings import config

class SiemLogger:
    """Handles connection to external SIEM systems"""
    
    def __init__(self, endpoint: Optional[str] = None):
        """
        Initialize the SIEM logger
        
        Args:
            endpoint: Optional override for SIEM endpoint
        """
        self.endpoint = endpoint or config.get("siem_endpoint", "https://splunk.example.com")
        logger.info(f"SIEM Logger initialized with endpoint: {self.endpoint}")
    
    def log_to_siem(self, vulnerability: str, response: str, model: str) -> bool:
        """
        Log a security event to the configured SIEM endpoint
        
        Args:
            vulnerability: Description of the vulnerability
            response: Model response demonstrating the vulnerability
            model: Name of the model
            
        Returns:
            True if logging was successful, False otherwise
        """
        siem_event = {
            "event": "LLM Vulnerability Discovery",
            "model": model,
            "vulnerability": vulnerability,
            "response": response,
            "timestamp": datetime.utcnow().isoformat(),
            "source": "STRATUM_LIGHT",
            "severity": "HIGH",
            "event_id": f"stratum-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        }
        
        try:
            response = requests.post(
                self.endpoint, 
                json=siem_event,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code in (200, 201, 202):
                logger.info(f"SIEM event logged successfully: {siem_event['event_id']}")
                return True
            else:
                logger.error(f"SIEM logging failed with status code {response.status_code}: {response.text}")
                self._save_local_backup(siem_event)
                return False
                
        except Exception as e:
            logger.error(f"SIEM logging failed: {str(e)}")
            self._save_local_backup(siem_event)
            return False
    
    def _save_local_backup(self, event: Dict[str, Any]) -> None:
        """
        Save a local backup of the SIEM event if sending fails
        
        Args:
            event: SIEM event data
        """
        try:
            filename = f"siem_event_{event.get('event_id', datetime.utcnow().strftime('%Y%m%d%H%M%S'))}.json"
            with open(filename, "w") as f:
                json.dump(event, f, indent=2)
            logger.info(f"SIEM event backup saved to {filename}")
        except Exception as e:
            logger.error(f"Failed to save local SIEM backup: {str(e)}")
    
    def log_system_event(self, event_type: str, details: Dict[str, Any], severity: str = "INFO") -> bool:
        """
        Log a system event to the SIEM
        
        Args:
            event_type: Type of system event
            details: Event details
            severity: Event severity (INFO, WARNING, ERROR, CRITICAL)
            
        Returns:
            True if logging was successful, False otherwise
        """
        siem_event = {
            "event": event_type,
            "details": details,
            "timestamp": datetime.utcnow().isoformat(),
            "source": "STRATUM_LIGHT",
            "severity": severity,
            "event_id": f"stratum-sys-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        }
        
        try:
            response = requests.post(
                self.endpoint, 
                json=siem_event,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code in (200, 201, 202):
                logger.info(f"System event logged to SIEM: {event_type}")
                return True
            else:
                logger.error(f"System event logging failed with status code {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"System event logging failed: {str(e)}")
            return False
    
    def batch_log_events(self, events: list[Dict[str, Any]]) -> Dict[str, int]:
        """
        Log multiple events to SIEM in batch
        
        Args:
            events: List of event dictionaries
            
        Returns:
            Dictionary with counts of successful and failed events
        """
        if not events:
            logger.warning("No events provided for batch logging")
            return {"success": 0, "failed": 0}
        
        results = {"success": 0, "failed": 0}
        
        try:
            # Add timestamps and IDs if missing
            for event in events:
                if "timestamp" not in event:
                    event["timestamp"] = datetime.utcnow().isoformat()
                if "event_id" not in event:
                    event["event_id"] = f"stratum-batch-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
                if "source" not in event:
                    event["source"] = "STRATUM_LIGHT"
            
            # Send batch request
            response = requests.post(
                f"{self.endpoint}/batch",
                json={"events": events},
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code in (200, 201, 202):
                logger.info(f"Batch logged {len(events)} events to SIEM")
                results["success"] = len(events)
            else:
                logger.error(f"Batch logging failed with status code {response.status_code}")
                results["failed"] = len(events)
                # Save backup of all events
                for event in events:
                    self._save_local_backup(event)
                    
        except Exception as e:
            logger.error(f"Batch logging failed: {str(e)}")
            results["failed"] = len(events)
            # Save backup of all events
            for event in events:
                self._save_local_backup(event)
        
        return results

# Create singleton instance for easy import
siem_logger = SiemLogger()

def log_vulnerability(vulnerability: str, response: str, model: str) -> bool:
    """
    Convenience function to log a vulnerability to SIEM
    
    Args:
        vulnerability: Description of the vulnerability
        response: Model response demonstrating the vulnerability
        model: Name of the model
        
    Returns:
        True if logging was successful, False otherwise
    """
    return siem_logger.log_to_siem(vulnerability, response, model)

def log_system_event(event_type: str, details: Dict[str, Any], severity: str = "INFO") -> bool:
    """
    Convenience function to log a system event to SIEM
    
    Args:
        event_type: Type of system event
        details: Event details
        severity: Event severity (INFO, WARNING, ERROR, CRITICAL)
        
    Returns:
        True if logging was successful, False otherwise
    """
    return siem_logger.log_system_event(event_type, details, severity)
