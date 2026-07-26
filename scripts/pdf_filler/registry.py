# ==============================================================================
# Filename:       pdf_filler/registry.py
# Version:        1.0
# Author:         opencode (jimmy, athena)
# Last Modified:  2026-07-25
# Context:        http://trac.gafla.us.com/ticket/4042
#
# Purpose:
#     Template Registry for the generic PDF form-filling library. Discovers
#     and loads template JSON configs from pdf_filler_templates/. Each .json
#     file (except _schema.json) is one registered template.
#
# Secrets:
#     None -- no credentials or secrets required.
#
# Usage:
#     from pdf_filler.registry import TemplateRegistry
#     reg = TemplateRegistry()
#     templates = reg.list_templates()
#     config = reg.get_or_raise("ga-poa-dca")
#
# WWOS:   http://wwos.home.arpa/index.php/Pdf_filler
# GitHub: https://github.com/wrtaff/ansible-netbox/blob/master/scripts/pdf_filler/registry.py
#
# Revision History:
#     1.0 (2026-07-25) - Initial version. Trac #4042 WP6.
# ==============================================================================

import json
from pathlib import Path
from typing import Dict, Optional


# Default templates directory: sibling to pdf_filler/ package
_DEFAULT_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "pdf_filler_templates"


class TemplateConfig:
    """Parsed template configuration from a JSON file."""

    def __init__(self, data: dict, config_path: Path):
        self.raw = data
        self.config_path = config_path
        self.template_name: str = data["template_name"]
        self.display_name: str = data["display_name"]
        self.source_pdf: str = data["source_pdf"]
        self.source_url: str = data.get("source_url", "")
        self.description: str = data.get("description", "")
        self.trac_ticket: Optional[int] = data.get("trac_ticket")
        self.fields: Dict[str, dict] = data.get("fields", {})
        self.groups: Dict[str, dict] = data.get("groups", {})
        self.control_keys: Dict[str, str] = data.get("control_keys", {})

    def get_field_map(self) -> Dict[str, str]:
        """Return {friendly_key: pdf_field_name} mapping."""
        return {k: v["pdf_field"] for k, v in self.fields.items()}

    def get_group_members(self, group_name: str) -> list:
        """Return friendly keys belonging to a named group."""
        return [k for k, v in self.fields.items() if v.get("group") == group_name]

    def resolve_source_pdf(self) -> Path:
        """Resolve the source PDF path. Checks:
        1. Absolute path as-is
        2. Relative to the config file's directory
        3. Relative to the scripts/ directory (sibling of pdf_filler_templates/)
        """
        p = Path(self.source_pdf)
        if p.is_absolute() and p.exists():
            return p
        # Relative to config dir
        candidate = self.config_path.parent / p
        if candidate.exists():
            return candidate.resolve()
        # Relative to scripts/
        scripts_dir = self.config_path.parent.parent
        candidate = scripts_dir / p
        if candidate.exists():
            return candidate.resolve()
        # Return the scripts/ path even if it doesn't exist yet (caller handles)
        return (scripts_dir / p).resolve()

    def __repr__(self):
        return f"TemplateConfig({self.template_name!r}, {len(self.fields)} fields)"


class TemplateRegistry:
    """Discovers and loads template configs from a directory."""

    def __init__(self, templates_dir: Optional[Path] = None):
        self.templates_dir = Path(templates_dir) if templates_dir else _DEFAULT_TEMPLATES_DIR
        self._cache: Dict[str, TemplateConfig] = {}

    def _scan(self):
        """Scan the templates directory for JSON configs."""
        if self._cache:
            return
        if not self.templates_dir.is_dir():
            return
        for f in sorted(self.templates_dir.glob("*.json")):
            if f.name.startswith("_"):
                continue  # skip _schema.json etc.
            try:
                data = json.loads(f.read_text())
                tc = TemplateConfig(data, f)
                self._cache[tc.template_name] = tc
            except (json.JSONDecodeError, KeyError) as e:
                import sys
                print(f"WARNING: skipping invalid template {f.name}: {e}", file=sys.stderr)

    def list_templates(self) -> list:
        """Return list of (template_name, display_name) tuples."""
        self._scan()
        return [(tc.template_name, tc.display_name) for tc in self._cache.values()]

    def get(self, template_name: str) -> Optional[TemplateConfig]:
        """Get a template config by name."""
        self._scan()
        return self._cache.get(template_name)

    def get_or_raise(self, template_name: str) -> TemplateConfig:
        """Get a template config or raise ValueError."""
        tc = self.get(template_name)
        if tc is None:
            available = [n for n, _ in self.list_templates()]
            raise ValueError(
                f"Template '{template_name}' not found. "
                f"Available: {', '.join(available) or '(none)'}"
            )
        return tc
