#!/usr/bin/env python3
# Environment Schema Test Module for STRATUM_LIGHT

import os
import pytest
from unittest.mock import patch
import logging
from config.environment import EnvironmentSchema, EnvironmentTier, ValidationLevel

# Test environment tier detection
def test_environment_tier_detection():
    # Test development tier detection
    with patch.dict(os.environ, {"STRATUM_ENV": "development"}):
        env = EnvironmentSchema()
        assert env.is_dev() is True
        assert env.is_staging() is False
        assert env.is_prod() is False
        assert env.get_tier() == EnvironmentTier.DEVELOPMENT
    
    # Test staging tier detection
    with patch.dict(os.environ, {"STRATUM_ENV": "staging"}):
        env = EnvironmentSchema()
        assert env.is_dev() is False
        assert env.is_staging() is True
        assert env.is_prod() is False
        assert env.get_tier() == EnvironmentTier.STAGING
    
    # Test production tier detection
    with patch.dict(os.environ, {"STRATUM_ENV": "production"}):
        env = EnvironmentSchema()
        assert env.is_dev() is False
        assert env.is_staging() is False
        assert env.is_prod() is True
        assert env.get_tier() == EnvironmentTier.PRODUCTION
    
    # Test alias detection
    with patch.dict(os.environ, {"STRATUM_ENV": "dev"}):
        env = EnvironmentSchema()
        assert env.is_dev() is True
    
    with patch.dict(os.environ, {"STRATUM_ENV": "prod"}):
        env = EnvironmentSchema()
        assert env.is_prod() is True
    
    # Test default to development
    with patch.dict(os.environ, {"STRATUM_ENV": "unknown"}):
        env = EnvironmentSchema()
        assert env.is_dev() is True

# Test required variable validation
def test_required_variable_validation():
    # Test missing required variable
    with patch.dict(os.environ, {
        "STRATUM_ENV": "development",
        # Missing LIGHT_BOUNTY_KEY
        "LIGHT_CONFIG_KEY": "test-key"
    }):
        with pytest.raises(ValueError) as excinfo:
            env = EnvironmentSchema()
        assert "Required environment variable LIGHT_BOUNTY_KEY is missing" in str(excinfo.value)
    
    # Test all required variables present
    with patch.dict(os.environ, {
        "STRATUM_ENV": "development",
        "LIGHT_BOUNTY_KEY": "test-bounty-key",
        "LIGHT_CONFIG_KEY": "test-config-key"
    }):
        env = EnvironmentSchema()
        assert env["bounty_key"] == "test-bounty-key"
        assert env["config_key"] == "test-config-key"

# Test tier-enforced variable validation
def test_tier_enforced_variable_validation():
    # Test missing tier-enforced variable in development (should pass)
    with patch.dict(os.environ, {
        "STRATUM_ENV": "development",
        "LIGHT_BOUNTY_KEY": "test-bounty-key",
        "LIGHT_CONFIG_KEY": "test-config-key"
        # Missing CLOUD_DEPLOY_AUTH_AWS
    }):
        env = EnvironmentSchema()
        assert env.get("cloud.aws") is None
    
    # Test missing tier-enforced variable in production (should fail)
    with patch.dict(os.environ, {
        "STRATUM_ENV": "production",
        "LIGHT_BOUNTY_KEY": "test-bounty-key",
        "LIGHT_CONFIG_KEY": "test-config-key"
        # Missing CLOUD_DEPLOY_AUTH_AWS
    }):
        with pytest.raises(ValueError) as excinfo:
            env = EnvironmentSchema()
        assert "Required environment variable CLOUD_DEPLOY_AUTH_AWS is missing" in str(excinfo.value)
    
    # Test all tier-enforced variables present in production
    with patch.dict(os.environ, {
        "STRATUM_ENV": "production",
        "LIGHT_BOUNTY_KEY": "test-bounty-key",
        "LIGHT_CONFIG_KEY": "test-config-key",
        "CLOUD_DEPLOY_AUTH_AWS": "test-aws-auth",
        "CLOUD_DEPLOY_AUTH_AZURE": "test-azure-auth",
        "CLOUD_DEPLOY_AUTH_GCP": "test-gcp-auth",
        "SIEM_ENDPOINT": "https://prod-splunk.example.com"
    }):
        env = EnvironmentSchema()
        assert env["cloud"]["aws"] == "test-aws-auth"
        assert env["cloud"]["azure"] == "test-azure-auth"
        assert env["cloud"]["gcp"] == "test-gcp-auth"
        assert env["siem_endpoint"] == "https://prod-splunk.example.com"

# Test soft-required variable validation
def test_soft_required_variable_validation(caplog):
    caplog.set_level(logging.WARNING)
    
    # Test missing soft-required variable
    with patch.dict(os.environ, {
        "STRATUM_ENV": "development",
        "LIGHT_BOUNTY_KEY": "test-bounty-key",
        "LIGHT_CONFIG_KEY": "test-config-key"
        # Missing LOG_LEVEL
    }):
        env = EnvironmentSchema()
        assert "Soft-required environment variable LOG_LEVEL is missing" in caplog.text
        assert env["log_level"] == "INFO"  # Default value
    
    # Test soft-required variable present
    with patch.dict(os.environ, {
        "STRATUM_ENV": "development",
        "LIGHT_BOUNTY_KEY": "test-bounty-key",
        "LIGHT_CONFIG_KEY": "test-config-key",
        "LOG_LEVEL": "DEBUG"
    }):
        env = EnvironmentSchema()
        assert env["log_level"] == "DEBUG"

# Test optional variable validation
def test_optional_variable_validation():
    # Test missing optional variable
    with patch.dict(os.environ, {
        "STRATUM_ENV": "development",
        "LIGHT_BOUNTY_KEY": "test-bounty-key",
        "LIGHT_CONFIG_KEY": "test-config-key"
        # Missing DEBUG_MODE
    }):
        env = EnvironmentSchema()
        assert env["debug"] is False  # Default value
    
    # Test optional variable present
    with patch.dict(os.environ, {
        "STRATUM_ENV": "development",
        "LIGHT_BOUNTY_KEY": "test-bounty-key",
        "LIGHT_CONFIG_KEY": "test-config-key",
        "DEBUG_MODE": "true"
    }):
        env = EnvironmentSchema()
        assert env["debug"] is True

# Test environment context structure
def test_environment_context_structure():
    with patch.dict(os.environ, {
        "STRATUM_ENV": "development",
        "LIGHT_BOUNTY_KEY": "test-bounty-key",
        "LIGHT_CONFIG_KEY": "test-config-key",
        "DEBUG_MODE": "true",
        "CLOUD_DEPLOY_AUTH_AWS": "test-aws-auth"
    }):
        env = EnvironmentSchema()
        context = env.get_env_context()
        
        # Check top-level structure
        assert context["env"] == "development"
        assert context["tier"] == EnvironmentTier.DEVELOPMENT
        assert context["debug"] is True
        assert context["bounty_key"] == "test-bounty-key"
        assert context["config_key"] == "test-config-key"
        
        # Check nested structure
        assert "cloud" in context
        assert context["cloud"]["aws"] == "test-aws-auth"
        assert context["cloud"]["azure"] is None
        assert context["cloud"]["gcp"] is None

# Test sensitive value redaction
def test_sensitive_value_redaction():
    with patch.dict(os.environ, {
        "STRATUM_ENV": "development",
        "LIGHT_BOUNTY_KEY": "test-bounty-key",
        "LIGHT_CONFIG_KEY": "test-config-key",
        "CLOUD_DEPLOY_AUTH_AWS": "test-aws-auth"
    }):
        env = EnvironmentSchema()
        
        # Get redacted dict
        redacted = env.to_dict(redact_sensitive=True)
        
        # Check redacted values
        assert redacted["bounty_key"] == "[REDACTED]"
        assert redacted["config_key"] == "[REDACTED]"
        assert redacted["cloud"]["aws"] == "[REDACTED]"
        
        # Check non-redacted values
        assert redacted["env"] == "development"
        assert redacted["debug"] is False
        
        # Get non-redacted dict
        non_redacted = env.to_dict(redact_sensitive=False)
        
        # Check non-redacted values
        assert non_redacted["bounty_key"] == "test-bounty-key"
        assert non_redacted["config_key"] == "test-config-key"
        assert non_redacted["cloud"]["aws"] == "test-aws-auth"

# Test tier-specific behavior
def test_tier_specific_behavior():
    # Test development tier behavior
    with patch.dict(os.environ, {
        "STRATUM_ENV": "development",
        "LIGHT_BOUNTY_KEY": "test-bounty-key",
        "LIGHT_CONFIG_KEY": "test-config-key",
        "LOG_LEVEL": "INFO"  # Should be overridden to DEBUG in development
    }):
        env = EnvironmentSchema()
        assert env["log_level"] == "DEBUG"
    
    # Test production tier behavior with development endpoint (should fail)
    with patch.dict(os.environ, {
        "STRATUM_ENV": "production",
        "LIGHT_BOUNTY_KEY": "test-bounty-key",
        "LIGHT_CONFIG_KEY": "test-config-key",
        "CLOUD_DEPLOY_AUTH_AWS": "test-aws-auth",
        "CLOUD_DEPLOY_AUTH_AZURE": "test-azure-auth",
        "CLOUD_DEPLOY_AUTH_GCP": "test-gcp-auth",
        "SIEM_ENDPOINT": "https://dev-splunk.example.com"  # Development endpoint in production
    }):
        with pytest.raises(ValueError) as excinfo:
            env = EnvironmentSchema()
        assert "Cannot use development endpoint" in str(excinfo.value)

# Test example .env generation
def test_env_example_generation():
    with patch.dict(os.environ, {
        "STRATUM_ENV": "development",
        "LIGHT_BOUNTY_KEY": "test-bounty-key",
        "LIGHT_CONFIG_KEY": "test-config-key"
    }):
        env = EnvironmentSchema()
        
        # Generate example for development
        dev_example = env.generate_env_example(EnvironmentTier.DEVELOPMENT)
        assert "STRATUM_ENV=development" in dev_example
        assert "LIGHT_BOUNTY_KEY=your-secret-here  # REQUIRED" in dev_example
        
        # Generate example for production
        prod_example = env.generate_env_example(EnvironmentTier.PRODUCTION)
        assert "STRATUM_ENV=production" in prod_example
        assert "CLOUD_DEPLOY_AUTH_AWS=your-secret-here  # REQUIRED" in prod_example

# Test schema documentation generation
def test_schema_documentation_generation():
    with patch.dict(os.environ, {
        "STRATUM_ENV": "development",
        "LIGHT_BOUNTY_KEY": "test-bounty-key",
        "LIGHT_CONFIG_KEY": "test-config-key"
    }):
        env = EnvironmentSchema()
        
        # Generate documentation
        docs = env.generate_schema_documentation()
        assert "# STRATUM_LIGHT Environment Schema" in docs
        assert "## Environment Tiers" in docs
        assert "## Validation Levels" in docs
        assert "## Environment Variables" in docs
        assert "## Tier-Specific Requirements" in docs
        assert "## Runtime Behavior" in docs
        assert "## Usage Examples" in docs
