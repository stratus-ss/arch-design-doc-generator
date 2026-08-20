#!/usr/bin/env python3
"""
config.py — Project configuration reader.

Reads project.yaml and exposes values to bash scripts via CLI queries
or to Python scripts via direct import.

CLI usage (for bash scripts):
    python3 scripts/shared/lib/config.py get client_name
    python3 scripts/shared/lib/config.py get brand.primary_color
    python3 scripts/shared/lib/config.py get-list hld.phase_files
    python3 scripts/shared/lib/config.py get-list phases[].lld_file
    python3 scripts/shared/lib/config.py get-map hld.summary_map
    python3 scripts/shared/lib/config.py render-css --doc-type hld

Python usage:
    from config import load_config
    config = load_config()
    print(config["client_name"])
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

    # This file lives in scripts/shared/lib/; project.yaml is the repo root.
    lib_dir = Path(__file__).resolve().parent
    repo_root = lib_dir.parent.parent.parent
    candidate = repo_root / "project.yaml"
    if candidate.exists():
        return candidate

    # Fallback: walk up from start or cwd
    search = start or Path.cwd()
    for directory in [search, *search.parents]:
        for location in [directory / "project.yaml", directory / "src" / "project.yaml"]:
            if location.exists():
                return location
    raise FileNotFoundError("project.yaml not found in any parent directory")


def load_config(path: Path | None = None) -> dict:
    """Load and return the project config dict."""
    config_path = path or find_project_yaml()
    with open(config_path, encoding="utf-8") as config_file:
        return yaml.safe_load(config_file)


def get_engagement_type(config: dict) -> str:
    return config.get("engagement_type", "ocp-v")


def is_health_check(config: dict) -> bool:
    return get_engagement_type(config) == "health-check"


def get_health_check_config(config: dict) -> dict:
    return config.get("health_check", {})


def get_template_dir(config: dict) -> str:
    if is_health_check(config):
        return "templates/Health_Check"
    return "templates/HLD/markdown_files"


def resolve_key(config: dict, key: str):
    """Resolve a dot-separated key path, with [] suffix for list extraction."""
    if "[]." in key:
        list_key, field = key.split("[].", 1)
        items = resolve_key(config, list_key)
        if isinstance(items, list):
            return [item[field] for item in items if field in item]
        return []

    parts = key.split(".")
    value = config
    for part in parts:
        if isinstance(value, dict):
            value = value[part]
        else:
            raise KeyError(f"Cannot traverse into {type(value)} at '{part}'")
    return value


def get_client_identity(config: dict) -> tuple[str, str]:
    """Return (client_name, project_code) from config, with defaults."""
    client = str(config.get("client_name", "")).strip()
    code = str(config.get("project_code", "OCP-V")).strip() or "OCP-V"
    return client, code


def _css_string(value: str) -> str:
    """Escape a string for interpolation into CSS content:"..." and similar."""
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def _brand_css_values(config: dict) -> tuple[str, str, str, str, str]:
    """Return primary, secondary, header_font, code_font, footer_text for CSS interpolation."""
    brand = config["brand"]
    return (
        brand["primary_color"],
        brand["secondary_color"],
        _css_string(brand["header_font"]),
        _css_string(brand["code_font"]),
        _css_string(brand["footer_text"]),
    )


def _cover_meta_css(primary: str, *, for_print: bool) -> str:
    """Shared cover-meta table rules for print and screen HC stylesheets."""
    if for_print:
        wrapper = """div.cover-meta {
  page-break-after: always;
  padding-top: 1in;
}
"""
        cell_rules = """div.cover-meta th, div.cover-meta td {
  border: none;
  background: none;
  color: #1a1a1a;
  font-size: 10pt;
  padding: 4px 8px;
  overflow-wrap: normal;
}
div.cover-meta tbody tr:nth-child(even) { background-color: transparent; }
"""
    else:
        wrapper = ""
        cell_rules = """div.cover-meta th, div.cover-meta td {
  border: none; background: none;
  overflow-wrap: normal; white-space: normal;
}
div.cover-meta tbody tr:nth-child(even) { background: transparent; }
"""

    return f"""{wrapper}div.cover-meta table {{
  width: 70%; border: none; table-layout: fixed;
}}
{cell_rules}div.cover-meta thead {{ display: none; }}
div.cover-meta td:first-child {{
  font-weight: 600; color: {primary};
  white-space: nowrap; width: 42%;
}}
div.cover-meta td:last-child {{
  overflow-wrap: break-word;
}}
"""


def render_css(config: dict, doc_type: str) -> str:
    """Render the print CSS with brand values substituted."""
    primary, secondary, header_font, code_font, footer_text = _brand_css_values(config)

    if doc_type == "hld":
        title = config["document_title_hld"]
    elif doc_type == "lld":
        title = config["document_title_lld"]
    elif doc_type == "hc":
        title = f"{config.get('client_name', '')} OpenShift Health Check"
    else:
        title = f"{config.get('client_name', '')} {config.get('project_code', '')} — {doc_type.upper()}"
    title = _css_string(title)

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
  overflow-wrap: break-word;
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
  page-break-inside: auto; table-layout: auto;
}}
thead {{ display: table-header-group; }}
tr {{ page-break-inside: avoid; }}
th {{
  background-color: #be0000; color: #ffffff; font-weight: 600;
  text-align: left; padding: 6px 8px; border: 1px solid #be0000;
  font-size: 8.5pt; overflow-wrap: break-word; white-space: nowrap;
}}
td {{
  padding: 5px 8px; border: 1px solid #cbd5e1;
  vertical-align: top; overflow-wrap: break-word;
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
ul.task-list {{ list-style: none; padding-left: 0.5em; }}
ul.task-list li {{ list-style: none; margin-bottom: 5px; }}
ul.task-list li label {{ display: flex; align-items: flex-start; gap: 0.5em; }}
ul.task-list li input[type="checkbox"] {{ flex-shrink: 0; margin-top: 2.5px; width: 10px; height: 10px; }}
a {{ color: {secondary}; text-decoration: none; }}
p {{ margin: 5px 0; orphans: 3; widows: 3; }}
h2 + p, h3 + p, h3 + table, h2 + table {{ page-break-before: avoid; }}
div.cover-page {{
  page-break-after: always;
  padding-top: 2.5in;
  padding-left: 0;
}}
div.cover-page h1 {{
  font-size: 28pt; color: {primary};
  border-bottom: none;
  margin-bottom: 8px;
  padding-bottom: 0;
}}
div.cover-page h2 {{
  font-size: 18pt; color: {primary};
  border-bottom: none;
  margin-top: 4px;
  margin-bottom: 24px;
}}
div.cover-page p {{
  font-size: 11pt; color: #333;
  margin: 4px 0;
}}
{_cover_meta_css(primary, for_print=True)}/* PDF bookmarks — WeasyPrint renders these as the collapsible outline sidebar */
h1 {{ bookmark-level: 1; bookmark-label: content(); }}
h2 {{ bookmark-level: 2; bookmark-label: content(); }}
h3 {{ bookmark-level: 3; bookmark-label: content(); }}"""


def render_css_html(config: dict) -> str:
    """Render a screen-optimised CSS stylesheet for the collapsible HTML report."""
    primary, secondary, header_font, code_font, _ = _brand_css_values(config)
    client = config.get("client_name", "")

    return f"""/* HC HTML Report — screen stylesheet */
:root {{
  --primary:   {primary};
  --secondary: {secondary};
}}
* {{ box-sizing: border-box; }}
body {{
  font-family: {header_font};
  font-size: 15px; line-height: 1.6; color: #1a1a1a;
  max-width: 1100px; margin: 0 auto; padding: 0 24px 60px;
  background: #ffffff;
  overflow-wrap: break-word;
}}
h1 {{
  font-size: 2em; color: {primary};
  border-bottom: 3px solid {primary};
  padding-bottom: 6px; margin-top: 32px;
}}
h2 {{
  font-size: 1.4em; color: {primary};
  border-bottom: 1.5px solid {secondary};
  padding-bottom: 3px; margin-top: 28px;
}}
h3 {{
  font-size: 1.1em; color: {primary}; margin-top: 18px;
}}
h4 {{ font-size: 1em; color: {primary}; margin-top: 14px; }}
table {{
  border-collapse: collapse; width: 100%;
  margin: 10px 0 16px 0; font-size: 0.88em;
  table-layout: auto;
}}
th {{
  background: #be0000; color: #fff; font-weight: 600;
  text-align: left; padding: 7px 10px; border: 1px solid #be0000;
  overflow-wrap: break-word; white-space: nowrap;
}}
td {{
  padding: 6px 10px; border: 1px solid #cbd5e1; vertical-align: top;
  overflow-wrap: break-word;
}}
tbody tr:nth-child(even) {{ background: #f8fafc; }}
td strong {{ color: {primary}; }}
hr {{ border: none; border-top: 1.5px solid {secondary}; margin: 24px 0; }}
code {{
  font-family: {code_font};
  font-size: 0.85em; background: #f1f5f9;
  padding: 1px 5px; border-radius: 3px; color: #b91c1c;
}}
pre {{
  background: #f8fafc; border: 1px solid #e2e8f0;
  border-left: 3px solid {primary}; padding: 10px 14px;
  border-radius: 4px; font-size: 0.82em; overflow-x: auto;
}}
pre code {{ background: none; padding: 0; color: inherit; }}
a {{ color: {secondary}; }}
p {{ margin: 6px 0; }}
ul, ol {{ margin: 6px 0; padding-left: 22px; }}
blockquote {{
  border-left: 4px solid {secondary}; margin: 12px 0;
  padding: 4px 14px; background: #f8fafc; color: #444;
}}
div.cover-page {{
  padding-top: 80px; padding-bottom: 40px;
  border-bottom: 3px solid {primary}; margin-bottom: 40px;
}}
div.cover-page h1 {{
  font-size: 2.4em; border-bottom: none;
}}
{_cover_meta_css(primary, for_print=False)}/* sticky top-bar */
#hc-header {{
  position: sticky; top: 0; z-index: 200;
  background: {primary}; color: #fff;
  padding: 6px 16px; font-size: 0.8em; font-weight: 600;
  display: flex; align-items: center; gap: 16px;
  margin: 0 -24px;
}}
#hc-header .title {{ flex: 1; }}
#hc-header button {{
  padding: 3px 12px; border: 1px solid rgba(255,255,255,0.5);
  border-radius: 4px; background: transparent; color: #fff;
  cursor: pointer; font-size: 0.9em;
}}
#hc-header button:hover {{ background: rgba(255,255,255,0.15); }}
/* details/summary */
details {{ margin: 4px 0; }}
details > summary {{
  cursor: pointer; list-style: none;
  padding: 7px 12px; border-radius: 4px; font-weight: 600;
  user-select: none; background: #f1f5f9;
  border-left: 3px solid {primary};
  display: flex; align-items: center; gap: 8px;
}}
details > summary::-webkit-details-marker {{ display: none; }}
details > summary::before {{
  content: "▶"; font-size: 0.7em;
  transition: transform 0.15s; flex-shrink: 0;
}}
details[open] > summary::before {{ transform: rotate(90deg); }}
details > summary:hover {{ background: #e2e8f0; }}
details details {{ margin-left: 14px; }}
details details > summary {{
  background: #f8fafc;
  border-left: 2px solid {secondary};
  font-size: 0.92em; font-weight: 500;
}}
/* title of {client} HC report */
title {{ display: none; }}
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Query project.yaml values")
    parser.add_argument("--config", type=Path, default=None, help="Path to project.yaml (default: auto-detect)")
    sub = parser.add_subparsers(dest="command")

    get_p = sub.add_parser("get", help="Get a scalar value")
    get_p.add_argument("key", help="Dot-separated key path")

    getlist_p = sub.add_parser("get-list", help="Get a list value (one per line)")
    getlist_p.add_argument("key", help="Dot-separated key path")

    getmap_p = sub.add_parser("get-map", help="Get a map as JSON")
    getmap_p.add_argument("key", help="Dot-separated key path")

    css_p = sub.add_parser("render-css", help="Render print CSS")
    css_p.add_argument("--doc-type", required=True, choices=["hld", "lld", "hc"], help="Document type for header title")

    sub.add_parser("render-css-html", help="Render screen CSS for collapsible HTML report")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    config = load_config(args.config)

    if args.command == "get":
        if args.key == "engagement_type":
            print(get_engagement_type(config))
        elif args.key == "is_health_check":
            print("true" if is_health_check(config) else "false")
        elif args.key == "template_dir":
            print(get_template_dir(config))
        else:
            value = resolve_key(config, args.key)
            print(value)
    elif args.command == "get-list":
        value = resolve_key(config, args.key)
        if isinstance(value, list):
            for item in value:
                print(item)
        else:
            print(value)
    elif args.command == "get-map":
        value = resolve_key(config, args.key)
        print(json.dumps(value, indent=2))
    elif args.command == "render-css":
        print(render_css(config, args.doc_type))
    elif args.command == "render-css-html":
        print(render_css_html(config))


if __name__ == "__main__":
    main()
