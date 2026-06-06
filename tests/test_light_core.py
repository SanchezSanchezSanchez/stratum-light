import pytest
from unittest.mock import patch, MagicMock, ANY
from core.light_core import LightCore
from core.analyzer import PromptInjectionAnalyzer
from core.llm_interface import LocalLLMAdapter, RemoteAPILLMAdapter, HelperLLMInterface
from config.settings import ConfigManager # To mock the global 'config' object

# --- Fixtures ---

@pytest.fixture
def mock_config_manager_instance():
    """Mocks the global 'config' object (instance of ConfigManager)."""
    mock_config_data = {
        "models": ["gpt2", "test_model"],
        "helper_llm": { # Default to no helper
            "type": "none",
        },
        "target_model_sdk": { # Default empty target SDK
            "api_endpoint": "",
            "api_key": ""
        }
    }

    # Create a MagicMock that can behave like the ConfigManager instance
    mock_instance = MagicMock(spec=ConfigManager)

    # Configure the mock's get method to return values from mock_config_data
    # This needs to handle nested gets like config.get("helper_llm.type")
    def side_effect_get(key_path, default=None):
        parts = key_path.split('.')
        value = mock_config_data
        try:
            for part in parts:
                value = value[part]
            return value
        except KeyError:
            return default

    mock_instance.get.side_effect = side_effect_get
    # Allow direct dictionary-like access if LightCore uses it (it does for self.config.get)
    mock_instance.__getitem__.side_effect = lambda key: mock_config_data[key]

    return mock_instance, mock_config_data # Return data for easy modification in tests

# --- Test Cases ---

class TestLightCoreInitialization:

    @patch('core.light_core.PromptInjectionAnalyzer') # Patch PIA constructor
    @patch('core.light_core.RemoteAPILLMAdapter')   # Patch Remote Adapter constructor
    @patch('core.light_core.LocalLLMAdapter')      # Patch Local Adapter constructor
    def test_init_no_helper_llm(self, MockLocalLLMAdapter, MockRemoteAPILLMAdapter, MockPIA, mock_config_manager_instance):
        """Test LightCore init when helper_llm.type is 'none'."""
        mock_config, _ = mock_config_manager_instance
        with patch('core.light_core.config', mock_config): # Replace global config with our mock
            core = LightCore()
            MockLocalLLMAdapter.assert_not_called()
            MockRemoteAPILLMAdapter.assert_not_called()
            MockPIA.assert_called_once_with(helper_llm=None, config=mock_config)
            assert isinstance(core.prompt_injection_analyzer, MagicMock) # It's the mocked PIA

    @patch('core.light_core.PromptInjectionAnalyzer')
    @patch('core.light_core.RemoteAPILLMAdapter')
    @patch('core.light_core.LocalLLMAdapter')
    def test_init_with_local_helper_llm(self, MockLocalLLMAdapter, MockRemoteAPILLMAdapter, MockPIA, mock_config_manager_instance):
        """Test LightCore init with local helper_llm."""
        mock_config, mock_config_data = mock_config_manager_instance
        mock_config_data["helper_llm"] = {
            "type": "local",
            "local_model_path": "/path/to/local.gguf",
            "local_model_type": "gguf"
        }

        mock_local_adapter_instance = MockLocalLLMAdapter.return_value

        with patch('core.light_core.config', mock_config):
            core = LightCore()
            MockLocalLLMAdapter.assert_called_once_with(config=mock_config_data["helper_llm"])
            MockRemoteAPILLMAdapter.assert_not_called()
            MockPIA.assert_called_once_with(helper_llm=mock_local_adapter_instance, config=mock_config)

    @patch('core.light_core.PromptInjectionAnalyzer')
    @patch('core.light_core.RemoteAPILLMAdapter')
    @patch('core.light_core.LocalLLMAdapter')
    def test_init_with_remote_helper_llm(self, MockLocalLLMAdapter, MockRemoteAPILLMAdapter, MockPIA, mock_config_manager_instance):
        """Test LightCore init with remote_api helper_llm."""
        mock_config, mock_config_data = mock_config_manager_instance
        mock_config_data["helper_llm"] = {
            "type": "remote_api",
            "remote_api_endpoint": "http://remote.api",
            "remote_api_key": "key123"
        }

        mock_remote_adapter_instance = MockRemoteAPILLMAdapter.return_value

        with patch('core.light_core.config', mock_config):
            core = LightCore()
            MockLocalLLMAdapter.assert_not_called()
            MockRemoteAPILLMAdapter.assert_called_once_with(config=mock_config_data["helper_llm"])
            MockPIA.assert_called_once_with(helper_llm=mock_remote_adapter_instance, config=mock_config)

    @patch('core.light_core.PromptInjectionAnalyzer')
    @patch('core.light_core.RemoteAPILLMAdapter')
    @patch('core.light_core.LocalLLMAdapter')
    def test_init_with_invalid_helper_llm_type(self, MockLocalLLMAdapter, MockRemoteAPILLMAdapter, MockPIA, mock_config_manager_instance):
        """Test LightCore init with an invalid helper_llm type."""
        mock_config, mock_config_data = mock_config_manager_instance
        mock_config_data["helper_llm"] = {"type": "unknown_type"}

        with patch('core.light_core.config', mock_config):
            core = LightCore() # Should log a warning
            MockLocalLLMAdapter.assert_not_called()
            MockRemoteAPILLMAdapter.assert_not_called()
            MockPIA.assert_called_once_with(helper_llm=None, config=mock_config) # Falls back to no helper

    @patch('core.light_core.PromptInjectionAnalyzer')
    @patch('core.light_core.RemoteAPILLMAdapter', side_effect=Exception("Remote Adapter Failed"))
    @patch('core.light_core.LocalLLMAdapter')
    def test_init_helper_llm_adapter_fails_to_init(self, MockLocalLLMAdapter, MockRemoteAPILLMAdapter, MockPIA, mock_config_manager_instance):
        """Test LightCore init when a configured adapter fails to initialize."""
        mock_config, mock_config_data = mock_config_manager_instance
        mock_config_data["helper_llm"] = {"type": "remote_api", "remote_api_endpoint": "http://remote.api"} # Configured for remote

        with patch('core.light_core.config', mock_config):
            core = LightCore() # RemoteAPILLMAdapter constructor will raise an exception
            MockLocalLLMAdapter.assert_not_called()
            MockRemoteAPILLMAdapter.assert_called_once() # Attempted to init
            # PIA should still be initialized, but with helper_llm=None due to adapter failure
            MockPIA.assert_called_once_with(helper_llm=None, config=mock_config)


class TestLightCoreAnalyzePromptInjection:

    @patch('core.light_core.PromptInjectionAnalyzer') # Mock PIA class
    def test_analyze_prompt_injection_passes_params_correctly(self, MockPIAClass, mock_config_manager_instance):
        """Test that analyze_prompt_injection passes params correctly to PIA."""
        mock_config, mock_config_data = mock_config_manager_instance
        # Setup specific target SDK config for this test
        mock_config_data["target_model_sdk"] = {
            "api_endpoint": "http://target.api/specific",
            "api_key": "target_key_123"
        }
        mock_config_data["helper_llm"]["type"] = "none" # No helper for simplicity here

        # Mock the instance of PIA that LightCore creates
        mock_pia_instance = MockPIAClass.return_value
        mock_pia_instance.detect_injection.return_value = {"result": "mocked_analysis"}

        with patch('core.light_core.config', mock_config):
            core = LightCore()

            # Ensure the PIA instance on core is the one we want to check calls on
            core.prompt_injection_analyzer = mock_pia_instance

            result = core.analyze_prompt_injection(
                target_model_name="test_target",
                prompt_to_test="the prompt",
                auxiliary_prompts=["aux1"]
            )

            assert result == {"result": "mocked_analysis"}
            mock_pia_instance.detect_injection.assert_called_once_with(
                target_model_name="test_target",
                prompt_to_test="the prompt",
                auxiliary_prompts=["aux1"],
                target_model_api_key="target_key_123",
                target_model_api_endpoint="http://target.api/specific"
            )

    @patch('core.light_core.PromptInjectionAnalyzer')
    def test_analyze_prompt_injection_default_target_sdk(self, MockPIAClass, mock_config_manager_instance):
        """Test with default (empty) target SDK config."""
        mock_config, mock_config_data = mock_config_manager_instance
        # Ensure target_model_sdk is default (empty strings)
        mock_config_data["target_model_sdk"] = {"api_endpoint": "", "api_key": ""}
        mock_config_data["helper_llm"]["type"] = "none"

        mock_pia_instance = MockPIAClass.return_value
        mock_pia_instance.detect_injection.return_value = {"result": "default_sdk_analysis"}

        with patch('core.light_core.config', mock_config):
            core = LightCore()
            core.prompt_injection_analyzer = mock_pia_instance

            core.analyze_prompt_injection(target_model_name="another_target", prompt_to_test="another prompt")

            mock_pia_instance.detect_injection.assert_called_once_with(
                target_model_name="another_target",
                prompt_to_test="another prompt",
                auxiliary_prompts=None, # Default for aux_prompts
                target_model_api_key="", # From default config
                target_model_api_endpoint="" # From default config
            )

    def test_analyze_prompt_injection_pia_not_init_graceful_error(self, mock_config_manager_instance):
        """Test graceful error if PIA somehow wasn't initialized."""
        mock_config, _ = mock_config_manager_instance
        with patch('core.light_core.config', mock_config):
            core = LightCore()
            core.prompt_injection_analyzer = None # Simulate PIA not being initialized

            result = core.analyze_prompt_injection("test", "prompt")
            assert result['error'] == "PromptInjectionAnalyzer not initialized."
            assert result['injection_detected'] is False

    @patch('core.light_core.PromptInjectionAnalyzer')
    def test_analyze_prompt_injection_missing_target_endpoint_for_remote_helper(self, MockPIAClass, mock_config_manager_instance):
        """
        Test scenario: Remote helper is used, which needs to call a remote target model,
        but the target_model_sdk.api_endpoint is missing.
        The error should originate from the RemoteAPILLMAdapter.get_target_model_output
        and be caught by PromptInjectionAnalyzer.
        """
        mock_config, mock_config_data = mock_config_manager_instance
        mock_config_data["helper_llm"] = { # Configure a remote helper
            "type": "remote_api",
            "remote_api_endpoint": "http://helper.api",
            "remote_api_key": "helper_key"
        }
        mock_config_data["target_model_sdk"] = { # Missing api_endpoint for target
            "api_endpoint": "",
            "api_key": "target_key"
        }

        # We need to mock the actual PIA instance and its detect_injection method
        # to simulate the error it would return if its helper_llm failed.
        # This tests LightCore's parameter passing more than PIA's internal error handling here.
        # For this specific test, we assume LightCore correctly instantiates RemoteAPILLMAdapter,
        # and that adapter, when called by PIA's detect_injection, would fail due to missing target endpoint.
        # So, PIA's detect_injection would then return an error.

        # Let's mock what detect_injection would return in such a scenario
        # based on PromptInjectionAnalyzer's logic when helper_llm.get_target_model_output fails.
        expected_pia_error_response = {
            'injection_detected': False, # Or based on phrase
            'confidence_score': 0.1,    # Or based on phrase
            'explanation': "Phrase-based: No common injection phrases detected. LLM-based: Orchestration error: ValueError('api_endpoint must be provided for the target model when using RemoteAPILLMAdapter.').",
            'error': "ValueError('api_endpoint must be provided for the target model when using RemoteAPILLMAdapter.')"
        }

        # Mock the PromptInjectionAnalyzer instance that LightCore will create and use
        mock_pia_instance = MagicMock(spec=PromptInjectionAnalyzer)
        mock_pia_instance.detect_injection.return_value = expected_pia_error_response
        MockPIAClass.return_value = mock_pia_instance # Ensure LightCore uses this instance

        with patch('core.light_core.config', mock_config):
            # We also need to patch the RemoteAPILLMAdapter so LightCore can initialize it
            # This adapter instance is then passed to the (mocked) PIAClass
            with patch('core.light_core.RemoteAPILLMAdapter') as MockedRemoteAdapter:
                core = LightCore()
                # Ensure the mocked PIA instance is on core for the call
                # This is a bit redundant if MockPIAClass.return_value is set, but makes it explicit
                core.prompt_injection_analyzer = mock_pia_instance

                result = core.analyze_prompt_injection(
                    target_model_name="remote_target_model",
                    prompt_to_test="a test prompt"
                )

                # Verify that detect_injection was called with the (missing) endpoint
                mock_pia_instance.detect_injection.assert_called_once_with(
                    target_model_name="remote_target_model",
                    prompt_to_test="a test prompt",
                    auxiliary_prompts=None,
                    target_model_api_key="target_key",
                    target_model_api_endpoint="" # Empty endpoint passed from config
                )

                # Check that the result from LightCore matches what PIA would return with such an error
                assert result['error'] is not None
                assert "api_endpoint must be provided" in result['error']
                assert "LLM-based: Orchestration error" in result['explanation']
                assert result['injection_detected'] == expected_pia_error_response['injection_detected']
