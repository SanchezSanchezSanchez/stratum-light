#!/usr/bin/env python3
"""
STRATUM_LIGHT Documentation Generator

This script auto-generates comprehensive documentation for the STRATUM_LIGHT project,
including API schemas, architectural diagrams, and user guides.
"""

import os
import sys
import shutil
import subprocess
import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Set

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def create_directory_structure():
    """Create the documentation directory structure."""
    print("Creating documentation directory structure...")
    
    # Define directories
    directories = [
        "api",
        "architecture",
        "cli",
        "deployment",
        "development",
        "guides",
        "modules",
        "security",
        "assets/images",
        "assets/css",
        "assets/js",
    ]
    
    # Create directories
    for directory in directories:
        os.makedirs(os.path.join("docs", directory), exist_ok=True)
    
    print("Directory structure created.")

def generate_index_page():
    """Generate the main index.html page."""
    print("Generating main index page...")
    
    index_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>STRATUM_LIGHT Documentation</title>
    <link rel="stylesheet" href="assets/css/styles.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css">
</head>
<body>
    <header>
        <div class="logo">
            <h1>STRATUM_LIGHT</h1>
            <p>Enterprise AI Security Platform</p>
        </div>
        <nav>
            <ul>
                <li><a href="#overview">Overview</a></li>
                <li><a href="#architecture">Architecture</a></li>
                <li><a href="#guides">Guides</a></li>
                <li><a href="#api">API</a></li>
                <li><a href="#cli">CLI</a></li>
                <li><a href="#security">Security</a></li>
                <li><a href="#deployment">Deployment</a></li>
            </ul>
        </nav>
    </header>
    
    <main>
        <section id="hero">
            <div class="hero-content">
                <h2>The World's First LLM-Native Security Framework</h2>
                <p>STRATUM_LIGHT identifies unpatchable vulnerabilities in real time, providing enterprise-grade protection for your AI systems.</p>
                <div class="cta-buttons">
                    <a href="guides/getting_started.html" class="cta-button primary">Get Started</a>
                    <a href="architecture/overview.html" class="cta-button secondary">Learn More</a>
                </div>
            </div>
        </section>
        
        <section id="overview" class="content-section">
            <h2>Overview</h2>
            <p>STRATUM_LIGHT is a comprehensive AI security platform focused on protecting Large Language Models (LLMs) from emerging threats and vulnerabilities. With its modular architecture, behavioral intelligence, and fault governance capabilities, STRATUM_LIGHT provides unparalleled protection for enterprise AI deployments.</p>
            
            <div class="feature-grid">
                <div class="feature-card">
                    <i class="fas fa-shield-alt"></i>
                    <h3>Preventive-Forensic Architecture</h3>
                    <p>Identifies vulnerabilities before exploitation while providing forensic analysis capabilities.</p>
                </div>
                <div class="feature-card">
                    <i class="fas fa-brain"></i>
                    <h3>Behavioral Intelligence</h3>
                    <p>Self-learning system that adapts to emerging threats and anomalous patterns.</p>
                </div>
                <div class="feature-card">
                    <i class="fas fa-cogs"></i>
                    <h3>Fault Governance</h3>
                    <p>Autonomous incident response with minimal human intervention.</p>
                </div>
                <div class="feature-card">
                    <i class="fas fa-chart-line"></i>
                    <h3>Telemetry Integration</h3>
                    <p>Real-time monitoring and observability for comprehensive threat detection.</p>
                </div>
            </div>
        </section>
        
        <section id="architecture" class="content-section">
            <h2>Architecture</h2>
            <p>STRATUM_LIGHT features a modular architecture designed for flexibility, scalability, and security.</p>
            
            <div class="architecture-diagram">
                <img src="architecture/architecture_diagram.png" alt="STRATUM_LIGHT Architecture Diagram">
            </div>
            
            <div class="button-container">
                <a href="architecture/overview.html" class="button">Architecture Overview</a>
                <a href="architecture/components.html" class="button">Core Components</a>
                <a href="architecture/data_flow.html" class="button">Data Flow</a>
            </div>
        </section>
        
        <section id="guides" class="content-section">
            <h2>Guides</h2>
            <p>Get started with STRATUM_LIGHT using our comprehensive guides.</p>
            
            <div class="guides-grid">
                <a href="guides/getting_started.html" class="guide-card">
                    <i class="fas fa-rocket"></i>
                    <h3>Getting Started</h3>
                    <p>Quick start guide for new users</p>
                </a>
                <a href="guides/installation.html" class="guide-card">
                    <i class="fas fa-download"></i>
                    <h3>Installation</h3>
                    <p>Detailed installation instructions</p>
                </a>
                <a href="guides/configuration.html" class="guide-card">
                    <i class="fas fa-sliders-h"></i>
                    <h3>Configuration</h3>
                    <p>Configuration options and best practices</p>
                </a>
                <a href="guides/security_testing.html" class="guide-card">
                    <i class="fas fa-bug"></i>
                    <h3>Security Testing</h3>
                    <p>How to test LLM security with STRATUM_LIGHT</p>
                </a>
            </div>
        </section>
        
        <section id="api" class="content-section">
            <h2>API Reference</h2>
            <p>Integrate STRATUM_LIGHT into your existing security infrastructure using our comprehensive API.</p>
            
            <div class="api-endpoints">
                <div class="endpoint-card">
                    <h3>Analysis Endpoints</h3>
                    <ul>
                        <li><a href="api/analysis.html#token-analysis">/api/v1/analyze/tokens</a></li>
                        <li><a href="api/analysis.html#prompt-analysis">/api/v1/analyze/prompt</a></li>
                        <li><a href="api/analysis.html#response-analysis">/api/v1/analyze/response</a></li>
                    </ul>
                </div>
                <div class="endpoint-card">
                    <h3>Security Endpoints</h3>
                    <ul>
                        <li><a href="api/security.html#vulnerability-scan">/api/v1/security/scan</a></li>
                        <li><a href="api/security.html#threat-detection">/api/v1/security/threats</a></li>
                        <li><a href="api/security.html#mitigation">/api/v1/security/mitigate</a></li>
                    </ul>
                </div>
                <div class="endpoint-card">
                    <h3>Reporting Endpoints</h3>
                    <ul>
                        <li><a href="api/reporting.html#generate-report">/api/v1/reports/generate</a></li>
                        <li><a href="api/reporting.html#get-reports">/api/v1/reports/list</a></li>
                        <li><a href="api/reporting.html#export-report">/api/v1/reports/export</a></li>
                    </ul>
                </div>
                <div class="endpoint-card">
                    <h3>System Endpoints</h3>
                    <ul>
                        <li><a href="api/system.html#health-check">/api/v1/system/health</a></li>
                        <li><a href="api/system.html#metrics">/api/v1/system/metrics</a></li>
                        <li><a href="api/system.html#configuration">/api/v1/system/config</a></li>
                    </ul>
                </div>
            </div>
            
            <div class="button-container">
                <a href="api/overview.html" class="button">API Overview</a>
                <a href="api/authentication.html" class="button">Authentication</a>
                <a href="api/examples.html" class="button">API Examples</a>
            </div>
        </section>
        
        <section id="cli" class="content-section">
            <h2>Command Line Interface</h2>
            <p>STRATUM_LIGHT provides a powerful CLI for security testing, analysis, and reporting.</p>
            
            <div class="cli-examples">
                <div class="cli-example">
                    <h3>Basic Usage</h3>
                    <pre><code>python stratum_light_launcher.py --mode=cli analyze --prompt "Your prompt here"</code></pre>
                </div>
                <div class="cli-example">
                    <h3>Security Scanning</h3>
                    <pre><code>python stratum_light_launcher.py --mode=cli scan --model gpt-4 --prompt-file prompts.txt</code></pre>
                </div>
                <div class="cli-example">
                    <h3>Report Generation</h3>
                    <pre><code>python stratum_light_launcher.py --mode=cli report --format pdf --output report.pdf</code></pre>
                </div>
            </div>
            
            <div class="button-container">
                <a href="cli/overview.html" class="button">CLI Overview</a>
                <a href="cli/commands.html" class="button">Command Reference</a>
                <a href="cli/examples.html" class="button">CLI Examples</a>
            </div>
        </section>
        
        <section id="security" class="content-section">
            <h2>Security Features</h2>
            <p>STRATUM_LIGHT includes comprehensive security features to protect your AI systems.</p>
            
            <div class="security-features">
                <div class="security-feature">
                    <i class="fas fa-shield-alt"></i>
                    <h3>Runtime Threat Shield</h3>
                    <p>Real-time protection against emerging threats and vulnerabilities.</p>
                </div>
                <div class="security-feature">
                    <i class="fas fa-brain"></i>
                    <h3>Behavioral Intelligence</h3>
                    <p>Anomaly detection and pattern recognition for proactive security.</p>
                </div>
                <div class="security-feature">
                    <i class="fas fa-cogs"></i>
                    <h3>Fault Governance</h3>
                    <p>Autonomous incident response and recovery mechanisms.</p>
                </div>
                <div class="security-feature">
                    <i class="fas fa-key"></i>
                    <h3>Secret Rotation</h3>
                    <p>Automated credential management and rotation.</p>
                </div>
                <div class="security-feature">
                    <i class="fas fa-chart-line"></i>
                    <h3>SIEM Integration</h3>
                    <p>Integration with Security Information and Event Management systems.</p>
                </div>
                <div class="security-feature">
                    <i class="fas fa-file-alt"></i>
                    <h3>Compliance</h3>
                    <p>Alignment with OWASP, NIST, and ISO 27001 standards.</p>
                </div>
            </div>
            
            <div class="button-container">
                <a href="security/overview.html" class="button">Security Overview</a>
                <a href="security/compliance.html" class="button">Compliance</a>
                <a href="security/best_practices.html" class="button">Best Practices</a>
            </div>
        </section>
        
        <section id="deployment" class="content-section">
            <h2>Deployment</h2>
            <p>STRATUM_LIGHT supports multiple deployment options to fit your infrastructure needs.</p>
            
            <div class="deployment-options">
                <div class="deployment-option">
                    <i class="fab fa-docker"></i>
                    <h3>Docker Deployment</h3>
                    <p>Deploy STRATUM_LIGHT using Docker and Docker Compose for containerized environments.</p>
                    <a href="deployment/docker.html" class="button">Docker Guide</a>
                </div>
                <div class="deployment-option">
                    <i class="fas fa-server"></i>
                    <h3>Local Installation</h3>
                    <p>Install STRATUM_LIGHT directly on your servers for maximum control and customization.</p>
                    <a href="deployment/local.html" class="button">Local Guide</a>
                </div>
                <div class="deployment-option">
                    <i class="fas fa-cloud"></i>
                    <h3>Cloud Deployment</h3>
                    <p>Deploy STRATUM_LIGHT to cloud environments like AWS, Azure, or GCP.</p>
                    <a href="deployment/cloud.html" class="button">Cloud Guide</a>
                </div>
            </div>
        </section>
    </main>
    
    <footer>
        <div class="footer-content">
            <div class="footer-section">
                <h3>STRATUM_LIGHT</h3>
                <p>Enterprise AI Security Platform</p>
            </div>
            <div class="footer-section">
                <h3>Documentation</h3>
                <ul>
                    <li><a href="#overview">Overview</a></li>
                    <li><a href="#architecture">Architecture</a></li>
                    <li><a href="#guides">Guides</a></li>
                    <li><a href="#api">API</a></li>
                    <li><a href="#cli">CLI</a></li>
                </ul>
            </div>
            <div class="footer-section">
                <h3>Resources</h3>
                <ul>
                    <li><a href="guides/getting_started.html">Getting Started</a></li>
                    <li><a href="security/best_practices.html">Best Practices</a></li>
                    <li><a href="deployment/docker.html">Deployment</a></li>
                </ul>
            </div>
        </div>
        <div class="footer-bottom">
            <p>&copy; 2025 STRATUM_LIGHT. All rights reserved.</p>
        </div>
    </footer>
    
    <script src="assets/js/main.js"></script>
</body>
</html>
"""
    
    with open(os.path.join("docs", "index.html"), "w") as f:
        f.write(index_content)
    
    print("Main index page generated.")

def generate_css():
    """Generate CSS styles for the documentation portal."""
    print("Generating CSS styles...")
    
    css_content = """/* STRATUM_LIGHT Documentation Portal Styles */

/* Variables */
:root {
    --primary-color: #0a0a0a;
    --secondary-color: #1e54b7;
    --accent-color: #dc143c;
    --text-color: #f0f0f0;
    --background-color: #121212;
    --card-background: #1e1e1e;
    --border-color: #333;
    --success-color: #28a745;
    --warning-color: #ffc107;
    --danger-color: #dc3545;
    --font-main: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
    --font-code: 'IBM Plex Mono', monospace;
}

/* Base Styles */
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
    font-family: var(--font-main);
    color: var(--text-color);
}

body {
    background-color: var(--background-color);
    line-height: 1.6;
}

header, footer {
    background: var(--primary-color);
    padding: 1rem;
}

.content-section {
    padding: 2rem;
}

"""

    css_path = os.path.join("docs", "assets", "css", "styles.css")
    with open(css_path, "w") as f:
        f.write(css_content)

    print("CSS styles generated.")


def generate_docs() -> None:
    """Generate the documentation site."""
    create_directory_structure()
    generate_index_page()
    generate_css()


if __name__ == "__main__":
    generate_docs()
