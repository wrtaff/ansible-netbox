#!/usr/bin/env python3
# ==============================================================================
# Filename:       pdf_filler/cli.py
# Version:        1.0
# Author:         opencode (jimmy, athena)
# Last Modified:  2026-07-25
# Context:        http://trac.gafla.us.com/ticket/4042
#
# Purpose:
#     Generic PDF Form Filler CLI. Provides a command-line interface to the
#     pdf_filler library for filling, previewing, and inspecting registered
#     PDF form templates.
#
# Secrets:
#     None -- no credentials or secrets required.
#
# Usage:
#     python3 -m pdf_filler.cli --template ga-poa-dca --data values.yml --out filled.pdf
#     python3 -m pdf_filler.cli --template ga-poa-dca --list-fields
#     python3 -m pdf_filler.cli --template ga-poa-dca --data values.yml --preview
#     python3 -m pdf_filler.cli --list-templates
#
# WWOS:   http://wwos.home.arpa/index.php/Pdf_filler
# GitHub: https://github.com/wrtaff/ansible-netbox/blob/master/scripts/pdf_filler/cli.py
#
# Revision History:
#     1.0 (2026-07-25) - Initial version. Trac #4042 WP7-WP8.
# ==============================================================================

import argparse
import sys
from pathlib import Path

from pdf_filler.registry import TemplateRegistry
from pdf_filler.engine import FillerEngine


def main():
    ap = argparse.ArgumentParser(
        description="Generic PDF AcroForm filler. Fills arbitrary PDF forms "
                    "using template configs from the registry.",
        prog="pdf_filler",
    )
    ap.add_argument(
        "--template", "-t",
        help="Template name from the registry (e.g. 'ga-poa-dca'), or path "
             "to a template JSON config file."
    )
    ap.add_argument(
        "--data", "-d",
        help="YAML/JSON data file of friendly-key values."
    )
    ap.add_argument(
        "--out", "-o",
        help="Output PDF path."
    )
    ap.add_argument(
        "--flatten", action="store_true",
        help="Bake values into page content and remove form fields "
             "(locks the PDF). Needs pypdf >= 4.x."
    )
    ap.add_argument(
        "--list-fields", action="store_true",
        help="List the template's AcroForm field names and exit."
    )
    ap.add_argument(
        "--list-templates", action="store_true",
        help="List all registered templates and exit."
    )
    ap.add_argument(
        "--preview", action="store_true",
        help="Dry-run: show what fields would be filled and flag overflows."
    )
    ap.add_argument(
        "--templates-dir",
        help="Override the templates directory (default: pdf_filler_templates/)."
    )

    args = ap.parse_args()

    # Set up registry
    registry = TemplateRegistry(args.templates_dir) if args.templates_dir else TemplateRegistry()
    engine = FillerEngine(registry)

    # List templates
    if args.list_templates:
        templates = registry.list_templates()
        if not templates:
            print("No templates found.")
        else:
            print(f"{len(templates)} registered template(s):")
            for name, display in templates:
                print(f"  {name:20s}  {display}")
        return

    # From here, --template is required
    if not args.template:
        ap.error("--template is required (or use --list-templates)")

    # List fields
    if args.list_fields:
        print(engine.list_fields(args.template))
        return

    # Preview (dry-run)
    if args.preview:
        if not args.data:
            ap.error("--data is required for --preview")
        print(engine.preview(args.template, args.data))
        return

    # Fill
    if not args.data or not args.out:
        ap.error("--data and --out are required for fill mode")

    result = engine.fill(args.template, args.data, args.out, flatten=args.flatten)
    print(result.summary())

    if not result.success:
        sys.exit(1)


if __name__ == "__main__":
    main()
