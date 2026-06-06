#!/usr/bin/env python3
"""Cloud deployment utilities for STRATUM_LIGHT."""

import subprocess
import logging

logger = logging.getLogger(__name__)

class CloudDeployer:
    """Deploy trained models to supported cloud providers."""

    @staticmethod
    def deploy_to_cloud(provider: str, model: str) -> None:
        if provider == "aws":
            subprocess.run(["aws", "sagemaker", "create-model", "--model-name", model])
        elif provider == "azure":
            subprocess.run(["az", "ml", "model", "create", "--name", model])
        else:
            logger.warning("Unknown provider %s", provider)
            return
        logger.info("Model %s deployed to %s", model, provider)
