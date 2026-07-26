# ==============================================================================
# Filename:       pdf_filler/__init__.py
# Version:        1.0
# Author:         opencode (jimmy, athena)
# Last Modified:  2026-07-25
# Context:        http://trac.gafla.us.com/ticket/4042
#
# Purpose:
#     Package init for the generic PDF AcroForm filling library.
#     Exports TemplateRegistry and FillerEngine for programmatic use.
#
# Secrets:
#     None -- no credentials or secrets required.
#
# Usage:
#     from pdf_filler import TemplateRegistry, FillerEngine
#
# WWOS:   http://wwos.home.arpa/index.php/Pdf_filler
# GitHub: https://github.com/wrtaff/ansible-netbox/blob/master/scripts/pdf_filler/
#
# Revision History:
#     1.0 (2026-07-25) - Initial version. Trac #4042 WP6-WP8.
# ==============================================================================

from pdf_filler.registry import TemplateRegistry
from pdf_filler.engine import FillerEngine

__all__ = ["TemplateRegistry", "FillerEngine"]
__version__ = "1.0.0"
