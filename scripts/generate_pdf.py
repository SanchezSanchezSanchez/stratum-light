#!/usr/bin/env python3
"""
STRATUM_LIGHT Sales One-Pager PDF Generator
"""

import os
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration

# Configure fonts
font_config = FontConfiguration()

# Input and output paths
html_path = '/home/ubuntu/stratum_light/presentation/sales_one_pager.html'
pdf_path = '/home/ubuntu/stratum_light/presentation/sales_one_pager.pdf'

# Generate PDF from HTML
HTML(html_path).write_pdf(
    pdf_path,
    font_config=font_config
)

print(f"PDF generated successfully: {pdf_path}")
