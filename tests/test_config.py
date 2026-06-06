#!/usr/bin/env python3
# Configuration Tests for STRATUM_LIGHT

import pytest
import os
import json
from unittest.mock import patch, mock_open, MagicMock
from cryptography.fernet import Fernet

# Import the module to test
from config.settings import ConfigManager, MainConfig # Import MainConfig for Pydantic
from pydantic import ValidationError # Import Pydantic's ValidationError

# Fixture to provide a base valid config dictionary that matches MainConfig structure
@pytest.fixture
def base_valid_config_dict():
    # This should mirror the structure expected by MainConfig, including defaults
    # where MainConfig defines them, or providing valid values.
    return {
        "models": ["g1", "g2"], "boost": 1.0,
        "bounty_endpoints": ["http://example.com/bounty"],
        "cvss_base": 7.0, "cvss_vector": "AV:N/AC:L",
        "siem_endpoint": "http://example.com/siem",
        "cloud_providers": ["test_cloud"],
        "logging": {"level": "DEBUG", "log_to_file": False, "log_path": "/tmp/test.log"},
        "api_bounty_endpoint": "http://example.com/api_bounty",
        "api_siem_endpoint": "http://example.com/api_siem",
        "default_model": "g1", "timeout": 60, "environment": "testing",
        "helper_llm": {
            "type": "none",
            "local_model_path": "", "local_model_type": "",
            "local_helper_max_tokens": 100, "local_helper_temperature": 0.0,
            "local_helper_llama_cpp_n_ctx": 1000, "local_helper_llama_cpp_n_gpu_layers": 0,
            "local_helper_llama_cpp_verbose": False, "local_helper_llama_cpp_args": "",
            "remote_api_endpoint": None, # Correctly None if not set, Pydantic HttpUrl is Optional
            "remote_api_key": "", "remote_api_timeout": 20,
        },
        "target_model_sdk": {
            "api_endpoint": None, "api_key": "",
            "local_target_max_tokens": 100, "local_target_temperature": 0.5,
            "local_target_llama_cpp_n_ctx": 1000, "local_target_llama_cpp_n_gpu_layers": 0,
            "local_target_llama_cpp_verbose": False,
        }
    }


@pytest.mark.unit
def test_config_initialization(base_valid_config_dict):
    """Test ConfigManager initialization with default values"""
    # Mock _load_and_merge_configs to return a dictionary that would be the result of all loading steps
    # This isolates testing of the Pydantic validation part within __init__
    with patch.object(ConfigManager, '_load_and_merge_configs', return_value=base_valid_config_dict):
        config_manager = ConfigManager() # This will now use base_valid_config_dict and try to validate it
            
        # Check that _config now holds the Pydantic model's dict representation (type-coerced)
        assert isinstance(config_manager._config, dict)
        assert config_manager._config["models"] == ["g1", "g2"] # From base_valid_config_dict
        assert config_manager._config["boost"] == 1.0       # From base_valid_config_dict
        assert config_manager._config["logging"]["level"] == "DEBUG" # From base_valid_config_dict
        assert config_manager._validated_config is not None # Ensure Pydantic model was created
        assert isinstance(config_manager._validated_config, MainConfig)

@pytest.mark.unit
def test_config_get_method(base_valid_config_dict):
    """Test the get method of ConfigManager after Pydantic validation."""
    with patch.object(ConfigManager, '_load_and_merge_configs', return_value=base_valid_config_dict):
        config_manager = ConfigManager()
            
        assert config_manager.get("models") == ["g1", "g2"]
        assert config_manager.get("helper_llm.type") == "none"
        assert config_manager.get("helper_llm.local_helper_max_tokens") == 100 # Type coerced by Pydantic
        assert config_manager.get("logging.log_to_file") is False # Type coerced
            
        assert config_manager.get("nonexistent", "default_value") == "default_value"
        assert config_manager.get("nonexistent") is None

@pytest.mark.unit
def test_config_dict_access(base_valid_config_dict):
    """Test dictionary-style access to ConfigManager"""
    with patch('os.getenv') as mock_getenv:
        mock_getenv.return_value = None
        with patch('os.path.exists') as mock_exists:
            mock_exists.return_value = False
            config_manager = ConfigManager()
            
            # Test __getitem__
            assert config_manager["models"] == ["gpt2", "llama", "grok"]
            
            # Test __contains__
            assert "models" in config_manager
            assert "nonexistent" not in config_manager

@pytest.mark.unit
def test_config_update():
    """Test updating configuration values"""
    with patch('os.getenv') as mock_getenv:
        mock_getenv.return_value = None
        with patch('os.path.exists') as mock_exists:
            mock_exists.return_value = False
            config_manager = ConfigManager()
            
            # Update existing key
            config_manager.update_config({"boost": 2.0})
            assert config_manager["boost"] == 2.0
            
            # Add new key
            config_manager.update_config({"new_key": "new_value"})
            assert config_manager["new_key"] == "new_value"

@pytest.mark.unit
def test_config_encrypted_loading():
    """Test loading configuration from encrypted file"""
    # Generate a test key
    test_key = Fernet.generate_key()
    cipher = Fernet(test_key)
    
    # Create encrypted test config based on a subset of base_valid_config_dict for simplicity
    # Pydantic validation will run on the merged result.
    test_file_config = {
        "models": ["test_model_from_file"], # Overrides default
        "boost": 3.0,
        "helper_llm": { # Partially override helper_llm
            "type": "local",
            "local_model_path": "/file/path.gguf"
            # Other helper_llm fields will come from defaults in MainConfig or default_config
        }
    }
    encrypted_config = cipher.encrypt(json.dumps(test_file_config).encode())
    
    # Mock os.getenv for LIGHT_CONFIG_KEY, others return None to use defaults
    def mock_getenv_for_encryption(key, default=None):
        if key == "LIGHT_CONFIG_KEY":
            return test_key.decode()
        # For other env vars, return None so they don't override test_file_config or defaults
        return None

    with patch('os.getenv', side_effect=mock_getenv_for_encryption):
        with patch('os.path.exists') as mock_exists: # Ensure only encrypted file 'exists'
            mock_exists.side_effect = lambda path: ".enc" in path
            with patch('builtins.open', mock_open(read_data=encrypted_config)):
                # ConfigManager will load defaults, then merge this file config, then env vars (none in this test for simplicity)
                # Then Pydantic validation runs.
                config_manager = ConfigManager()
                
                # Check values: some from file, some from defaults (via Pydantic model if not in file)
                assert config_manager.get("models") == ["test_model_from_file"] # From file
                assert config_manager.get("boost") == 3.0 # From file
                assert config_manager.get("helper_llm.type") == "local" # From file
                assert config_manager.get("helper_llm.local_model_path") == "/file/path.gguf" # From file
                # This default comes from Pydantic model default if not in file or default_config dict
                assert config_manager.get("helper_llm.local_helper_max_tokens") == 256
                assert config_manager.get("logging.level") == "INFO" # From default_config in settings.py via Pydantic
                assert config_manager.get("cvss_base") == 9.0 # From default_config

@pytest.mark.unit
def test_config_env_override_type_coercion(base_valid_config_dict):
    """Test environment variable overrides with Pydantic type coercion."""
    # Start with a base valid config
    initial_merged_config = base_valid_config_dict.copy()

    # Simulate environment variables that will override parts of initial_merged_config
    # These will be processed by _apply_env_overrides and then by Pydantic
    mock_env_vars = {
        "STRATUM_BOOST": "2.5", # string -> float
        "STRATUM_TIMEOUT": "45",  # string -> int
        "STRATUM_LOGGING__LOG_TO_FILE": "false", # string -> bool
        "STRATUM_HELPER_LLM__TYPE": "remote_api", # string -> Literal
        "STRATUM_HELPER_LLM__REMOTE_API_ENDPOINT": "http://new.remote.api", # string -> HttpUrl
        "STRATUM_HELPER_LLM__REMOTE_API_TIMEOUT": "25" # string -> int
    }

    with patch.dict(os.environ, mock_env_vars, clear=True): # Temporarily set os.environ
        # We want ConfigManager to go through its full load, merge, env_override, and Pydantic validation
        # So, we don't mock _load_and_merge_configs directly if we want to test env var parsing.
        # Instead, we ensure default_config is used and no files are loaded.
        with patch('os.path.exists', return_value=False): # No config files exist
            # The ConfigManager will build its config from defaults then apply our mocked env vars
            config_manager = ConfigManager()

            assert config_manager.get("boost") == 2.5
            assert isinstance(config_manager.get("boost"), float)
            assert config_manager.get("timeout") == 45
            assert isinstance(config_manager.get("timeout"), int)
            assert config_manager.get("logging.log_to_file") is False
            assert isinstance(config_manager.get("logging.log_to_file"), bool)
            assert config_manager.get("helper_llm.type") == "remote_api"
            assert str(config_manager.get("helper_llm.remote_api_endpoint")) == "http://new.remote.api/" # Pydantic HttpUrl adds trailing /
            assert config_manager.get("helper_llm.remote_api_timeout") == 25

@pytest.mark.unit
def test_pydantic_validation_failure_missing_field(base_valid_config_dict):
    """Test that Pydantic validation fails if a required field (hypothetically) is missing."""
    # To test this, we'd need a Pydantic model where a field is truly required (no default)
    # Our current MainConfig has defaults for most things. Let's make 'models' missing.
    invalid_config_data = base_valid_config_dict.copy()
    del invalid_config_data["models"] # 'models' is required by MainConfig (List[str])

    with patch.object(ConfigManager, '_load_and_merge_configs', return_value=invalid_config_data):
        with pytest.raises(SystemExit) as exc_info:
            ConfigManager()
        assert "Configuration validation failed!" in str(exc_info.value) # Check SystemExit message or logged critical
        # Further checks could be done on logged messages if log capture is set up

@pytest.mark.unit
def test_pydantic_validation_failure_wrong_type(base_valid_config_dict):
    """Test Pydantic validation failure due to wrong data type that Pydantic can't coerce."""
    invalid_config_data = base_valid_config_dict.copy()
    invalid_config_data["boost"] = "not-a-float" # boost is float
    invalid_config_data["helper_llm"]["local_helper_max_tokens"] = "not-an-int"

    with patch.object(ConfigManager, '_load_and_merge_configs', return_value=invalid_config_data):
        with pytest.raises(SystemExit) as exc_info:
            ConfigManager()
        # Pydantic's error messages can be quite detailed. We check that SystemExit was raised.
        # Specific error messages can be checked if log capture is added to the test.
        assert "Configuration validation failed!" in str(exc_info.value)

@pytest.mark.unit
def test_pydantic_validation_failure_literal_constraint(base_valid_config_dict):
    """Test Pydantic validation failure due to Literal constraint violation."""
    invalid_config_data = base_valid_config_dict.copy()
    invalid_config_data["helper_llm"]["type"] = "invalid_type" # Must be 'none', 'local', or 'remote_api'

    with patch.object(ConfigManager, '_load_and_merge_configs', return_value=invalid_config_data):
        with pytest.raises(SystemExit) as exc_info:
            ConfigManager()
        assert "Configuration validation failed!" in str(exc_info.value)

@pytest.mark.unit
def test_pydantic_validation_httpurl_failure(base_valid_config_dict):
    """Test Pydantic HttpUrl validation failure."""
    invalid_config_data = base_valid_config_dict.copy()
    invalid_config_data["helper_llm"]["type"] = "remote_api"
    invalid_config_data["helper_llm"]["remote_api_endpoint"] = "not_a_valid_url"

    with patch.object(ConfigManager, '_load_and_merge_configs', return_value=invalid_config_data):
        with pytest.raises(SystemExit) as exc_info:
            ConfigManager()
        assert "Configuration validation failed!" in str(exc_info.value)
        # Can check logs for "Input should be a valid URL"

@pytest.mark.unit
def test_config_save():
    """Test saving configuration to encrypted file"""
    # Generate a test key
    test_key = Fernet.generate_key()
    
    with patch('os.getenv') as mock_getenv:
        mock_getenv.return_value = test_key.decode()
        with patch('os.path.exists') as mock_exists:
            mock_exists.return_value = False
            with patch('builtins.open', mock_open()) as mock_file:
                config_manager = ConfigManager()
                
                # Save config
                result = config_manager.save_config()
                
                # Check result
                assert result is True
                
                # Verify file was written
                mock_file.assert_called_once()
                
                # Verify write was called
                mock_file().write.assert_called_once()

@pytest.mark.unit
def test_config_save_without_key():
    """Test saving configuration without encryption key"""
    with patch('os.getenv') as mock_getenv:
        mock_getenv.return_value = None
        with patch('os.path.exists') as mock_exists:
            mock_exists.return_value = False
            config_manager = ConfigManager()
            
            # Try to save without key
            result = config_manager.save_config()
            
            # Should fail
            assert result is False
