#!/usr/bin/env python3
# Integration Tests for STRATUM_LIGHT Bootstrap System

import os
import sys
import unittest
import logging
from unittest.mock import patch, MagicMock
import tempfile
import json
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import environment schema
from config.environment import EnvironmentTier

class TestBootstrapIntegration(unittest.TestCase):
    """Integration tests for the bootstrap system"""
    
    def setUp(self):
        """Set up test environment"""
        # Create temp directory for logs
        self.temp_dir = tempfile.TemporaryDirectory()
        self.log_path = os.path.join(self.temp_dir.name, "test.log")
        
        # Clear environment variables
        self.env_patcher = patch.dict('os.environ', {
            "STRATUM_ENV": "development",
            "LIGHT_BOUNTY_KEY": "test-bounty-key",
            "LIGHT_CONFIG_KEY": "test-config-key"
        })
        self.env_patcher.start()
        
        # Clear root logger handlers
        self.root_logger = logging.getLogger()
        self.original_handlers = self.root_logger.handlers.copy()
        self.root_logger.handlers.clear()
    
    def tearDown(self):
        """Clean up test environment"""
        # Stop environment patcher
        self.env_patcher.stop()
        
        # Restore root logger handlers
        self.root_logger.handlers.clear()
        for handler in self.original_handlers:
            self.root_logger.addHandler(handler)
        
        # Clean up temp directory
        self.temp_dir.cleanup()
    
    def test_bootstrap_development_tier(self):
        """Test bootstrap in development tier"""
        # Set up environment for development
        with patch.dict('os.environ', {
            "STRATUM_ENV": "development",
            "LIGHT_BOUNTY_KEY": "test-bounty-key",
            "LIGHT_CONFIG_KEY": "test-config-key",
            "LOG_LEVEL": "DEBUG"
        }):
            # Import bootstrap modules
            from config.environment import env
            from bootstrap.logging import configure_logging
            from bootstrap.runtime import RuntimeState
            import bootstrap
            
            # Verify environment tier
            self.assertTrue(env.is_dev())
            self.assertEqual(env.get_tier(), EnvironmentTier.DEVELOPMENT)
            
            # Initialize bootstrap
            result = bootstrap.initialize()
            self.assertTrue(result)
            
            # Verify runtime state
            runtime = bootstrap.get_runtime_state()
            self.assertIsInstance(runtime, RuntimeState)
            
            # Verify development-specific features
            self.assertTrue(runtime.is_feature_enabled("debug_mode"))
            self.assertTrue(runtime.is_feature_enabled("verbose_logging"))
            self.assertTrue(runtime.is_feature_enabled("mock_endpoints"))
            self.assertFalse(runtime.is_feature_enabled("high_security"))
    
    def test_bootstrap_staging_tier(self):
        """Test bootstrap in staging tier"""
        # Set up environment for staging
        with patch.dict('os.environ', {
            "STRATUM_ENV": "staging",
            "LIGHT_BOUNTY_KEY": "test-bounty-key",
            "LIGHT_CONFIG_KEY": "test-config-key",
            "CLOUD_DEPLOY_AUTH_AWS": "test-aws-auth",
            "CLOUD_DEPLOY_AUTH_AZURE": "test-azure-auth",
            "CLOUD_DEPLOY_AUTH_GCP": "test-gcp-auth",
            "SIEM_ENDPOINT": "https://staging-splunk.example.com",
            "LOG_LEVEL": "INFO"
        }):
            # Import bootstrap modules
            from config.environment import env
            from bootstrap.logging import configure_logging
            from bootstrap.runtime import RuntimeState
            import bootstrap
            
            # Verify environment tier
            self.assertTrue(env.is_staging())
            self.assertEqual(env.get_tier(), EnvironmentTier.STAGING)
            
            # Initialize bootstrap
            result = bootstrap.initialize()
            self.assertTrue(result)
            
            # Verify runtime state
            runtime = bootstrap.get_runtime_state()
            self.assertIsInstance(runtime, RuntimeState)
            
            # Verify staging-specific features
            self.assertFalse(runtime.is_feature_enabled("debug_mode"))
            self.assertFalse(runtime.is_feature_enabled("verbose_logging"))
            self.assertFalse(runtime.is_feature_enabled("mock_endpoints"))
            self.assertTrue(runtime.is_feature_enabled("audit_mode"))
            self.assertFalse(runtime.is_feature_enabled("high_security"))
    
    def test_bootstrap_production_tier(self):
        """Test bootstrap in production tier"""
        # Set up environment for production
        with patch.dict('os.environ', {
            "STRATUM_ENV": "production",
            "LIGHT_BOUNTY_KEY": "test-bounty-key",
            "LIGHT_CONFIG_KEY": "test-config-key",
            "CLOUD_DEPLOY_AUTH_AWS": "test-aws-auth",
            "CLOUD_DEPLOY_AUTH_AZURE": "test-azure-auth",
            "CLOUD_DEPLOY_AUTH_GCP": "test-gcp-auth",
            "SIEM_ENDPOINT": "https://prod-splunk.example.com",
            "LOG_LEVEL": "WARNING"
        }):
            # Import bootstrap modules
            from config.environment import env
            from bootstrap.logging import configure_logging
            from bootstrap.runtime import RuntimeState
            import bootstrap
            
            # Verify environment tier
            self.assertTrue(env.is_prod())
            self.assertEqual(env.get_tier(), EnvironmentTier.PRODUCTION)
            
            # Initialize bootstrap
            result = bootstrap.initialize()
            self.assertTrue(result)
            
            # Verify runtime state
            runtime = bootstrap.get_runtime_state()
            self.assertIsInstance(runtime, RuntimeState)
            
            # Verify production-specific features
            self.assertFalse(runtime.is_feature_enabled("debug_mode"))
            self.assertFalse(runtime.is_feature_enabled("verbose_logging"))
            self.assertFalse(runtime.is_feature_enabled("mock_endpoints"))
            self.assertTrue(runtime.is_feature_enabled("audit_mode"))
            self.assertTrue(runtime.is_feature_enabled("high_security"))
            self.assertFalse(runtime.is_feature_enabled("local_override"))
    
    def test_bootstrap_missing_required_env_vars(self):
        """Test bootstrap with missing required environment variables"""
        # Set up environment with missing required variables
        with patch.dict('os.environ', {
            "STRATUM_ENV": "production",
            # Missing LIGHT_BOUNTY_KEY
            "LIGHT_CONFIG_KEY": "test-config-key"
        }):
            # Import environment schema
            from config.environment import env
            
            # Verify environment validation fails
            with self.assertRaises(ValueError):
                env.get_env_context()
    
    def test_bootstrap_missing_tier_enforced_vars_in_production(self):
        """Test bootstrap with missing tier-enforced variables in production"""
        # Set up environment with missing tier-enforced variables
        with patch.dict('os.environ', {
            "STRATUM_ENV": "production",
            "LIGHT_BOUNTY_KEY": "test-bounty-key",
            "LIGHT_CONFIG_KEY": "test-config-key",
            # Missing CLOUD_DEPLOY_AUTH_AWS
            # Missing SIEM_ENDPOINT
        }):
            # Import environment schema
            from config.environment import env
            
            # Verify environment validation fails
            with self.assertRaises(ValueError):
                env.get_env_context()
    
    def test_logging_configuration_development(self):
        """Test logging configuration in development tier"""
        # Set up environment for development
        with patch.dict('os.environ', {
            "STRATUM_ENV": "development",
            "LIGHT_BOUNTY_KEY": "test-bounty-key",
            "LIGHT_CONFIG_KEY": "test-config-key",
            "LOG_LEVEL": "DEBUG"
        }):
            # Import environment schema
            from config.environment import env
            
            # Get environment context
            env_context = env.get_env_context()
            
            # Configure logging with file output
            env_context["logging"] = {
                "log_to_file": True,
                "log_path": self.log_path
            }
            
            # Import logging module
            from bootstrap.logging import configure_logging
            
            # Configure logging
            configure_logging(env_context)
            
            # Get logger
            logger = logging.getLogger("test")
            
            # Log test messages
            logger.debug("Debug message")
            logger.info("Info message")
            logger.warning("Warning message")
            logger.error("Error message")
            
            # Verify log file exists
            self.assertTrue(os.path.exists(self.log_path))
            
            # Read log file
            with open(self.log_path, "r") as f:
                log_content = f.read()
            
            # Verify log content
            self.assertIn("Debug message", log_content)
            self.assertIn("Info message", log_content)
            self.assertIn("Warning message", log_content)
            self.assertIn("Error message", log_content)
    
    def test_logging_configuration_production(self):
        """Test logging configuration in production tier"""
        # Set up environment for production
        with patch.dict('os.environ', {
            "STRATUM_ENV": "production",
            "LIGHT_BOUNTY_KEY": "test-bounty-key",
            "LIGHT_CONFIG_KEY": "test-config-key",
            "CLOUD_DEPLOY_AUTH_AWS": "test-aws-auth",
            "CLOUD_DEPLOY_AUTH_AZURE": "test-azure-auth",
            "CLOUD_DEPLOY_AUTH_GCP": "test-gcp-auth",
            "SIEM_ENDPOINT": "https://prod-splunk.example.com",
            "LOG_LEVEL": "INFO"
        }):
            # Import environment schema
            from config.environment import env
            
            # Get environment context
            env_context = env.get_env_context()
            
            # Configure logging with file output
            env_context["logging"] = {
                "log_to_file": True,
                "log_path": self.log_path
            }
            
            # Import logging module
            from bootstrap.logging import configure_logging
            
            # Configure logging
            configure_logging(env_context)
            
            # Get logger
            logger = logging.getLogger("test")
            
            # Log test messages
            logger.debug("Debug message")  # Should not be logged
            logger.info("Info message")
            logger.warning("Warning message")
            logger.error("Error message")
            
            # Verify log file exists
            self.assertTrue(os.path.exists(self.log_path))
            
            # Read log file
            with open(self.log_path, "r") as f:
                log_content = f.read()
            
            # Verify log content (JSON format in production)
            self.assertNotIn("Debug message", log_content)  # Debug should not be logged
            self.assertIn("Info message", log_content)
            self.assertIn("Warning message", log_content)
            self.assertIn("Error message", log_content)
            
            # Verify JSON format
            self.assertIn("{", log_content)
            self.assertIn("}", log_content)
    
    def test_sensitive_information_redaction(self):
        """Test sensitive information redaction in logs"""
        # Set up environment
        with patch.dict('os.environ', {
            "STRATUM_ENV": "development",
            "LIGHT_BOUNTY_KEY": "test-bounty-key",
            "LIGHT_CONFIG_KEY": "test-config-key"
        }):
            # Import environment schema
            from config.environment import env
            
            # Get environment context
            env_context = env.get_env_context()
            
            # Configure logging with file output
            env_context["logging"] = {
                "log_to_file": True,
                "log_path": self.log_path
            }
            
            # Import logging module
            from bootstrap.logging import configure_logging
            
            # Configure logging
            configure_logging(env_context)
            
            # Get logger
            logger = logging.getLogger("test")
            
            # Log sensitive information
            logger.info("API key=secret123")
            logger.info('{"password": "secret123"}')
            logger.info("token=abc123")
            
            # Verify log file exists
            self.assertTrue(os.path.exists(self.log_path))
            
            # Read log file
            with open(self.log_path, "r") as f:
                log_content = f.read()
            
            # Verify sensitive information is redacted
            self.assertIn("API key=[REDACTED]", log_content)
            self.assertIn('"password": "[REDACTED]"', log_content)
            self.assertIn("token=[REDACTED]", log_content)
            self.assertNotIn("secret123", log_content)
            self.assertNotIn("abc123", log_content)
    
    def test_runtime_state_management(self):
        """Test runtime state management"""
        # Set up environment
        with patch.dict('os.environ', {
            "STRATUM_ENV": "development",
            "LIGHT_BOUNTY_KEY": "test-bounty-key",
            "LIGHT_CONFIG_KEY": "test-config-key"
        }):
            # Import environment schema
            from config.environment import env
            
            # Get environment context
            env_context = env.get_env_context()
            
            # Import runtime module
            from bootstrap.runtime import RuntimeState
            
            # Create runtime state
            runtime = RuntimeState(env_context)
            
            # Test feature management
            runtime.set_feature("test_feature", True)
            self.assertTrue(runtime.is_feature_enabled("test_feature"))
            
            # Test state management
            runtime.set_state("test_key", "test_value")
            self.assertEqual(runtime.get_state("test_key"), "test_value")
            
            # Test module registration
            runtime.register_module("test_module")
            self.assertTrue(runtime.is_module_initialized("test_module"))
            
            # Test health management
            runtime.update_health("healthy")
            self.assertEqual(runtime.get_health()["status"], "healthy")
            
            # Test serialization
            state_dict = runtime.to_dict()
            self.assertIn("features", state_dict)
            self.assertIn("state", state_dict)
            self.assertIn("uptime", state_dict)
            
            # Test JSON serialization
            json_str = runtime.to_json()
            parsed = json.loads(json_str)
            self.assertIn("features", parsed)
            self.assertIn("state", parsed)
            self.assertIn("uptime", parsed)
    
    def test_bootstrap_core_module_loading(self):
        """Test core module loading in bootstrap"""
        # Mock core modules
        mock_modules = {
            "core.analyzer": MagicMock(),
            "core.prompt_engine": MagicMock(),
            "core.reporter": MagicMock(),
            "core.siem": MagicMock(),
            "core.deployer": MagicMock()
        }
        
        def mock_import_module(name):
            if name in mock_modules:
                return mock_modules[name]
            raise ImportError(f"No module named '{name}'")
        
        # Set up environment
        with patch.dict('os.environ', {
            "STRATUM_ENV": "development",
            "LIGHT_BOUNTY_KEY": "test-bounty-key",
            "LIGHT_CONFIG_KEY": "test-config-key"
        }), patch('importlib.import_module', side_effect=mock_import_module):
            # Import bootstrap
            import bootstrap
            
            # Initialize bootstrap
            result = bootstrap.initialize()
            self.assertTrue(result)
            
            # Verify core modules were loaded
            bootstrap_instance = bootstrap.bootstrap
            self.assertEqual(len(bootstrap_instance.core_modules), 5)
            
            # Verify module access
            for module_name in ["analyzer", "prompt_engine", "reporter", "siem", "deployer"]:
                module = bootstrap.get_core_module(module_name)
                self.assertIsNotNone(module)
    
    def test_bootstrap_tier_specific_initialization(self):
        """Test tier-specific initialization in bootstrap"""
        # Set up environment for each tier
        tiers = ["development", "staging", "production"]
        
        for tier in tiers:
            env_vars = {
                "STRATUM_ENV": tier,
                "LIGHT_BOUNTY_KEY": "test-bounty-key",
                "LIGHT_CONFIG_KEY": "test-config-key"
            }
            
            # Add tier-specific variables
            if tier in ["staging", "production"]:
                env_vars.update({
                    "CLOUD_DEPLOY_AUTH_AWS": "test-aws-auth",
                    "CLOUD_DEPLOY_AUTH_AZURE": "test-azure-auth",
                    "CLOUD_DEPLOY_AUTH_GCP": "test-gcp-auth",
                    "SIEM_ENDPOINT": f"https://{tier}-splunk.example.com"
                })
            
            with patch.dict('os.environ', env_vars), \
                 patch('importlib.import_module', return_value=MagicMock()):
                
                # Reload bootstrap module
                if 'bootstrap' in sys.modules:
                    del sys.modules['bootstrap']
                
                # Import bootstrap
                import bootstrap
                
                # Initialize bootstrap
                result = bootstrap.initialize()
                self.assertTrue(result)
                
                # Get runtime state
                runtime = bootstrap.get_runtime_state()
                
                # Verify tier-specific features
                if tier == "development":
                    self.assertTrue(runtime.is_feature_enabled("debug_mode"))
                    self.assertTrue(runtime.is_feature_enabled("mock_endpoints"))
                elif tier == "staging":
                    self.assertFalse(runtime.is_feature_enabled("debug_mode"))
                    self.assertFalse(runtime.is_feature_enabled("mock_endpoints"))
                    self.assertTrue(runtime.is_feature_enabled("audit_mode"))
                elif tier == "production":
                    self.assertFalse(runtime.is_feature_enabled("debug_mode"))
                    self.assertFalse(runtime.is_feature_enabled("mock_endpoints"))
                    self.assertTrue(runtime.is_feature_enabled("audit_mode"))
                    self.assertTrue(runtime.is_feature_enabled("high_security"))

if __name__ == "__main__":
    unittest.main()
