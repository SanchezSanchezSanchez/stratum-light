#!/usr/bin/env python3
# Reporting Module for STRATUM_LIGHT

import os
import json
import logging
import requests
import asyncio
import aiohttp
import uuid
from typing import Dict
from datetime import datetime

# Logger setup
logger = logging.getLogger(__name__)

# Import config from global scope
from config.settings import config

class BountyReporter:
    @staticmethod
    def calculate_cvss(model: str) -> Dict:
        base_score = 9.0 if model in ["gpt2", "llama", "grok"] else 8.5
        return {"base_score": base_score, "vector": config["cvss_vector"]}

    @staticmethod
    async def submit_report_async(vulnerability: str, response: str, model: str):
        report = {
            "title": f"Critical LLM Vulnerability in {model}: {vulnerability}",
            "description": f"Unpatchable systemic flaw: {vulnerability}\nPoC: {response}",
            "severity": "Critical",
            "exploit": "Adversarial prompt injection and logit manipulation",
            "mitigation": "Requires architectural changes or advanced adversarial training",
            "cvss": BountyReporter.calculate_cvss(model),
            "timestamp": datetime.utcnow().isoformat(),
            "uuid": str(uuid.uuid4())
        }
        async with aiohttp.ClientSession() as session:
            for endpoint in config["bounty_endpoints"]:
                try:
                    async with session.post(endpoint, json=report, headers={"Authorization": f"Bearer {os.getenv('LIGHT_BOUNTY_KEY')}"}):
                        logger.info(f"Bounty report submitted to {endpoint}")
                except Exception as e:
                    logger.error(f"Bounty submission to {endpoint} failed: {str(e)}")
                    with open(f"bounty_report_{model}_{datetime.utcnow().isoformat()}.json", "w") as f:
                        json.dump(report, f)
                    logger.info("Report saved locally")

class SiemLogger:
    @staticmethod
    def log_to_siem(vulnerability: str, response: str, model: str):
        siem_event = {
            "event": "LLM Vulnerability Discovery",
            "model": model,
            "vulnerability": vulnerability,
            "response": response,
            "timestamp": datetime.utcnow().isoformat()
        }
        try:
            requests.post(config["siem_endpoint"], json=siem_event)
            logger.info("SIEM event logged")
        except Exception as e:
            logger.error(f"SIEM logging failed: {str(e)}")
