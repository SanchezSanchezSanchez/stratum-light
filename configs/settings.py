#!/usr/bin/env python3
# Configuration Module for STRATUM_LIGHT

import os
import json
import logging
import re
from typing import Dict, Any, Optional, List, Union
from cryptography.fernet import Fernet

# Set up logger
logger = logging.getLogger(__name__)

# Try to import dotenv for environment variable management
try:
    from dotenv import load_dotenv
    load_dotenv()
    logger.info("Environment variables loaded from .env file")
except ImportError:
    logger.warning("python-dotenv not installed, using system environment variables only")

# Import Pydantic models for validation
try:
    from .schemas import MainConfig
    from pydantic import ValidationError
except ImportError:
    logger.critical("Failed to import configuration schemas. Pydantic validation will be skipped.")
    MainConfig = None
    ValidationError = None


class ConfigManager:
    """Configuration manager for STRATUM_LIGHT with dynamic key parsing"""
    
    # Environment variable prefix for config overrides
    ENV_PREFIX = "STRATUM_"
    
    # Sensitive keys that should be redacted in logs
    SENSITIVE_KEYS = [
        "key", "secret", "password", "token", "credential", "auth", 
        "license", "api_key", "private", "cert"
    ]
    
    def __init__(self):
        self._raw_config = self._load_and_merge_configs() # Step 1: Load raw config

        if MainConfig and ValidationError:
            try:
                # Step 2: Validate and parse with Pydantic
                self._validated_config = MainConfig(**self._raw_config)
                logger.info("Configuration successfully validated with Pydantic models.")
                # Keep both the validated model and a dict representation
                self._config = self._validated_config.model_dump(mode='python')


            except ValidationError as e:
                logger.critical("Configuration validation failed!")
                for error in e.errors():
                    logger.critical(f"  - Location: {'.'.join(map(str, error['loc']))}, Message: {error['msg']}, Input: {error['input']}")
                raise SystemExit("Configuration validation failed!")
            except Exception as e: # Catch other potential errors during Pydantic processing
                logger.critical(f"An unexpected error occurred during Pydantic model parsing: {e}", exc_info=True)
                raise SystemExit("Exiting due to unexpected error during configuration parsing.")
        else:
            logger.warning("Pydantic models (MainConfig or ValidationError) not available. Skipping Pydantic validation.")
            self._config = self._raw_config # Use raw config if Pydantic isn't available
            self._validated_config = None # No validated config
        
    def _load_and_merge_configs(self) -> Dict[str, Any]:
        # Note: Provide static defaults here; STRATUM_* env overrides are applied later
        """Loads configuration from defaults, file, and environment, then merges them."""
        # Default configuration
        default_config = {
            "models": ["gpt2", "llama", "grok"],
            "boost": 1.5,
            "bounty_endpoints": [
                "https://api.hackerone.com/v1/reports",
                "https://api.bugcrowd.com/submissions",
                "https://api.xai.com/v1/bounties"
            ],
            "cvss_base": 9.0,
            "cvss_vector": "AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H",
            "siem_endpoint": "https://splunk.example.com",
            "cloud_providers": ["aws", "azure", "gcp"],
            "logging": {
                "level": "INFO",
                "log_to_file": True,
                "log_path": "logs/stratum.log"
            },
            "api_bounty_endpoint": "https://api.hackerone.com/v1/reports",
            "api_siem_endpoint": "https://splunk.example.com",
            "default_model": "gpt2",
            "timeout": 30,
            "environment": "development",

            # Configuration for Helper LLM used by PromptInjectionAnalyzer
            "helper_llm": {
                "type": "none",  # "local", "remote_api", or "none"
                "local_model_path": "",
                "local_model_type": "",
                # Parameters for local model inference (primarily for GGUF via llama-cpp-python)
                "local_helper_max_tokens": 256,
                "local_helper_temperature": 0.1,
                "local_helper_llama_cpp_n_ctx": 2048,
                "local_helper_llama_cpp_n_gpu_layers": 0,
                "local_helper_llama_cpp_verbose": False,
                "local_helper_llama_cpp_args": "",

                "remote_api_endpoint": None,
                "remote_api_key": "",
                "remote_api_timeout": 30,
            },

            # Configuration for the Target Model (model being analyzed by PromptInjectionAnalyzer)
            "target_model_sdk": {
                # For API-based target models
                "api_endpoint": None,
                "api_key": "",

                # Parameters for local TARGET model inference (primarily for GGUF via llama-cpp-python)
                # These are used by LocalLLMAdapter.get_target_model_output if model_name is a local path
                "local_target_max_tokens": 150,
                "local_target_temperature": 0.7,
                "local_target_llama_cpp_n_ctx": 2048,
                "local_target_llama_cpp_n_gpu_layers": 0,
                "local_target_llama_cpp_verbose": False,
                # No STRATUM_LOCAL_TARGET_LLAMA_CPP_ARGS for now, to keep it simpler. Can be added if needed.
            }
        }
        
        # Try to load from encrypted config file first
        config_from_file = self._load_encrypted_config()
        
        # If encrypted config failed, try plaintext as fallback
        if not config_from_file:
            config_from_file = self._load_plaintext_config()
        
        # Merge with defaults, prioritizing file config
        merged_config = self._deep_merge(default_config, config_from_file or {})
        
        # Apply environment variable overrides
        config_with_env = self._apply_env_overrides(merged_config)
        
        return config_with_env
    
    def _load_encrypted_config(self) -> Optional[Dict[str, Any]]:
        """Load configuration from encrypted file"""
        config_key = os.getenv("LIGHT_CONFIG_KEY")
        if not config_key:
            logger.warning("LIGHT_CONFIG_KEY not set, skipping encrypted config")
            return None
            
        try:
            cipher = Fernet(config_key)
            config_path = os.path.join(os.path.dirname(__file__), "..", "light_config.json.enc")
            
            # Try encrypted file first
            if os.path.exists(config_path):
                with open(config_path, "rb") as f:
                    encrypted_config = f.read()
                    decrypted_config = json.loads(cipher.decrypt(encrypted_config))
                    logger.info("Configuration loaded from encrypted file")
                    return decrypted_config
            else:
                logger.warning(f"Encrypted config file not found at {config_path}")
                return None
        except Exception as e:
            logger.error(f"Failed to load encrypted configuration: {str(e)}")
            return None
    
    def _load_plaintext_config(self) -> Optional[Dict[str, Any]]:
        """Load configuration from plaintext file as fallback"""
        try:
            config_path = os.path.join(os.path.dirname(__file__), "..", "light_config.json")
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    config = json.load(f)
                    logger.warning("Configuration loaded from plaintext file - SECURITY RISK")
                    return config
            else:
                logger.warning(f"Plaintext config file not found at {config_path}")
                return None
        except Exception as e:
            logger.error(f"Failed to load plaintext configuration: {str(e)}")
            return None
    
    def _deep_merge(self, dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively merge two dictionaries
        
        Args:
            dict1: Base dictionary
            dict2: Dictionary to merge (takes precedence for conflicts)
            
        Returns:
            Merged dictionary
        """
        result = dict1.copy()
        
        for key, value in dict2.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                # Recursively merge nested dictionaries
                result[key] = self._deep_merge(result[key], value)
            else:
                # Override or add value
                result[key] = value
                
        return result
    
    def _apply_env_overrides(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply environment variable overrides to configuration
        
        Args:
            config: Base configuration
            
        Returns:
            Configuration with environment overrides applied
        """
        result = config.copy()
        
        # Get all environment variables with the prefix
        for env_key, env_value in os.environ.items():
            if env_key.startswith(self.ENV_PREFIX):
                # Convert environment variable name to config key path
                # e.g., STRATUM_LOGGING_LEVEL -> logging.level
                config_path = env_key[len(self.ENV_PREFIX):].lower().replace("__", ".")
                
                # Apply the override
                self._set_nested_key(result, config_path, self._parse_env_value(env_value))
                
                # Log the override (redact sensitive values)
                if any(sensitive in config_path.lower() for sensitive in self.SENSITIVE_KEYS):
                    logger.info(f"Applied environment override for {config_path}: [REDACTED]")
                else:
                    logger.info(f"Applied environment override for {config_path}: {env_value}")
        
        return result
    
    def _parse_env_value(self, value: str) -> Any:
        """
        Parse environment variable value to appropriate type
        
        Args:
            value: String value from environment
            
        Returns:
            Parsed value (bool, int, float, list, or original string)
        """
        # Boolean values
        if value.lower() in ("true", "yes", "1", "on"):
            return True
        if value.lower() in ("false", "no", "0", "off"):
            return False
            
        # Try to parse as JSON (for lists, dicts)
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass
            
        # Try to parse as integer
        try:
            return int(value)
        except ValueError:
            pass
            
        # Try to parse as float
        try:
            return float(value)
        except ValueError:
            pass
            
        # Return as string
        return value
    
    def _set_nested_key(self, config: Dict[str, Any], key_path: str, value: Any) -> None:
        """
        Set a nested key in the configuration
        
        Args:
            config: Configuration dictionary
            key_path: Dot-separated path to the key
            value: Value to set
        """
        keys = key_path.split(".")
        current = config
        
        # Navigate to the parent of the target key
        for key in keys[:-1]:
            if key not in current or not isinstance(current[key], dict):
                current[key] = {}
            current = current[key]
            
        # Set the value
        current[keys[-1]] = value
    
    def get(self, key_path: str, default: Optional[Any] = None) -> Any:
        """
        Get configuration value by key path with optional default
        
        Args:
            key_path: Dot-separated path to the key
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        try:
            value = self._get_nested_key(self._config, key_path)
            return value if value is not None else default
        except KeyError:
            if default is None:
                logger.warning(f"Configuration key '{key_path}' not found and no default provided")
            return default
    
    def _get_nested_key(self, config_dict: Dict[str, Any], key_path: str) -> Any:
        """
        Get a nested key from a dictionary.
        
        Args:
            config_dict: The dictionary to search.
            key_path: Dot-separated path to the key.
            
        Returns:
            Configuration value
            
        Raises:
            KeyError: If key not found
        """
        # Handle direct key access (no dots)
        if "." not in key_path:
            # Ensure we are using the passed dictionary, not the global 'config'
            return config_dict.get(key_path)
            
        # Handle nested key access
        keys = key_path.split(".")
        current = config_dict
        
        # Navigate to the target key
        for key in keys[:-1]:
            if not isinstance(current, dict) or key not in current: # Check if current is a dict before access
                raise KeyError(f"Key path '{key_path}' not found at segment '{key}'")
            current = current[key]
            
        # Get the value
        if not isinstance(current, dict) or keys[-1] not in current: # Check if current is a dict before access
            raise KeyError(f"Key path '{key_path}' not found at final segment '{keys[-1]}'")
            
        return current[keys[-1]]
    
    def __getitem__(self, key_path: str) -> Any:
        """Allow dictionary-style access to configuration"""
        value = self.get(key_path)
        if value is None:
            raise KeyError(f"Configuration key '{key_path}' not found")
        return value
    
    def __contains__(self, key_path: str) -> bool:
        """Check if configuration contains key path"""
        try:
            return self._get_nested_key(self._config, key_path) is not None
        except KeyError:
            return False
    
    def update_config(self, new_config: Dict[str, Any]) -> None:
        """Update configuration with new values"""
        self._config = self._deep_merge(self._config, new_config)
        logger.info("Configuration updated")
    
    def save_config(self, encrypt: bool = True) -> bool:
        """
        Save current configuration to file
        
        Args:
            encrypt: Whether to encrypt the configuration
            
        Returns:
            True if successful, False otherwise
        """
        if encrypt:
            return self._save_encrypted_config()
        else:
            return self._save_plaintext_config()
    
    def _save_encrypted_config(self) -> bool:
        """Save configuration to encrypted file"""
        config_key = os.getenv("LIGHT_CONFIG_KEY")
        if not config_key:
            logger.error("Cannot save encrypted configuration: LIGHT_CONFIG_KEY not set")
            return False
            
        try:
            cipher = Fernet(config_key)
            config_path = os.path.join(os.path.dirname(__file__), "..", "light_config.json.enc")
            encrypted_config = cipher.encrypt(json.dumps(self._config, indent=2).encode())
            
            with open(config_path, "wb") as f:
                f.write(encrypted_config)
                
            logger.info("Configuration saved to encrypted file")
            return True
        except Exception as e:
            logger.error(f"Failed to save encrypted configuration: {str(e)}")
            return False
    
    def _save_plaintext_config(self) -> bool:
        """Save configuration to plaintext file"""
        try:
            config_path = os.path.join(os.path.dirname(__file__), "..", "light_config.json")
            
            with open(config_path, "w") as f:
                json.dump(self._config, f, indent=2)
                
            logger.warning("Configuration saved to plaintext file - SECURITY RISK")
            return True
        except Exception as e:
            logger.error(f"Failed to save plaintext configuration: {str(e)}")
            return False
    
    def get_all(self, redact_sensitive: bool = True) -> Dict[str, Any]:
        """
        Get all configuration values
        
        Args:
            redact_sensitive: Whether to redact sensitive values
            
        Returns:
            Complete configuration dictionary
        """
        if not redact_sensitive:
            return self._config.copy()
            
        # Create a deep copy with sensitive values redacted
        return self._redact_sensitive_values(self._config)
    
    def _redact_sensitive_values(self, config: Dict[str, Any], path: str = "") -> Dict[str, Any]:
        """
        Recursively redact sensitive values in configuration
        
        Args:
            config: Configuration dictionary
            path: Current path in the configuration
            
        Returns:
            Configuration with sensitive values redacted
        """
        result = {}
        
        for key, value in config.items():
            current_path = f"{path}.{key}" if path else key
            
            if isinstance(value, dict):
                # Recursively process nested dictionaries
                result[key] = self._redact_sensitive_values(value, current_path)
            elif any(sensitive in current_path.lower() for sensitive in self.SENSITIVE_KEYS):
                # Redact sensitive values
                result[key] = "[REDACTED]"
            else:
                # Keep non-sensitive values
                result[key] = value
                
        return result
    
    def generate_key(self) -> str:
        """
        Generate a new encryption key
        
        Returns:
            Base64-encoded Fernet key
        """
        return Fernet.generate_key().decode()

# Create singleton instance
config = ConfigManager()

# Configure logging based on config
log_level = getattr(logging, config.get("logging.level", "INFO"))
logging.basicConfig(level=log_level, format='%(asctime)s|%(levelname)s|%(message)s')

# Set up file logging if enabled
if config.get("logging.log_to_file", False):
    log_path = config.get("logging.log_path", "logs/stratum.log")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    file_handler = logging.FileHandler(log_path)
    file_handler.setFormatter(logging.Formatter('%(asctime)s|%(levelname)s|%(message)s'))
    logging.getLogger().addHandler(file_handler)

# Validate critical configuration
if not config.get("api_bounty_endpoint") and not config.get("bounty_endpoints"):
    logger.critical("No bounty endpoints configured")

if not config.get("api_siem_endpoint") and not config.get("siem_endpoint"):
    logger.critical("No SIEM endpoint configured")

# Export the config instance for other modules
__all__ = ["config"]
