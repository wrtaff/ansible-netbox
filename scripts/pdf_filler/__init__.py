# ==============================================================================
# pdf_filler -- Generic PDF AcroForm Filling Library
# Trac #4042 -- Design/Implement robust, generic PDF form-filling library
#
# Package init. Exports the main classes for programmatic use.
# ==============================================================================

from pdf_filler.registry import TemplateRegistry
from pdf_filler.engine import FillerEngine

__all__ = ["TemplateRegistry", "FillerEngine"]
__version__ = "1.0.0"
