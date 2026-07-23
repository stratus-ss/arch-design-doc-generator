#!/usr/bin/env python3
"""
config.py — Project configuration reader.

Reads project.yaml and exposes values to bash scripts via CLI queries
or to Python scripts via direct import.

CLI usage (for bash scripts):
    python3 scripts/lib/config.py get client_name
    python3 scripts/lib/config.py get brand.primary_color
    python3 scripts/lib/config.py get-list hld.phase_files
    python3 scripts/lib/config.py get-list phases[].lld_file
    python3 scripts/lib/config.py get-map hld.summary_map
    python3 scripts/lib/config.py render-css --doc-type hld

Python usage:
    from config import load_config
    cfg = load_config()
    print(cfg["client_name"])
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml


def find_project_yaml(start: Path | None = None) -> Path:
    """Find project.yaml. Checks sibling of scripts/ first, then walks up."""
    if start and start.is_file():
        start = start.parent

    # This file lives in src/scripts/lib/; project.yaml is under src/
    lib_dir = Path(__file__).resolve().parent
    src_dir = lib_dir.parent.parent
    candidate = src_dir / "project.yaml"
    if candidate.exists():
        return candidate

    # Fallback: walk up from start or cwd
    search = start or Path.cwd()
    for d in [search, *search.parents]:
        for loc in [d / "project.yaml", d / "src" / "project.yaml"]:
            if loc.exists():
                return loc
    raise FileNotFoundError("project.yaml not found in any parent directory")


def load_config(path: Path | None = None) -> dict:
    """Load and return the project config dict."""
    config_path = path or find_project_yaml()
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve_key(cfg: dict, key: str):
    """Resolve a dot-separated key path, with [] suffix for list extraction."""
    if "[]." in key:
        list_key, field = key.split("[].", 1)
        items = resolve_key(cfg, list_key)
        if isinstance(items, list):
            return [item[field] for item in items if field in item]
        return []

    parts = key.split(".")
    val = cfg
    for part in parts:
        if isinstance(val, dict):
            val = val[part]
        else:
            raise KeyError(f"Cannot traverse into {type(val)} at '{part}'")
    return val


def render_css(cfg: dict, doc_type: str) -> str:
    """Render the print CSS with brand values substituted."""
    brand = cfg["brand"]
    primary = brand["primary_color"]
    secondary = brand["secondary_color"]
    header_font = brand["header_font"]
    code_font = brand["code_font"]
    footer_text = brand["footer_text"]

    if doc_type == "hld":
        title = cfg["document_title_hld"]
    elif doc_type == "lld":
        title = cfg["document_title_lld"]
    else:
        title = f"{cfg['client_name']} {cfg['project_code']} — {doc_type.upper()}"

    return f"""@page {{
  size: letter;
  margin: 0.75in 0.65in 0.65in 0.65in;
  @top-left {{
    content: "{title}";
    font-size: 7.5pt; color: {primary}; font-weight: 600;
    font-family: {header_font};
  }}
  @top-right {{
    content: "{footer_text}";
    font-size: 7.5pt; color: {primary};
    font-family: {header_font};
  }}
  @bottom-right {{
    content: counter(page);
    font-size: 7.5pt; color: #666;
    font-family: {header_font};
  }}
}}
@page :first {{
  margin-top: 1in;
  @top-left {{ content: none; }}
  @top-right {{ content: none; }}
}}
* {{ box-sizing: border-box; }}
body {{
  font-family: {header_font};
  font-size: 10pt; line-height: 1.5; color: #1a1a1a;
}}
h1 {{
  font-size: 19pt; color: {primary};
  border-bottom: 2.5px solid {primary};
  padding-bottom: 5px; margin-top: 28px; margin-bottom: 12px;
  page-break-after: avoid;
}}
h2 {{
  font-size: 14pt; color: {primary};
  border-bottom: 1.2px solid {secondary};
  padding-bottom: 3px; margin-top: 22px; margin-bottom: 10px;
  page-break-after: avoid;
}}
h3 {{
  font-size: 11.5pt; color: {primary};
  margin-top: 16px; margin-bottom: 8px;
  page-break-after: avoid;
}}
h4 {{
  font-size: 10.5pt; color: {primary};
  margin-top: 12px; margin-bottom: 6px;
  page-break-after: avoid;
}}
table {{
  border-collapse: collapse; width: 100%;
  margin: 10px 0 14px 0; font-size: 8.5pt; line-height: 1.4;
  page-break-inside: auto;
}}
thead {{ display: table-header-group; }}
tr {{ page-break-inside: avoid; }}
th {{
  background-color: {primary}; color: #ffffff; font-weight: 600;
  text-align: left; padding: 6px 8px; border: 1px solid {primary};
  font-size: 8.5pt; white-space: nowrap;
}}
td {{
  padding: 5px 8px; border: 1px solid #cbd5e1;
  vertical-align: top; word-wrap: break-word;
}}
tbody tr:nth-child(even) {{ background-color: #f1f5f9; }}
td strong {{ color: {primary}; }}
hr {{ border: none; border-top: 1.5px solid {secondary}; margin: 20px 0; }}
img {{
  display: block;
  margin: 10px auto;
  max-width: 100%;
  max-height: 7.5in;
  image-resolution: 250dpi;
}}
figure {{
  margin: 10px 0;
  page-break-inside: avoid;
}}
figcaption {{ display: none; }}
code {{
  font-family: {code_font};
  font-size: 8pt; background-color: #f1f5f9;
  padding: 1px 4px; border-radius: 2px; color: #b91c1c;
}}
pre {{
  background-color: #f8fafc; border: 1px solid #e2e8f0;
  border-left: 3px solid {primary}; padding: 8px 12px;
  border-radius: 3px; font-size: 8pt; page-break-inside: avoid;
}}
pre code {{ background: none; padding: 0; color: inherit; }}
ul, ol {{ margin: 5px 0; padding-left: 20px; }}
ul {{ list-style-type: disc; }}
ul ul {{ list-style-type: circle; }}
ul ul ul {{ list-style-type: square; }}
li {{ margin-bottom: 2px; }}
li > ul, li > ol {{ margin-top: 2px; margin-bottom: 2px; }}
a {{ color: {secondary}; text-decoration: none; }}
p {{ margin: 5px 0; orphans: 3; widows: 3; }}
h2 + p, h3 + p, h3 + table, h2 + table {{ page-break-before: avoid; }}"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Query project.yaml values")
    parser.add_argument("--config", type=Path, default=None,
                        help="Path to project.yaml (default: auto-detect)")
    sub = parser.add_subparsers(dest="command")

    get_p = sub.add_parser("get", help="Get a scalar value")
    get_p.add_argument("key", help="Dot-separated key path")

    getlist_p = sub.add_parser("get-list", help="Get a list value (one per line)")
    getlist_p.add_argument("key", help="Dot-separated key path")

    getmap_p = sub.add_parser("get-map", help="Get a map as JSON")
    getmap_p.add_argument("key", help="Dot-separated key path")

    css_p = sub.add_parser("render-css", help="Render print CSS")
    css_p.add_argument("--doc-type", required=True, choices=["hld", "lld"],
                       help="Document type for header title")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    cfg = load_config(args.config)

    if args.command == "get":
        val = resolve_key(cfg, args.key)
        print(val)
    elif args.command == "get-list":
        val = resolve_key(cfg, args.key)
        if isinstance(val, list):
            for item in val:
                print(item)
        else:
            print(val)
    elif args.command == "get-map":
        val = resolve_key(cfg, args.key)
        print(json.dumps(val, indent=2))
    elif args.command == "render-css":
        print(render_css(cfg, args.doc_type))


if __name__ == "__main__":
    main()
