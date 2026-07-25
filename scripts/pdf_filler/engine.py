# ==============================================================================
# pdf_filler/engine.py -- Generic PDF AcroForm Filler Engine
# Trac #4042
#
# Core filler: loads a template config from the registry, maps data values to
# AcroForm field names, fills the PDF, optionally flattens (pypdf >= 4.x),
# and writes the output.
#
# pypdf compatibility:
#   Written to the pypdf 3.4.x API for fleet portability. Flatten uses 4.x+
#   native support when available, degrades gracefully otherwise.
# ==============================================================================

import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from pypdf import PdfReader, PdfWriter
except ImportError:
    sys.exit(
        "ERROR: pypdf is not installed. Provision it via Ansible:\n"
        "  ansible-playbook -i inventory.ini playbooks/install_pypdf.yml --limit <host>"
    )

from pdf_filler.registry import TemplateConfig, TemplateRegistry
from pdf_filler.text_layout import check_field_overflow


class FillResult:
    """Result of a fill operation."""

    def __init__(self):
        self.fields_requested: int = 0
        self.fields_filled: int = 0
        self.fields_skipped: List[str] = []
        self.warnings: List[str] = []
        self.overflow_warnings: List[str] = []
        self.output_path: Optional[str] = None
        self.flattened: bool = False

    @property
    def success(self) -> bool:
        return self.fields_filled > 0 and self.output_path is not None

    def summary(self) -> str:
        tag = " (flattened)" if self.flattened else ""
        lines = [f"Filled {self.fields_filled}/{self.fields_requested} populated fields{tag}"]
        if self.output_path:
            lines.append(f"  -> {self.output_path}")
        for w in self.warnings:
            lines.append(f"  WARNING: {w}")
        for w in self.overflow_warnings:
            lines.append(f"  OVERFLOW: {w}")
        if self.fields_skipped:
            lines.append(f"  Skipped fields: {', '.join(self.fields_skipped)}")
        return "\n".join(lines)


class FillerEngine:
    """Generic PDF AcroForm filler driven by template configs."""

    def __init__(self, registry: Optional[TemplateRegistry] = None):
        self.registry = registry or TemplateRegistry()

    def load_data(self, path: str) -> dict:
        """Load a YAML or JSON data file into a dict."""
        text = Path(path).read_text()
        suffix = Path(path).suffix.lower()
        if suffix in (".yml", ".yaml"):
            try:
                import yaml
            except ImportError:
                raise ImportError(
                    "PyYAML not installed but a .yml data file was given. "
                    "Use JSON, or install python3-yaml."
                )
            return yaml.safe_load(text) or {}
        if suffix == ".json":
            return json.loads(text)
        # Try JSON first, then YAML
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            import yaml
            return yaml.safe_load(text) or {}

    def build_field_values(
        self, data: dict, template: TemplateConfig
    ) -> Dict[str, str]:
        """Translate friendly-key data dict into {acroform_field_name: value}
        using the template's field map and group logic."""
        field_map = template.get_field_map()
        values = {}

        # Handle group-based 'initials' shortcut (GA POA pattern)
        initials = data.get("initials")
        grants = set(data.get("grants") or [])

        for group_name, group_cfg in template.groups.items():
            all_field = group_cfg.get("all_field")
            prefix = group_cfg.get("member_prefix", "")

            # If 'grant_all_subjects' (or equivalent) is truthy, apply initials
            if all_field and data.get(all_field) and initials:
                if all_field in field_map:
                    values[field_map[all_field]] = initials
            elif initials and grants:
                # Selective grants
                for g in grants:
                    fk = f"{prefix}{g}"
                    if fk in field_map:
                        values[field_map[fk]] = initials

        # Direct friendly-key mappings
        control_keys = set(template.control_keys.keys())
        control_keys.update({"initials", "grants", "raw_fields"})
        # Also skip boolean control flags that map to group all_fields
        for g_cfg in template.groups.values():
            af = g_cfg.get("all_field")
            if af:
                control_keys.add(af)

        for friendly, val in data.items():
            if friendly in control_keys:
                continue
            if friendly in field_map:
                values[field_map[friendly]] = "" if val is None else str(val)
            elif friendly not in ("initials", "grants", "raw_fields",
                                  "grant_all_subjects"):
                print(f"WARNING: unknown data key '{friendly}' (ignored)",
                      file=sys.stderr)

        # Escape hatch: raw AcroForm field names
        for raw_name, val in (data.get("raw_fields") or {}).items():
            values[raw_name] = "" if val is None else str(val)

        return values

    def _supports_flatten(self) -> bool:
        """True if this pypdf's update_page_form_field_values accepts flatten=."""
        import inspect
        try:
            sig = inspect.signature(PdfWriter.update_page_form_field_values)
            return "flatten" in sig.parameters
        except (ValueError, TypeError):
            return False

    def preview(
        self, template_name: str, data_path: str
    ) -> str:
        """Dry-run: show what fields would be filled, flag overflows.

        Returns a human-readable report string.
        """
        template = self.registry.get_or_raise(template_name)
        pdf_path = template.resolve_source_pdf()

        data = self.load_data(data_path)
        values = self.build_field_values(data, template)

        # Load the template PDF to get field rects
        reader = PdfReader(str(pdf_path))
        template_fields = reader.get_fields() or {}

        lines = [
            f"=== Preview: {template.display_name} ===",
            f"Template: {pdf_path.name}",
            f"Data file: {data_path}",
            f"Fields in template: {len(template_fields)}",
            f"Fields to fill: {len([v for v in values.values() if v])}",
            "",
        ]

        # Non-empty values
        nonempty = {k: v for k, v in values.items() if v != ""}
        overflow_count = 0

        for pdf_field, value in sorted(nonempty.items()):
            # Find the friendly key
            friendly = "?"
            for fk, fc in template.fields.items():
                if fc["pdf_field"] == pdf_field:
                    friendly = fk
                    break

            exists = pdf_field in template_fields
            status = "OK" if exists else "MISSING"

            # Check overflow
            overflow_msg = ""
            if exists and value:
                field_obj = template_fields[pdf_field]
                fits, warning = check_field_overflow(value, field_obj)
                if not fits and warning:
                    overflow_msg = f" ** {warning}"
                    overflow_count += 1
                elif warning:
                    overflow_msg = f" ({warning})"

            lines.append(
                f"  [{status}] {friendly} -> '{pdf_field}' = "
                f"'{value[:50]}{'...' if len(value) > 50 else ''}'"
                f"{overflow_msg}"
            )

        # Unmapped/missing
        mapped_pdf_fields = set(template.get_field_map().values())
        unmapped = [f for f in template_fields if f not in mapped_pdf_fields]
        if unmapped:
            lines.append("")
            lines.append(f"Unmapped template fields ({len(unmapped)}):")
            for f in unmapped:
                lines.append(f"  {f!r}")

        lines.append("")
        lines.append(f"Summary: {len(nonempty)} fields to fill, "
                      f"{overflow_count} overflow warnings")
        if overflow_count:
            lines.append("** Some values may be truncated on the form. "
                          "Review the OVERFLOW warnings above.")

        return "\n".join(lines)

    def list_fields(self, template_name: str) -> str:
        """List the AcroForm fields of a template's source PDF.

        Returns a human-readable report string.
        """
        template = self.registry.get_or_raise(template_name)
        pdf_path = template.resolve_source_pdf()

        reader = PdfReader(str(pdf_path))
        fields = reader.get_fields() or {}

        lines = [f"{len(fields)} fields in {pdf_path.name}:"]
        field_map_reverse = {v["pdf_field"]: k for k, v in template.fields.items()}

        for i, (name, obj) in enumerate(fields.items()):
            alias = field_map_reverse.get(name, "(unmapped)")
            ft = obj.get("/FT", "?")
            lines.append(f"  [{i:02d}] {ft}  {name!r}  -> {alias}")

        return "\n".join(lines)

    def fill(
        self,
        template_name: str,
        data_path: str,
        out_path: str,
        flatten: bool = False,
    ) -> FillResult:
        """Fill a PDF template with data and write the output.

        Args:
            template_name: Registry name of the template (e.g. 'ga-poa-dca').
            data_path: Path to YAML/JSON data file.
            out_path: Output PDF path.
            flatten: If True, bake values and lock the PDF (needs pypdf >= 4.x).

        Returns:
            FillResult with details of the operation.
        """
        result = FillResult()

        template = self.registry.get_or_raise(template_name)
        pdf_path = template.resolve_source_pdf()

        if not pdf_path.exists():
            result.warnings.append(f"Template PDF not found: {pdf_path}")
            return result

        data = self.load_data(data_path)
        values = self.build_field_values(data, template)

        reader = PdfReader(str(pdf_path))
        template_fields = set((reader.get_fields() or {}).keys())

        # Warn on mapped fields missing from template
        missing = [n for n in values if n not in template_fields]
        for n in missing:
            result.warnings.append(f"Field {n!r} not found in template (skipped)")
            result.fields_skipped.append(n)
        values = {k: v for k, v in values.items() if k in template_fields}

        # Check for overflows
        all_fields = reader.get_fields() or {}
        nonempty = {k: v for k, v in values.items() if v != ""}
        for pdf_field, value in nonempty.items():
            if pdf_field in all_fields:
                fits, warning = check_field_overflow(value, all_fields[pdf_field])
                if warning:
                    result.overflow_warnings.append(warning)

        result.fields_requested = len(nonempty)

        writer = PdfWriter()
        writer.append(reader)

        # Suppress pypdf's per-page "no fields" chatter
        logging.getLogger("pypdf").setLevel(logging.ERROR)

        do_flatten = flatten and self._supports_flatten()
        if flatten and not do_flatten:
            result.warnings.append(
                "pypdf too old for native flatten (needs >= 4.x); "
                "writing UN-flattened."
            )

        for page in writer.pages:
            try:
                kwargs = {"auto_regenerate": False}
                if do_flatten:
                    kwargs["flatten"] = True
                writer.update_page_form_field_values(page, nonempty, **kwargs)
            except Exception:
                pass

        if do_flatten:
            # Strip widget annotations and AcroForm for true lock
            try:
                writer.remove_annotations(subtypes="/Widget")
            except Exception as e:
                result.warnings.append(f"Could not remove widget annotations: {e}")
            try:
                root = writer._root_object
                if "/AcroForm" in root:
                    del root["/AcroForm"]
            except Exception as e:
                result.warnings.append(f"Could not remove AcroForm: {e}")
            result.fields_filled = len(nonempty)
            result.flattened = True
        else:
            result_fields = writer.get_fields() or {}
            result.fields_filled = sum(
                1 for name in nonempty
                if (result_fields.get(name) or {}).get("/V") not in (None, "")
            )

        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "wb") as f:
            writer.write(f)

        result.output_path = out_path
        return result
