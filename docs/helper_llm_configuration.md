# Helper LLM & Target Model Configuration Guide

The `PromptInjectionAnalyzer` in Stratum Light can leverage a "helper LLM" for advanced behavioral analysis, in addition to its built-in phrase-based checks. This guide details how to configure this helper LLM and any necessary parameters for the *target model* (the model being analyzed).

All configurations can be set via environment variables (recommended for secrets) or by placing them in your `light_config.json.enc` / `light_config.json` file (see `config/settings.py` for structure). Environment variables take precedence. **On application startup, these configurations are validated for structure and basic types (e.g., ensuring numbers are numbers, URLs are valid format if specified as such); critical errors will halt startup with informative messages.**

## 1. Configuring the Helper LLM

The helper LLM is used by `PromptInjectionAnalyzer` to assess if a target model's output in response to a prompt seems manipulated or ignores prior instructions.

### 1.1. Helper LLM Type

**Variable:** `STRATUM_HELPER_LLM_TYPE`
**Default:** `"none"`

This setting determines which type of helper LLM backend to use.

*   **`"none"`:** (Default) Disables the LLM-based behavioral analysis. `PromptInjectionAnalyzer` will only perform its standard phrase-based checks.
*   **`"local"`:** Uses a locally hosted model file (e.g., GGUF, MLX). Requires further configuration for model path and type (see section 1.2).
*   **`"remote_api"`:** Uses a remote LLM accessible via an API. Requires further configuration for the API endpoint and key (see section 1.3).

### 1.2. Local Helper LLM Settings

These settings are applicable **only if `STRATUM_HELPER_LLM_TYPE="local"`**.

*   **Variable:** `STRATUM_LOCAL_HELPER_MODEL_PATH`
    **Default:** `""`
    **Description:** The absolute or relative path to your local helper model file.
    **Example:** `/path/to/your/models/dolphin-2.6-mistral-7b.Q4_K_M.gguf`

*   **Variable:** `STRATUM_LOCAL_HELPER_MODEL_TYPE`
    **Default:** `""`
    **Description:** Specifies the format/type of the local model to help Stratum Light load it correctly.
    **Supported Values:**
        *   `"gguf"`: For models in GGUF format. Requires `llama-cpp-python` to be installed (e.g., `pip install stratum_light[local_llm]` or `pip install llama-cpp-python`).
        *   `"mlx"`: For models compatible with Apple's MLX framework. Requires `mlx-lm` (e.g., `pip install stratum_light[local_llm]` or `pip install mlx-lm`). (Note: MLX inference is currently conceptual in the adapter and falls back to simulation).
    **Note:** Stratum Light's `LocalLLMAdapter` attempts to use these libraries if specified. Ensure they are installed in your Python environment if you intend to use corresponding local model types.

*   **Advanced GGUF Parameters for Helper LLM (Optional):**
    These apply if `STRATUM_HELPER_LLM_TYPE="local"` and `STRATUM_LOCAL_HELPER_MODEL_TYPE="gguf"`.
    *   `STRATUM_LOCAL_HELPER_MAX_TOKENS` (Default: `256`): Max tokens for the helper GGUF model's generation.
    *   `STRATUM_LOCAL_HELPER_TEMPERATURE` (Default: `0.1`): Temperature for helper GGUF model's generation.
    *   `STRATUM_LOCAL_HELPER_LLAMA_CPP_N_CTX` (Default: `2048`): Context window size for `llama-cpp-python`.
    *   `STRATUM_LOCAL_HELPER_LLAMA_CPP_N_GPU_LAYERS` (Default: `0`): Number of layers to offload to GPU for `llama-cpp-python`. `0` means CPU only, `-1` attempts to offload all.
    *   `STRATUM_LOCAL_HELPER_LLAMA_CPP_VERBOSE` (Default: `False`): Verbose logging from `llama-cpp-python`.
    *   `STRATUM_LOCAL_HELPER_LLAMA_CPP_ARGS` (Default: `""`): Comma-separated `key:value` pairs for additional arguments to the `Llama` constructor from `llama-cpp-python` (e.g., `"n_batch:1024,rope_freq_scale:0.5"`).

### 1.3. Remote Helper LLM API Settings

These settings are applicable **only if `STRATUM_HELPER_LLM_TYPE="remote_api"`**.

*   **Variable:** `STRATUM_REMOTE_HELPER_API_ENDPOINT`
    **Default:** `""`
    **Description:** The full URL of the remote helper LLM's API endpoint that accepts inference requests.
    **Example:** `https://api.private-llm-provider.com/v1/chat/completions`

*   **Variable:** `STRATUM_REMOTE_HELPER_API_KEY`
    **Default:** `""`
    **Description:** The API key required to authenticate with the remote helper LLM service. **This is a sensitive value.** Store it securely, preferably as an environment variable or in an encrypted configuration.
    **Example:** `your_secure_api_key_here`

*   **Variable:** `STRATUM_REMOTE_HELPER_API_TIMEOUT`
    **Default:** `30` (seconds)
    **Description:** Timeout in seconds for requests made to the remote helper LLM API.

## 2. Configuring the Target Model SDK (for API-based Targets)

When `PromptInjectionAnalyzer` uses a helper LLM, it first needs to get the output from the *target model* (the model you are actually testing for vulnerabilities). If this target model is itself accessed via an API, you may need to provide specific credentials or endpoint details for it, especially if they differ from any global default model configurations.

These settings are stored under the `target_model_sdk` configuration block.

*   **Variable:** `STRATUM_TARGET_MODEL_API_ENDPOINT`
    **Default:** `""`
    **Description:** The API endpoint URL for the *target model* if it's remote and requires a specific endpoint. If your target models are always local, or if they use a globally configured API endpoint (e.g., from your default OpenAI setup), this might be left empty.
    **Example:** `https://api.another-llm-provider.com/v1/generate`

*   **Variable:** `STRATUM_TARGET_MODEL_API_KEY`
    **Default:** `""`
    **Description:** The API key for the *target model* if it's remote and requires specific authentication. **This is a sensitive value.**
    **Example:** `target_model_specific_api_key`

*   **Local Target Model GGUF Parameters (Optional):**
    These apply if the `target_model_name` passed to the analyzer is a path to a local GGUF model and no `STRATUM_TARGET_MODEL_API_ENDPOINT` is set (i.e., it's treated as a local target).
    *   `STRATUM_LOCAL_TARGET_MAX_TOKENS` (Default: `150`): Max tokens for the target GGUF model's generation.
    *   `STRATUM_LOCAL_TARGET_TEMPERATURE` (Default: `0.7`): Temperature for target GGUF model's generation.
    *   `STRATUM_LOCAL_TARGET_LLAMA_CPP_N_CTX` (Default: `2048`): Context window size.
    *   `STRATUM_LOCAL_TARGET_LLAMA_CPP_N_GPU_LAYERS` (Default: `0`): GPU layers.
    *   `STRATUM_LOCAL_TARGET_LLAMA_CPP_VERBOSE` (Default: `False`): Verbose logging from `llama-cpp-python` for the target model.

**How it Works:**
When `PromptInjectionAnalyzer.detect_injection(...)` is called:
1.  It receives the `target_model_name`.
2.  If a helper LLM is configured, the `HelperLLMInterface`'s `get_target_model_output` method is called.
3.  This method will use `STRATUM_TARGET_MODEL_API_ENDPOINT` and `STRATUM_TARGET_MODEL_API_KEY` (if provided and the helper adapter is `RemoteAPILLMAdapter`) to fetch the output from the specified `target_model_name`.
4.  This output, along with the original prompt and any auxiliary outputs, is then passed to the helper LLM for behavioral analysis.

## Example `.env` Configuration Snippets

### Scenario 1: No Helper LLM (Phrase-Based Only)
```env
STRATUM_HELPER_LLM_TYPE="none"
# Other variables as needed...
```

### Scenario 2: Local GGUF Helper LLM
```env
STRATUM_HELPER_LLM_TYPE="local"
STRATUM_LOCAL_HELPER_MODEL_PATH="/path/to/your/model.gguf"
STRATUM_LOCAL_HELPER_MODEL_TYPE="gguf"

# If your target model is also local and identified by path, no specific target SDK vars needed.
# If your target model is an API:
# STRATUM_TARGET_MODEL_API_ENDPOINT="https://api.targetllm.com/v1/..."
# STRATUM_TARGET_MODEL_API_KEY="target_api_key"
```

### Scenario 3: Remote API Helper LLM
```env
STRATUM_HELPER_LLM_TYPE="remote_api"
STRATUM_REMOTE_HELPER_API_ENDPOINT="https://my.helperllm.com/api/analyze"
STRATUM_REMOTE_HELPER_API_KEY="helper_secret_key"
STRATUM_REMOTE_HELPER_API_TIMEOUT="60"

# If your target model is different from the helper and also API-based:
# STRATUM_TARGET_MODEL_API_ENDPOINT="https://api.targetllm.com/v1/..."
# STRATUM_TARGET_MODEL_API_KEY="target_api_key"
```

By configuring these settings appropriately, you can tailor the `PromptInjectionAnalyzer`'s capabilities to your specific environment and security requirements. Remember to handle API keys and other sensitive information securely.

## 3. Troubleshooting Common Issues

Here are some common issues you might encounter when configuring the helper LLM or target model SDK, along with potential solutions:

*   **Issue: `PromptInjectionAnalyzer` falls back to phrase-based checks only, even with helper LLM configured.**
    *   **Cause:** `STRATUM_HELPER_LLM_TYPE` might be misspelled, set to `"none"`, or not set (defaulting to `"none"`).
    *   **Solution:** Ensure `STRATUM_HELPER_LLM_TYPE` is correctly set to `"local"` or `"remote_api"` in your environment or configuration file. Check for typos.
    *   **Cause:** The respective adapter (`LocalLLMAdapter` or `RemoteAPILLMAdapter`) might have failed to initialize due to missing critical sub-configurations (e.g., no path for local, no endpoint for remote) or errors during the (simulated or actual) model loading/API client setup.
    *   **Solution:** Check Stratum Light's startup logs. `LightCore` logs warnings if an adapter type is specified but fails to initialize, or if the type is unsupported. Adapters themselves also log warnings if critical paths/endpoints are missing.

*   **Issue (Local Helper): `LocalLLMAdapter initialized without LOCAL_HELPER_MODEL_PATH` warning, or `Helper model not loaded` error in PIA results.**
    *   **Cause:** `STRATUM_LOCAL_HELPER_MODEL_PATH` is not set or is empty.
    *   **Solution:** Provide a valid file system path to your local model file for `STRATUM_LOCAL_HELPER_MODEL_PATH`.

*   **Issue (Local Helper): Errors related to `llama_cpp` or `mlx_lm` (e.g., `ImportError: No module named 'llama_cpp'`).**
    *   **Cause:** The required Python library for your chosen `STRATUM_LOCAL_HELPER_MODEL_TYPE` (e.g., `gguf`, `mlx`) is not installed in your Python environment.
    *   **Solution:** Install the necessary library (e.g., `pip install llama-cpp-python` or `pip install mlx mlx-lm`). Refer to their respective documentation for any additional system dependencies (like C compilers for `llama-cpp-python`).

*   **Issue (Local Helper): Model file not found or invalid format, even if path and type are set.**
    *   **Cause:** The path in `STRATUM_LOCAL_HELPER_MODEL_PATH` might be incorrect, or the model file itself is corrupted or not the format specified by `STRATUM_LOCAL_HELPER_MODEL_TYPE`.
    *   **Solution:** Double-check the file path. Ensure the model file is valid and matches the specified type. Check logs for more detailed errors from the underlying model loading library (when fully implemented).

*   **Issue (Remote Helper/Target): `RemoteAPILLMAdapter initialized without REMOTE_HELPER_API_ENDPOINT` warning, or `Helper API not configured` error in PIA results.**
    *   **Cause:** `STRATUM_REMOTE_HELPER_API_ENDPOINT` is not set or empty (for helper), or `STRATUM_TARGET_MODEL_API_ENDPOINT` is not set when `PromptInjectionAnalyzer` needs to call a remote target model.
    *   **Solution:** Ensure the correct API endpoint URL is provided for the respective variable.

*   **Issue (Remote Helper/Target): API requests fail with authentication errors (e.g., 401 Unauthorized, 403 Forbidden).**
    *   **Cause:** The API key (`STRATUM_REMOTE_HELPER_API_KEY` or `STRATUM_TARGET_MODEL_API_KEY`) is missing, incorrect, or lacks the necessary permissions for the API.
    *   **Solution:** Verify the API key is correct and has been set in your environment. Ensure it has the required scopes/permissions for the LLM provider. Remember that GitHub and some other services require Personal Access Tokens (PATs) instead of passwords for programmatic access.

*   **Issue (Remote Helper/Target): API requests fail with timeout errors.**
    *   **Cause:** The remote API is slow to respond, or the timeout value is too short.
    *   **Solution:** Increase `STRATUM_REMOTE_HELPER_API_TIMEOUT` (for helper) or the general `API_TIMEOUT` if applicable to target model calls. Check the LLM provider's status page for any ongoing incidents.

*   **Issue (Remote Helper/Target): `ValueError: api_endpoint must be provided...` when calling `get_target_model_output`.**
    *   **Cause:** `PromptInjectionAnalyzer` is trying to get output from a target model using the `RemoteAPILLMAdapter` (because the helper is remote, or because the target model is explicitly API-based), but the `target_model_api_endpoint` was not available/passed correctly.
    *   **Solution:** Ensure `STRATUM_TARGET_MODEL_API_ENDPOINT` is correctly configured if your target model is remote and needs to be called via API by the analyzer.

*   **Issue (Remote Helper): `ValueError: Helper API response format is invalid.`**
    *   **Cause:** The remote helper LLM API returned a response, but it wasn't the expected JSON structure (missing keys like `is_deviant_behavior`, `reasoning`, etc.).
    *   **Solution:** This indicates that the `RemoteAPILLMAdapter`'s `analyze_model_behavior` method needs adjustment for the specific API you're using. The TODO comments in that method highlight where payload construction and response parsing need to be tailored. Check the helper LLM's API documentation.

*   **Issue: PIA results show an `error` field with a message.**
    *   **Cause:** An exception occurred during the PIA process, often within the helper LLM interaction or when trying to get target model output.
    *   **Solution:** The message in the `error` field and the accompanying `explanation` should provide clues. Check Stratum Light's logs for more detailed tracebacks (e.g., `logs/stratum.log` if file logging is enabled).
