#!/usr/bin/env python3
"""Pydantic schema models for configuration validation.

These models are intentionally lightweight and align with the fields used
by tests to validate types and coercion.
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, HttpUrl


class LoggingConfig(BaseModel):
    level: str = "INFO"
    log_to_file: bool = False
    log_path: str = "logs/stratum.log"


class HelperLLMConfig(BaseModel):
    type: Literal["none", "local", "remote_api"] = "none"
    # Local helper params
    local_model_path: str = ""
    local_model_type: str = ""
    local_helper_max_tokens: int = 256
    local_helper_temperature: float = 0.1
    local_helper_llama_cpp_n_ctx: int = 2048
    local_helper_llama_cpp_n_gpu_layers: int = 0
    local_helper_llama_cpp_verbose: bool = False
    local_helper_llama_cpp_args: str = ""
    # Remote helper params
    remote_api_endpoint: Optional[HttpUrl] = None
    remote_api_key: str = ""
    remote_api_timeout: int = 30


class TargetModelSDK(BaseModel):
    api_endpoint: Optional[HttpUrl] = None
    api_key: str = ""
    local_target_max_tokens: int = 150
    local_target_temperature: float = 0.7
    local_target_llama_cpp_n_ctx: int = 2048
    local_target_llama_cpp_n_gpu_layers: int = 0
    local_target_llama_cpp_verbose: bool = False


class MainConfig(BaseModel):
    models: List[str]
    boost: float = 1.5
    bounty_endpoints: List[str] = []
    cvss_base: float = 9.0
    cvss_vector: str = "AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H"
    siem_endpoint: str = "https://splunk.example.com"
    cloud_providers: List[str] = ["aws", "azure", "gcp"]
    logging: LoggingConfig = LoggingConfig()
    api_bounty_endpoint: str = "https://api.hackerone.com/v1/reports"
    api_siem_endpoint: str = "https://splunk.example.com"
    default_model: str = "gpt2"
    timeout: int = 30
    environment: str = "development"

    helper_llm: HelperLLMConfig = HelperLLMConfig()
    target_model_sdk: TargetModelSDK = TargetModelSDK()


