#!/usr/bin/env python3
# ==============================================================================
# Filename:       scripts/fill_ga_poa.py
# Version:        1.0
# Author:         opencode (jimmy, ar0)
# Last Modified:  2026-07-25
# Trac Ticket:    #4042 (Implement PDF form-filling automation for GA POA documents)
#
# Purpose:
#     Data-driven filler for the Georgia Statutory (Financial) Power of Attorney
#     AcroForm. Reads a YAML or JSON data file of principal/agent/witness values,
#     maps friendly keys to the canonical State of Georgia (DCA) template's 67
#     AcroForm field names, and writes a pre-filled PDF to an output path.
#
#     Downstream (optional): --flatten bakes values into the page and removes the
#     form fields, producing a locked PDF that renders identically everywhere
#     (native pypdf >= 4.x). On the apt 3.4.1 baseline, flatten is deferred to an
#     external tool (Stirling PDF http://stirling-pdf.home.arpa, or qpdf).
#     See skills/domain/pdf-editor.md.
#
# Canonical template:
#     State of Georgia DCA fillable POA (dca.georgia.gov). 8 pages, 67 /Tx fields,
#     no XFA. A blank copy should live alongside as ga-poa-template-dca-fillable.pdf.
#
# pypdf compatibility:
#     Written to the pypdf 3.4.x API (apt python3-pypdf on Debian bookworm) for
#     fleet portability -- uses PdfWriter().append(reader) + per-page
#     update_page_form_field_values(..., auto_regenerate=False). Avoids 4.x-only
#     kwargs (clone_from=, flatten=). Works unchanged on newer pypdf (tested 6.9.2).
#
# Usage:
#     python3 scripts/fill_ga_poa.py \
#         --template ga-poa-template-dca-fillable.pdf \
#         --data poa_data.yml \
#         --out /home/will/pops/tmp/ga-poa-filled.pdf
#
#     # List the raw AcroForm field names of a template (setup/debug aid):
#     python3 scripts/fill_ga_poa.py --template <tmpl.pdf> --list-fields
#
# Data file:
#     YAML or JSON. Use the friendly keys in FIELD_MAP below (left-hand side).
#     See poa_data.example.yml for a complete annotated example. Any key you omit
#     is simply left blank on the form. You may also pass raw AcroForm field names
#     directly under a top-level 'raw_fields:' mapping for anything not aliased.
#
# Secrets: None.
# ==============================================================================

import argparse
import json
import sys
from pathlib import Path

try:
    from pypdf import PdfReader, PdfWriter
except ImportError:
    sys.exit(
        "ERROR: pypdf is not installed. Provision it via Ansible:\n"
        "  ansible-playbook -i inventory.ini playbooks/install_pypdf.yml --limit <host>"
    )

# ------------------------------------------------------------------------------
# FIELD MAP: friendly key -> exact AcroForm field name in the DCA template.
#
# The DCA form-maker left several widgets with generic/auto-generated names
# (Text1, Text19-23, a truncated 's email address', and a bare 'Name'). These
# were disambiguated positionally by page + surrounding form text (Trac #4042 WP3)
# and are noted inline. Signature/initial widgets that are meant to be hand-signed
# or hand-initialed are intentionally NOT aliased (left blank for wet ink).
# ------------------------------------------------------------------------------
FIELD_MAP = {
    # --- Page 0: State of Georgia / County header + principal identity block ---
    "principal_county": "County",
    "principal_name_header": "Name",          # bare 'Name' widget, p0 header block
    "principal_street": "Street Address",
    "principal_city": "City",
    "principal_state": "State",
    "principal_zip": "Zip Code",

    # --- Page 1: Designation of agent / successor agents ---
    "principal_name": "Name",                 # 'I ____ (Name of principal)'; see note below
    "agent_name": "Name of agent",
    "agent_address": "Agents address",
    "agent_phone": "Agents telephone number",
    "agent_email": "Agents email address",

    "successor_agent_name": "Name of successor agent",
    "successor_agent_address": "Successor agents address",
    "successor_agent_phone": "Successor agents telephone number",
    "successor_agent_email": "Successor agents email address",

    "second_successor_agent_name": "Name of second successor agent",
    "second_successor_agent_address": "Second successor agents address",
    "second_successor_agent_phone": "Second successor agents telephone number",
    # idx 14: truncated 'Second successor agent's e-mail address' -> stored as 's email address'
    "second_successor_agent_email": "s email address",

    # --- Page 2: Grant of General Authority (INITIAL each subject to include) ---
    # These are text/initial fields on the DCA form; put the principal's initials
    # (e.g. "WT") in each subject they wish to grant, or set grant_all_subjects.
    "grant_real_property": "Real property",
    "grant_tangible_personal_property": "Tangible personal property",
    "grant_stocks_and_bonds": "Stocks and bonds",
    "grant_commodities_and_options": "Commodities and options",
    "grant_banks": "Banks and other financial institutions",
    "grant_business": "Operation of entity or business",
    "grant_insurance_and_annuities": "Insurance and annuities",
    "grant_estates_trusts": "Estates trusts and other beneficial interests",
    "grant_claims_and_litigation": "Claims and litigation",
    "grant_personal_family_maintenance": "Personal and family maintenance",
    "grant_government_benefits": "Benefits from governmental programs or civil or military service",
    "grant_retirement_plans": "Retirement plans",
    "grant_taxes": "Taxes",
    "grant_all_subjects": "All preceding subjects",

    # --- Page 3: Grant of Specific Authority (INITIAL each) ---
    "special_inter_vivos_trust": "Create fund amend revoke or terminate an inter vivos trust",
    "special_make_a_gift": "Make a gift subject to the limitations of OCGA  106B56 and any Special",
    "special_rights_of_survivorship": "Create or change rights of survivorship",
    "special_beneficiary_designation": "Create or change a beneficiary designation",
    "special_authorize_another": "Authorize another person to exercise the authority granted under this power of attorney",
    "special_waive_survivor_annuity": "Waive the principals right to be a beneficiary of a joint and survivor annuity including a",
    "special_electronic_communications": "Excise authority over the content of electronic communications sent or received by the",
    "special_fiduciary_powers": "Exercise fiduciary powers that the principal has authority to delegate and that are",
    "special_renounce_interest": "Renounce an interest in property including a power of appointment",

    # --- Page 4: Special Instructions + Nomination of Conservator ---
    "special_instructions": "Text1",         # free-text Special Instructions block
    "conservator_nominee_name": "Name of nominee for conservator of my estate",
    "conservator_nominee_address": "Nominee's Address",
    "conservator_nominee_phone": "Nominees telephone number",
    "conservator_nominee_email": "Nominees email address",

    # --- Page 5: Signature & Acknowledgment / Witness / Notary ---
    "signature_date": "Date",
    "principal_name_printed": "Your name printed",
    "principal_address": "Your address",
    "principal_phone": "Your telephone number",
    "principal_email": "Your email address",

    "witness_signed_on": "This document was signed in my presence on",
    "witness_principal_name": "Name of principal",
    "witness_name_printed": "Witnesss name printed",
    "witness_address": "Witnesss address",
    "witness_phone": "Witnesss telephone number",
    "witness_email": "Witnesss email address",

    "notary_county": "County of_2",
    "notary_signed_on": "This document was signed in my presence on_2",
    "notary_principal_name": "Name of principal_2",
    "notary_commission_expires": "My commission expires",
    "document_prepared_by": "This document prepared by",

    # Unlabeled appearance-only signature widgets on p5 (Your signature / Witness
    # signature / Notary signature). Normally left blank for wet ink; exposed for
    # completeness only.
    "sig_widget_1": "Text19",
    "sig_widget_2": "Text20",
    "sig_widget_3": "Text21",

    # --- Page 6: 'Important Information for Agent' demonstration line ---
    # '(Principal's name) by (Your signature) as Agent' -- instructional; normally blank.
    "agent_demo_principal_name": "Text22",
    "agent_demo_signature": "Text23",
}

# Convenience: friendly keys that represent the 14 "initial to grant" subject boxes.
GRANT_SUBJECT_KEYS = [k for k in FIELD_MAP if k.startswith("grant_")]


def load_data(path):
    """Load a YAML or JSON data file into a dict."""
    text = Path(path).read_text()
    suffix = Path(path).suffix.lower()
    if suffix in (".yml", ".yaml"):
        try:
            import yaml
        except ImportError:
            sys.exit("ERROR: PyYAML not installed but a .yml data file was given. "
                     "Use JSON, or install python3-yaml.")
        return yaml.safe_load(text) or {}
    if suffix == ".json":
        return json.loads(text)
    # Try JSON first, then YAML, for extensionless files.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        import yaml
        return yaml.safe_load(text) or {}


def build_field_values(data):
    """Translate a friendly-key data dict into {acroform_field_name: value}."""
    values = {}

    # 'initials' shortcut: apply one initials string to every granted subject
    # that is set truthy under a 'grants' list, OR to all subjects if grant_all.
    initials = data.get("initials")
    grants = set(data.get("grants") or [])
    if data.get("grant_all_subjects") or "all" in grants:
        if initials:
            values[FIELD_MAP["grant_all_subjects"]] = initials
    elif initials and grants:
        for g in grants:
            fk = f"grant_{g}"
            if fk in FIELD_MAP:
                values[FIELD_MAP[fk]] = initials
            else:
                print(f"WARNING: unknown grant subject '{g}' (ignored)", file=sys.stderr)

    # Direct friendly-key mappings
    # 'grant_all_subjects' is a control flag handled above via 'initials', not a
    # literal string value -- never write the boolean into the field.
    CONTROL_KEYS = ("initials", "grants", "raw_fields", "grant_all_subjects")
    for friendly, val in data.items():
        if friendly in CONTROL_KEYS:
            continue
        if friendly in FIELD_MAP:
            values[FIELD_MAP[friendly]] = "" if val is None else str(val)
        else:
            print(f"WARNING: unknown data key '{friendly}' (ignored)", file=sys.stderr)

    # Escape hatch: raw AcroForm field names passed through verbatim
    for raw_name, val in (data.get("raw_fields") or {}).items():
        values[raw_name] = "" if val is None else str(val)

    return values


def list_fields(template):
    reader = PdfReader(template)
    fields = reader.get_fields() or {}
    print(f"{len(fields)} fields in {template}:")
    for i, (name, obj) in enumerate(fields.items()):
        print(f"  [{i:02d}] {obj.get('/FT')}  {name!r}")


def _supports_flatten():
    """True if this pypdf's update_page_form_field_values accepts flatten=."""
    import inspect
    try:
        sig = inspect.signature(PdfWriter.update_page_form_field_values)
        return "flatten" in sig.parameters
    except (ValueError, TypeError):
        return False


def fill(template, data_path, out_path, flatten=False):
    reader = PdfReader(template)
    template_fields = set((reader.get_fields() or {}).keys())

    data = load_data(data_path)
    values = build_field_values(data)

    # Warn on any mapped field that does not exist in the template (template drift)
    missing = [n for n in values if n not in template_fields]
    for n in missing:
        print(f"WARNING: field {n!r} not found in template (skipped)", file=sys.stderr)
    values = {k: v for k, v in values.items() if k in template_fields}

    writer = PdfWriter()
    writer.append(reader)  # 3.4.x-safe way to carry the AcroForm across

    # Only fields we actually want to write (non-empty). Empty-string entries in
    # the data file are intentional "leave blank" markers -- don't count them as
    # fills and don't let a blank overwrite anything.
    nonempty = {k: v for k, v in values.items() if v != ""}

    # Silence pypdf's informational "No fields to update on this page" chatter,
    # which it emits per page that has no matching widgets.
    import logging
    logging.getLogger("pypdf").setLevel(logging.ERROR)

    # Flatten bakes field values into page content and removes the interactive
    # widgets, producing a locked, universally-rendering PDF. Native to pypdf
    # >= 4.x via flatten=True; version-guarded so the script still runs (fill
    # only) on the apt 3.4.1 baseline -- flatten there is deferred to an external
    # tool (Stirling / qpdf).
    do_flatten = flatten and _supports_flatten()
    if flatten and not do_flatten:
        print("WARNING: this pypdf is too old for native flatten (needs >= 4.x); "
              "writing UN-flattened. Flatten downstream (Stirling/qpdf).",
              file=sys.stderr)

    for page in writer.pages:
        try:
            if do_flatten:
                writer.update_page_form_field_values(
                    page, nonempty, auto_regenerate=False, flatten=True
                )
            else:
                writer.update_page_form_field_values(
                    page, nonempty, auto_regenerate=False
                )
        except Exception:
            # Some pypdf versions raise when a page has no matching fields; ignore
            pass

    # Count how many of our requested non-empty values actually landed. After a
    # flatten the AcroForm is gone, so recount only makes sense un-flattened.
    if do_flatten:
        filled = len(nonempty)
    else:
        result_fields = writer.get_fields() or {}
        filled = sum(
            1 for name in nonempty
            if (result_fields.get(name) or {}).get("/V") not in (None, "")
        )

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        writer.write(f)

    tag = " (flattened)" if do_flatten else ""
    print(f"Filled {filled}/{len(nonempty)} populated fields{tag} -> {out_path}")
    if not do_flatten and filled < len(nonempty):
        print("NOTE: some values may render only after the viewer regenerates "
              "appearances; verify visually.", file=sys.stderr)
    return out_path


def main():
    ap = argparse.ArgumentParser(description="Fill the Georgia Statutory POA AcroForm.")
    ap.add_argument("--template", required=True, help="Blank fillable DCA POA PDF")
    ap.add_argument("--data", help="YAML/JSON data file of friendly-key values")
    ap.add_argument("--out", help="Output PDF path")
    ap.add_argument("--list-fields", action="store_true",
                    help="List the template's AcroForm field names and exit")
    ap.add_argument("--flatten", action="store_true",
                    help="Bake values into page content and remove form fields "
                         "(locks the PDF). Needs pypdf >= 4.x; warns + skips on older.")
    args = ap.parse_args()

    if args.list_fields:
        list_fields(args.template)
        return
    if not args.data or not args.out:
        ap.error("--data and --out are required unless --list-fields is used")
    fill(args.template, args.data, args.out, flatten=args.flatten)


if __name__ == "__main__":
    main()
