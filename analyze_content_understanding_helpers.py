import re
import json
from pathlib import Path
from markdown import markdown as md_convert
from typing import List, Dict, Optional


def extract_raw_markdown(contents: list) -> str:
    """Extract only the raw 'markdown' fields from each content block, joined together."""
    return "\n\n".join(block["markdown"] for block in contents if "markdown" in block)


def markdown_to_html(
    md: str,
    extensions: Optional[List[str]] = None,
    visualization_rules: Optional[List[Dict[str, str]]] = None,
) -> str:
    """
    Convert Markdown to HTML with:
      - table styling
      - optional regex-based visualization (comments, figures, etc)
      - full HTML/CSS scaffold
    """
    # 1) Markdown → HTML5
    html_body = md_convert(
        md,
        extensions=extensions or ["extra", "tables", "smarty"],
        output_format="html",
    )

    # 2) Table / cell styling
    html_body = re.sub(
        r"<table>",
        '<table style="width:100%;border-collapse:collapse;border:1px solid #000;margin:20px 0;">',
        html_body,
    )
    html_body = re.sub(
        r"<th>",
        '<th style="border:1px solid #000;padding:10px;background-color:#f0f0f0;color:#000;text-align:left;">',
        html_body,
    )
    html_body = re.sub(
        r"<td>",
        '<td style="border:1px solid #000;padding:10px;vertical-align:top;">',
        html_body,
    )

    # 3) Apply any config‐driven regex rules
    if visualization_rules:
        for rule in visualization_rules:
            pattern = rule["condition"]
            treatment = rule["treatment"]
            html_body = re.sub(pattern, treatment, html_body, flags=re.MULTILINE)

    # 4) Wrap in your full style guide
    html = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '  <meta charset="UTF-8"/>',
        "  <title>Styled OCR Output</title>",
        "  <style>",
        "    body { font-family: Arial, sans-serif; margin: 40px; color: #000; background-color: #fff; }",
        "    h1,h2,h3 { color: #000; }",
        "    table { width:100%; border-collapse:collapse; margin-bottom:2em; }",
        "    th,td { border:1px solid #000; padding:10px; vertical-align:top; }",
        "    th { background-color:#f0f0f0; color:#000; text-align:left; }",
        "    caption { caption-side: top; font-weight:bold; text-align:left; margin-bottom:10px; }",
        "    .note { font-style:italic; margin-top:20px; }",
        "    .footer-note { font-size:0.9em; color:#000; }",
        "  </style>",
        "</head>",
        "<body>",
        html_body,
        "</body>",
        "</html>",
    ]
    return "\n".join(html)


def save_markdown(content: str, output_path: Path):
    """Save Markdown text to a file."""
    output_path.write_text(content, encoding="utf-8")


def save_log(log_data: dict, log_path: Path):
    """Save raw JSON log to a file."""
    log_path.write_text(json.dumps(log_data, indent=2), encoding="utf-8")


def save_html(html_content: str, output_path: Path):
    """Save HTML content to a file."""
    output_path.write_text(html_content, encoding="utf-8")
