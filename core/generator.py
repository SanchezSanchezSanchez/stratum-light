#!/usr/bin/env python3
"""Response generation utilities for STRATUM_LIGHT."""

import sys
import logging
import psutil
try:
    import torch  # type: ignore
except Exception:  # pragma: no cover - optional dependency for tests
    class _TorchStub:
        def __getattr__(self, name):
            raise ImportError("torch is not installed; ResponseGenerator is unavailable")

    torch = _TorchStub()  # type: ignore
from typing import List
from .analyzer import import_backend
from config.settings import config

logger = logging.getLogger(__name__)

class ResponseGenerator:
    """Generate model responses with optional logit boosting."""

    _MODEL_CACHE = {}

    def __init__(self, model_name: str):
        if psutil.virtual_memory().available < 2 * 1024**3:
            logger.error("Insufficient memory for model")
            sys.exit(1)
        try:
            if model_name in self._MODEL_CACHE:
                self.tokenizer, self.model = self._MODEL_CACHE[model_name]
            else:
                AutoTokenizer, AutoModelForCausalLM = import_backend(model_name)
                self.tokenizer = AutoTokenizer.from_pretrained(model_name)
                self.model = AutoModelForCausalLM.from_pretrained(model_name)
                self._MODEL_CACHE[model_name] = (self.tokenizer, self.model)
        except Exception as e:
            logger.error(f"Model init failed: {str(e)}")
            sys.exit(1)
        self.device = torch.device(
            "cuda" if torch.cuda.is_available() else
            "mps" if hasattr(torch.backends, "mps") and torch.backends.mps.is_available() else
            "cpu"
        )
        self.model.to(self.device)
        logger.info("Model %s loaded on %s", model_name, self.device)

    def boost_logits(self, input_ids: torch.Tensor, suppressed: List[int]) -> torch.Tensor:
        """Boost suppressed token logits to increase chance of generation."""
        with torch.no_grad():
            outputs = self.model(input_ids)
            logits = outputs.logits[:, -1, :]
            std = torch.std(logits).item()
            valid_tokens = torch.tensor([t for t in suppressed if t < logits.shape[-1]], device=self.device)
            if valid_tokens.numel():
                logits[0, valid_tokens] += config.get("boost", 1.5) * std
            return logits

    def generate(self, prompt: str, suppressed: List[int], max_length: int = 100) -> str:
        """Generate a text response from a prompt."""
        try:
            inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
            input_ids = inputs["input_ids"]
            generated_ids = torch.zeros(1, max_length, dtype=torch.long, device=self.device)
            generated_ids[:, :input_ids.shape[1]] = input_ids
            for i in range(input_ids.shape[1], max_length):
                logits = self.boost_logits(generated_ids[:, :i], suppressed)
                if torch.isnan(logits).any():
                    logger.error("NaN detected in logits")
                    return "Generation failed"
                next_token = torch.multinomial(torch.softmax(logits, dim=-1), 1)
                generated_ids[:, i] = next_token
            response = self.tokenizer.decode(generated_ids[0], skip_special_tokens=True)
            logger.info("Response generated")
            return response
        except Exception as e:
            logger.error("Generation failed: %s", str(e))
            return "Generation failed"
