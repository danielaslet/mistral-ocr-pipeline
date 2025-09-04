import base64
import json
import uuid
from pathlib import Path
import httpx
from typing import List, Dict, Optional
from azure.core.credentials import AzureKeyCredential
from azure.ai.formrecognizer import DocumentAnalysisClient
import re
from markdown import markdown as md_convert


def generate_run_id() -> str:
    """Generate a short 8-char hex run ID."""
    return uuid.uuid4().hex[:8]


# --- Azure helpers ---
def call_azure_ocr(endpoint: str, api_key: str, pdf_path: str, model_id: str) -> dict:
    credential = AzureKeyCredential(api_key)
    client = DocumentAnalysisClient(endpoint, credential)
    with open(pdf_path, "rb") as f:
        poller = client.begin_analyze_document(model_id, document=f)
    result = poller.result()
    return result.to_dict()


# --- Mistral helpers ---
def encode_pdf_to_base64(pdf_path: str) -> str:
    with open(pdf_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def call_mistral_ocr(endpoint: str, api_key: str, pdf_path: str) -> dict:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    encoded = encode_pdf_to_base64(pdf_path)
    payload = {
        "model": "mistral-ocr-2503",
        "document": {
            "type": "document_url",
            "document_url": f"data:application/pdf;base64,{encoded}",
        },
        "include_image_base64": False,
    }
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(endpoint, headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()


# --- Markdown Extraction ---


def extract_markdown_from_pages(pages: list) -> str:
    md_pages = []
    for pg in pages:
        if "markdown" in pg:
            md_pages.append(pg["markdown"])
        else:
            lines = [ln.get("content", "") for ln in pg.get("lines", [])]
            md_pages.append("\n".join(lines))
    return "\n\n---\n\n".join(md_pages)


def extract_markdown_with_artifacts(contents: list) -> str:
    sections = []
    for block in contents:
        if block.get("kind") == "html" or block.get("contentType") == "html":
            sections.append(block.get("html", ""))
            continue
        if block.get("kind") == "table":
            html = block.get("html") or block.get("markdown", "")
            sections.append(html)
            continue
        if "comment" in block:
            sections.append(f"<!-- {block['comment']} -->")
            continue
        if "lines" in block:
            for ln in block["lines"]:
                txt = ln.get("content", "")
                if txt.strip().startswith("<!--") and txt.strip().endswith("-->"):
                    sections.append(txt)
                else:
                    sections.append(txt)
            continue
        if "markdown" in block:
            sections.append(block["markdown"])
    return "\n\n".join(sections)


def extract_raw_markdown(contents: list) -> str:
    """
    Extract only the raw 'markdown' fields from each content block,
    joined together, with no fallbacks or injections.
    """
    return "\n\n".join(block["markdown"] for block in contents if "markdown" in block)


# --- IO Helpers ---
def save_markdown(content: str, output_path: Path):
    output_path.write_text(content, encoding="utf-8")


def save_log(log_data: dict, log_path: Path):
    log_path.write_text(json.dumps(log_data, indent=2), encoding="utf-8")


# --- HTML Generation ---


def markdown_to_html(
    md: str, extensions=None, visualization_rules: Optional[List[Dict[str, str]]] = None
) -> str:
    # def markdown_to_html(
    #     md: str, extensions=None, visualization_rules: List[Dict[str, str]] = None
    # ) -> str:
    """
    Convert Markdown → HTML, style tables, then apply any
    condition/treatment rules from `visualization_rules`.
    """
    # 1) Markdown → HTML5
    html = md_convert(
        md,
        extensions=extensions or ["extra", "tables", "smarty"],
        output_format="html",
    )

    # 2) Style tables, TH, TD
    html = re.sub(
        r"<table>",
        '<table style="width:100%;border-collapse:collapse;border:1px solid #ddd;margin:20px 0;">',
        html,
    )
    html = re.sub(
        r"<th>",
        '<th style="border:1px solid #ddd;padding:8px;background-color:#215e99;color:white;">',
        html,
    )
    html = re.sub(r"<td>", '<td style="border:1px solid #ddd;padding:8px;">', html)

    # 3) Apply each condition→treatment in order
    if visualization_rules:
        for rule in visualization_rules:
            pattern = rule["condition"]
            repl = rule["treatment"]
            html = re.sub(pattern, repl, html, flags=re.MULTILINE)
    return html


def tables_to_structured_html(tables: list) -> str:
    html_parts = []
    seen = set()
    for tbl in tables:
        tbl_id = tbl.get("id")
        if tbl_id in seen:
            continue
        frags = [t for t in tables if t.get("id") == tbl_id]
        seen.add(tbl_id)
        html_parts.append(
            '<table style="width:100%;border-collapse:collapse;border:1px solid #ddd;margin:20px 0;">'
        )
        # header
        header = frags[0]["rows"][0]
        html_parts.append("<thead><tr>")
        for cell in header:
            html_parts.append(
                f'<th style="border:1px solid #ddd;padding:8px;background-color:#215e99;color:white;">{cell.get("content", "").strip()}</th>'
            )
        html_parts.append("</tr></thead><tbody>")
        for frag in frags:
            for row in frag.get("rows", [])[1:]:
                html_parts.append("<tr>")
                for cell in row:
                    html_parts.append(
                        f'<td style="border:1px solid #ddd;padding:8px;">{cell.get("content", "").strip()}</td>'
                    )
                html_parts.append("</tr>")
        html_parts.append("</tbody></table>")
    return "\n".join(html_parts)


def contents_to_structured_html(contents: list) -> str:
    parts = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        '<head><meta charset="UTF-8"/><title>OCR Output</title></head>',
        "<body>",
    ]
    # raw HTML & comments
    for block in contents:
        if block.get("kind") == "html" or block.get("contentType") == "html":
            parts.append(block.get("html", ""))
        elif "comment" in block:
            parts.append(f"<!-- {block['comment']} -->")
    # tables
    tables = [c for c in contents if c.get("kind") == "table"]
    if tables:
        parts.append(tables_to_structured_html(tables))
    # other blocks
    for block in contents:
        if block.get("kind") == "table":
            continue
        if (
            block.get("kind") == "html"
            or block.get("contentType") == "html"
            or "comment" in block
        ):
            continue
        if "markdown" in block:
            parts.append(markdown_to_html(block["markdown"]))
        elif "lines" in block:
            for ln in block["lines"]:
                txt = ln.get("content", "")
                if txt.strip().startswith("<!--") and txt.strip().endswith("-->"):
                    parts.append(txt)
                else:
                    parts.append(f"<p>{txt.strip()}</p>")
    parts.append("</body></html>")
    return "\n".join(parts)


def save_html(html_content: str, output_path: Path):
    output_path.write_text(html_content, encoding="utf-8")


# --- Full Style Guide Renderer ---
def markdown_to_styled_html(markdown_content: str) -> str:
    body_html = md_convert(
        markdown_content, extensions=["extra", "smarty"], output_format="html"
    )
    html = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "  <head>",
        '    <meta charset="UTF-8"/>',
        "    <title>Styled OCR Output</title>",
        "    <style>",
        "      body { font-family: Arial, sans-serif; margin: 40px; color: #000; background-color: #fff; }",
        "      h1,h2,h3 { color: #000; }",
        "      table { width:100%; border-collapse:collapse; margin-bottom:2em; }",
        "      th,td { border:1px solid #000; padding:10px; vertical-align:top; }",
        "      th { background-color:#f0f0f0; color:#000; text-align:left; }",
        "      caption { caption-side: top; font-weight:bold; text-align:left; margin-bottom:10px; }",
        "      .note { font-style:italic; margin-top:20px; }",
        "      .footer-note { font-size:0.9em; color:#000; }",
        "    </style>",
        "  </head>",
        "  <body>",
        body_html,
        "  </body>",
        "</html>",
    ]
    return "\n".join(html)


# import base64
# import json
# import uuid
# from pathlib import Path
# import httpx
# from azure.core.credentials import AzureKeyCredential
# from azure.ai.formrecognizer import DocumentAnalysisClient
# import re
# from markdown import markdown as md_convert


# def generate_run_id() -> str:
#     """Generate a short 8-char hex run ID."""
#     return uuid.uuid4().hex[:8]


# # --- Azure helpers ---
# def call_azure_ocr(endpoint: str, api_key: str, pdf_path: str, model_id: str) -> dict:
#     credential = AzureKeyCredential(api_key)
#     client = DocumentAnalysisClient(endpoint, credential)
#     with open(pdf_path, "rb") as f:
#         poller = client.begin_analyze_document(model_id, document=f)
#     result = poller.result()
#     return result.to_dict()


# # --- Mistral helpers ---
# def encode_pdf_to_base64(pdf_path: str) -> str:
#     with open(pdf_path, "rb") as f:
#         return base64.b64encode(f.read()).decode("utf-8")


# def call_mistral_ocr(endpoint: str, api_key: str, pdf_path: str) -> dict:
#     headers = {
#         "Content-Type": "application/json",
#         "Accept": "application/json",
#         "Authorization": f"Bearer {api_key}",
#     }
#     encoded = encode_pdf_to_base64(pdf_path)
#     payload = {
#         "model": "mistral-ocr-2503",
#         "document": {
#             "type": "document_url",
#             "document_url": f"data:application/pdf;base64,{encoded}",
#         },
#         "include_image_base64": False,
#     }
#     with httpx.Client(timeout=60.0) as client:
#         resp = client.post(endpoint, headers=headers, json=payload)
#         resp.raise_for_status()
#         return resp.json()


# # --- Markdown Extraction ---
# def extract_markdown_from_pages(pages: list) -> str:
#     md_pages = []
#     for pg in pages:
#         if "markdown" in pg:
#             md_pages.append(pg["markdown"])
#         else:
#             lines = [ln.get("content", "") for ln in pg.get("lines", [])]
#             md_pages.append("\n".join(lines))
#     return "\n\n---\n\n".join(md_pages)


# def extract_markdown_with_artifacts(contents: list) -> str:
#     sections = []
#     for block in contents:
#         if block.get("kind") == "html" or block.get("contentType") == "html":
#             sections.append(block.get("html", ""))
#             continue
#         if block.get("kind") == "table":
#             html = block.get("html") or block.get("markdown", "")
#             sections.append(html)
#             continue
#         if "comment" in block:
#             sections.append(f"<!-- {block['comment']} -->")
#             continue
#         if "lines" in block:
#             for ln in block["lines"]:
#                 txt = ln.get("content", "")
#                 if txt.strip().startswith("<!--") and txt.strip().endswith("-->"):
#                     sections.append(txt)
#                 else:
#                     sections.append(txt)
#             continue
#         if "markdown" in block:
#             sections.append(block["markdown"])
#     return "\n\n".join(sections)


# # --- IO Helpers ---
# def save_markdown(content: str, output_path: Path):
#     output_path.write_text(content, encoding="utf-8")


# def save_log(log_data: dict, log_path: Path):
#     log_path.write_text(json.dumps(log_data, indent=2), encoding="utf-8")


# # --- HTML Generation ---


# def markdown_to_html(md: str, **kwargs) -> str:
#     html = md_convert(
#         md, extensions=kwargs.pop("extensions", ["extra", "tables", "smarty"]), **kwargs
#     )
#     html = re.sub(
#         r"<table>",
#         '<table style="width:100%;border-collapse:collapse;border:1px solid #ddd;margin:20px 0;">',
#         html,
#     )
#     html = re.sub(
#         r"<th>",
#         '<th style="border:1px solid #ddd;padding:8px;background-color:#215e99;color:white;">',
#         html,
#     )
#     html = re.sub(r"<td>", '<td style="border:1px solid #ddd;padding:8px;">', html)
#     return html


# def tables_to_structured_html(tables: list) -> str:
#     html_parts = []
#     seen = set()
#     for tbl in tables:
#         tbl_id = tbl.get("id")
#         if tbl_id in seen:
#             continue
#         frags = [t for t in tables if t.get("id") == tbl_id]
#         seen.add(tbl_id)
#         html_parts.append(
#             '<table style="width:100%;border-collapse:collapse;border:1px solid #ddd;margin:20px 0;">'
#         )
#         # header
#         header = frags[0]["rows"][0]
#         html_parts.append("<thead><tr>")
#         for cell in header:
#             html_parts.append(
#                 f'<th style="border:1px solid #ddd;padding:8px;background-color:#215e99;color:white;">{cell.get("content", "").strip()}</th>'
#             )
#         html_parts.append("</tr></thead><tbody>")
#         for frag in frags:
#             for row in frag.get("rows", [])[1:]:
#                 html_parts.append("<tr>")
#                 for cell in row:
#                     html_parts.append(
#                         f'<td style="border:1px solid #ddd;padding:8px;">{cell.get("content", "").strip()}</td>'
#                     )
#                 html_parts.append("</tr>")
#         html_parts.append("</tbody></table>")
#     return "\n".join(html_parts)


# def contents_to_structured_html(contents: list) -> str:
#     parts = [
#         "<!DOCTYPE html>",
#         '<html lang="en">',
#         '<head><meta charset="UTF-8"/><title>OCR Output</title></head>',
#         "<body>",
#     ]
#     # raw HTML & comments
#     for block in contents:
#         if block.get("kind") == "html" or block.get("contentType") == "html":
#             parts.append(block.get("html", ""))
#         elif "comment" in block:
#             parts.append(f"<!-- {block['comment']} -->")
#     # tables
#     tables = [c for c in contents if c.get("kind") == "table"]
#     if tables:
#         parts.append(tables_to_structured_html(tables))
#     # other blocks
#     for block in contents:
#         if block.get("kind") == "table":
#             continue
#         if (
#             block.get("kind") == "html"
#             or block.get("contentType") == "html"
#             or "comment" in block
#         ):
#             continue
#         if "markdown" in block:
#             parts.append(markdown_to_html(block["markdown"]))
#         elif "lines" in block:
#             for ln in block["lines"]:
#                 txt = ln.get("content", "")
#                 if txt.strip().startswith("<!--") and txt.strip().endswith("-->"):
#                     parts.append(txt)
#                 else:
#                     parts.append(f"<p>{txt.strip()}</p>")
#     parts.append("</body></html>")
#     return "\n".join(parts)


# def save_html(html_content: str, output_path: Path):
#     output_path.write_text(html_content, encoding="utf-8")


# # --- Full Style Guide Renderer ---
# def markdown_to_styled_html(markdown_content: str) -> str:
#     body_html = md_convert(
#         markdown_content, extensions=["extra", "smarty"], output_format="html"
#     )
#     html = [
#         "<!DOCTYPE html>",
#         '<html lang="en">',
#         "  <head>",
#         '    <meta charset="UTF-8"/>',
#         "    <title>Styled OCR Output</title>",
#         "    <style>",
#         "      body { font-family: Arial, sans-serif; margin: 40px; color: #000; background-color: #fff; }",
#         "      h1,h2,h3 { color: #000; }",
#         "      table { width:100%; border-collapse:collapse; margin-bottom:2em; }",
#         "      th,td { border:1px solid #000; padding:10px; vertical-align:top; }",
#         "      th { background-color:#f0f0f0; color:#000; text-align:left; }",
#         "      caption { caption-side: top; font-weight:bold; text-align:left; margin-bottom:10px; }",
#         "      .note { font-style:italic; margin-top:20px; }",
#         "      .footer-note { font-size:0.9em; color:#000; }",
#         "    </style>",
#         "  </head>",
#         "  <body>",
#         body_html,
#         "  </body>",
#         "</html>",
#     ]
#     return "\n".join(html)


# import base64
# import json
# import uuid
# from pathlib import Path
# import httpx
# from azure.core.credentials import AzureKeyCredential
# from azure.ai.formrecognizer import DocumentAnalysisClient
# import re
# from markdown import markdown as md_convert


# def generate_run_id() -> str:
#     """Generate a short 8-char hex run ID."""
#     return uuid.uuid4().hex[:8]


# # --- Azure helpers ---
# def call_azure_ocr(endpoint: str, api_key: str, pdf_path: str, model_id: str) -> dict:
#     """Call Azure Document Intelligence begin_analyze_document and return full response as dict."""
#     credential = AzureKeyCredential(api_key)
#     client = DocumentAnalysisClient(endpoint, credential)
#     with open(pdf_path, "rb") as f:
#         poller = client.begin_analyze_document(model_id, document=f)
#     result = poller.result()
#     return result.to_dict()


# # --- Mistral helpers ---
# def encode_pdf_to_base64(pdf_path: str) -> str:
#     """Encode a PDF file to a base64 string."""
#     with open(pdf_path, "rb") as f:
#         return base64.b64encode(f.read()).decode("utf-8")


# def call_mistral_ocr(endpoint: str, api_key: str, pdf_path: str) -> dict:
#     """Call Mistral OCR endpoint and return JSON response."""
#     headers = {
#         "Content-Type": "application/json",
#         "Accept": "application/json",
#         "Authorization": f"Bearer {api_key}",
#     }
#     encoded = encode_pdf_to_base64(pdf_path)
#     payload = {
#         "model": "mistral-ocr-2503",
#         "document": {
#             "type": "document_url",
#             "document_url": f"data:application/pdf;base64,{encoded}",
#         },
#         "include_image_base64": False,
#     }
#     with httpx.Client(timeout=60.0) as client:
#         resp = client.post(endpoint, headers=headers, json=payload)
#         resp.raise_for_status()
#         return resp.json()


# # --- Markdown Extraction ---
# def extract_markdown_from_pages(pages: list) -> str:
#     """Flatten pages into a simple Markdown string (no raw HTML)."""
#     md_pages = []
#     for pg in pages:
#         if "markdown" in pg:
#             md_pages.append(pg["markdown"])
#         else:
#             lines = [ln.get("content", "") for ln in pg.get("lines", [])]
#             md_pages.append("\n".join(lines))
#     return "\n\n---\n\n".join(md_pages)


# def extract_markdown_with_artifacts(contents: list) -> str:
#     """Preserve raw HTML, comments, and tables in Markdown."""
#     sections = []
#     for block in contents:
#         # raw HTML blocks
#         if block.get("kind") == "html" or block.get("contentType") == "html":
#             sections.append(block.get("html", ""))
#             continue
#         # table fragments — emit as HTML
#         if block.get("kind") == "table":
#             html = block.get("html") or block.get("markdown", "")
#             sections.append(html)
#             continue
#         # comments
#         if "comment" in block:
#             sections.append(f"<!-- {block['comment']} -->")
#             continue
#         # text lines
#         if "lines" in block:
#             text = " ".join(ln.get("content", "") for ln in block.get("lines", []))
#             sections.append(text)
#             continue
#         # fallback markdown
#         if "markdown" in block:
#             sections.append(block["markdown"])
#     return "\n\n".join(sections)


# # --- IO Helpers ---
# def save_markdown(content: str, output_path: Path):
#     """Save Markdown text to a file."""
#     output_path.write_text(content, encoding="utf-8")


# def save_log(log_data: dict, log_path: Path):
#     """Save raw JSON log to a file."""
#     log_path.write_text(json.dumps(log_data, indent=2), encoding="utf-8")


# # --- HTML Generation ---
# def markdown_to_html(md: str, **kwargs) -> str:
#     """Convert Markdown to HTML with styled tables."""
#     html = md_convert(
#         md, extensions=kwargs.pop("extensions", ["extra", "tables", "smarty"]), **kwargs
#     )
#     html = re.sub(
#         r"<table>",
#         '<table style="width:100%;border-collapse:collapse;border:1px solid #ddd;margin:20px 0;">',
#         html,
#     )
#     html = re.sub(
#         r"<th>",
#         '<th style="border:1px solid #ddd;padding:8px;background-color:#215e99;color:white;">',
#         html,
#     )
#     html = re.sub(r"<td>", '<td style="border:1px solid #ddd;padding:8px;">', html)
#     return html


# def tables_to_structured_html(tables: list) -> str:
#     """Rebuild tables from JSON fragments, preserving headers across pages."""
#     html_parts = []
#     seen = set()
#     for tbl in tables:
#         tbl_id = tbl.get("id")
#         if tbl_id in seen:
#             continue
#         frags = [t for t in tables if t.get("id") == tbl_id]
#         seen.add(tbl_id)
#         html_parts.append(
#             '<table style="width:100%;border-collapse:collapse;border:1px solid #ddd;margin:20px 0;">'
#         )
#         # header
#         header = frags[0]["rows"][0]
#         html_parts.append("<thead><tr>")
#         for cell in header:
#             html_parts.append(
#                 f'<th style="border:1px solid #ddd;padding:8px;background-color:#215e99;color:white;">{cell.get("content", "").strip()}</th>'
#             )
#         html_parts.append("</tr></thead><tbody>")
#         # body
#         for frag in frags:
#             for row in frag.get("rows", [])[1:]:
#                 html_parts.append("<tr>")
#                 for cell in row:
#                     html_parts.append(
#                         f'<td style="border:1px solid #ddd;padding:8px;">{cell.get("content", "").strip()}</td>'
#                     )
#                 html_parts.append("</tr>")
#         html_parts.append("</tbody></table>")
#     return "\n".join(html_parts)


# def contents_to_structured_html(contents: list) -> str:
#     """Generate full HTML from JSON contents, including tables and markdown."""
#     parts = [
#         "<!DOCTYPE html>",
#         '<html lang="en">',
#         '<head><meta charset="UTF-8"/><title>OCR Output</title></head>',
#         "<body>",
#     ]
#     # render tables
#     tables = [c for c in contents if c.get("kind") == "table"]
#     if tables:
#         parts.append(tables_to_structured_html(tables))
#     # other blocks
#     for block in contents:
#         if block.get("kind") == "table":
#             continue
#         if "markdown" in block:
#             parts.append(markdown_to_html(block["markdown"]))
#         elif "lines" in block:
#             text = " ".join(ln.get("content", "") for ln in block.get("lines", []))
#             parts.append(f"<p>{text.strip()}</p>")
#     parts.append("</body></html>")
#     return "\n".join(parts)


# def save_html(html_content: str, output_path: Path):
#     """Save HTML content to a file."""
#     output_path.write_text(html_content, encoding="utf-8")


# # --- Full Style Guide Renderer ---
# def markdown_to_styled_html(markdown_content: str) -> str:
#     """Wrap Markdown in an HTML scaffold using the provided style guide."""
#     body_html = md_convert(
#         markdown_content, extensions=["extra", "smarty"], output_format="html"
#     )
#     html = [
#         "<!DOCTYPE html>",
#         '<html lang="en">',
#         "  <head>",
#         '    <meta charset="UTF-8"/>',
#         "    <title>Styled OCR Output</title>",
#         "    <style>",
#         "      body { font-family: Arial, sans-serif; margin: 40px; color: #000; background-color: #fff; }",
#         "      h1,h2,h3 { color: #000; }",
#         "      table { width:100%; border-collapse:collapse; margin-bottom:2em; }",
#         "      th,td { border:1px solid #000; padding:10px; vertical-align:top; }",
#         "      th { background-color:#f0f0f0; color:#000; text-align:left; }",
#         "      caption { caption-side: top; font-weight:bold; text-align:left; margin-bottom:10px; }",
#         "      .note { font-style:italic; margin-top:20px; }",
#         "      .footer-note { font-size:0.9em; color:#000; }",
#         "    </style>",
#         "  </head>",
#         "  <body>",
#         body_html,
#         "  </body>",
#         "</html>",
#     ]
#     return "\n".join(html)


# import base64
# import json
# import uuid

# from pathlib import Path
# import httpx
# from azure.core.credentials import AzureKeyCredential
# from azure.ai.formrecognizer import DocumentAnalysisClient

# # import markdown as _markdown
# import re
# from markdown import markdown as md_convert


# def generate_run_id() -> str:
#     """Generate a short 8-char hex run ID."""
#     return uuid.uuid4().hex[:8]


# # --- Azure helpers ---
# def call_azure_ocr(endpoint: str, api_key: str, pdf_path: str, model_id: str) -> dict:
#     """Call Azure Document Intelligence begin_analyze_document and return full response as dict."""
#     credential = AzureKeyCredential(api_key)
#     client = DocumentAnalysisClient(endpoint, credential)
#     with open(pdf_path, "rb") as f:
#         poller = client.begin_analyze_document(model_id, document=f)
#     result = poller.result()
#     return result.to_dict()


# # --- Mistral helpers ---
# def encode_pdf_to_base64(pdf_path: str) -> str:
#     with open(pdf_path, "rb") as f:
#         return base64.b64encode(f.read()).decode("utf-8")


# def call_mistral_ocr(endpoint: str, api_key: str, pdf_path: str) -> dict:
#     """Call Mistral OCR endpoint and return JSON response."""
#     headers = {
#         "Content-Type": "application/json",
#         "Accept": "application/json",
#         "Authorization": f"Bearer {api_key}",
#     }
#     encoded = encode_pdf_to_base64(pdf_path)
#     payload = {
#         "model": "mistral-ocr-2503",
#         "document": {
#             "type": "document_url",
#             "document_url": f"data:application/pdf;base64,{encoded}",
#         },
#         "include_image_base64": False,
#     }
#     with httpx.Client(timeout=60.0) as client:
#         resp = client.post(endpoint, headers=headers, json=payload)
#         resp.raise_for_status()
#         return resp.json()


# # --- Common output/save ---
# def extract_markdown_from_pages(pages: list) -> str:
#     """Join page markdown or lines into a single Markdown string."""
#     md_pages = []
#     for pg in pages:
#         if "markdown" in pg:
#             md = pg["markdown"]
#         else:
#             md = "\n".join([ln["content"] for ln in pg.get("lines", [])])
#         md_pages.append(md)
#     return "\n\n---\n\n".join(md_pages)


# def save_markdown(content: str, output_path: Path):
#     output_path.write_text(content, encoding="utf-8")


# def save_log(log_data: dict, log_path: Path):
#     log_path.write_text(json.dumps(log_data, indent=2), encoding="utf-8")


# # --- HTML helpers ---


# def markdown_to_html(markdown_content: str, **kwargs) -> str:
#     """Convert a Markdown string into HTML using Python-Markdown extensions and style the tables and cells."""
#     extensions = kwargs.pop("extensions", ["extra", "tables", "smarty"])
#     # Convert Markdown to HTML
#     html = md_convert(markdown_content, extensions=extensions, **kwargs)
#     # Style tables, headers, and cells per previous logic
#     html = re.sub(
#         r"<table>",
#         '<table style="width: 100%; border-collapse: collapse; border: 1px solid #ddd; margin: 20px 0;">',
#         html,
#     )
#     html = re.sub(
#         r"<th>",
#         '<th style="border: 1px solid #ddd; padding: 8px; background-color: #215e99; color: white;">',
#         html,
#     )
#     html = re.sub(r"<td>", '<td style="border: 1px solid #ddd; padding: 8px;">', html)
#     return html


# def contents_to_structured_html(contents: list) -> str:
#     """Convert raw Content Understanding JSON 'contents' into structured HTML."""
#     html_parts = [
#         "<!DOCTYPE html>",
#         '<html lang="en">',
#         "<head>",
#         '<meta charset="UTF-8" />',
#         "<title>OCR Output</title>",
#         "<style>",
#         "  body { font-family: Arial, sans-serif; margin: 40px; color: #000; background-color: #fff; }",
#         "  h1, h2, h3 { color: #000; }",
#         "  table { width: 100%; border-collapse: collapse; margin-bottom: 2em; }",
#         "  th, td { border: 1px solid #000; padding: 10px; vertical-align: top; }",
#         "  th { background-color: #f0f0f0; color: #000; text-align: left; }",
#         "  caption { caption-side: top; font-weight: bold; text-align: left; margin-bottom: 10px; }",
#         "  .note { font-style: italic; margin-top: 20px; }",
#         "  .footer-note { font-size: 0.9em; color: #000; }",
#         "</style>",
#         "</head>",
#         "<body>",
#     ]
#     for item in contents:
#         if "markdown" in item:
#             html_parts.append(markdown_to_html(item["markdown"]))
#         elif "lines" in item:
#             text = " ".join(ln.get("content", "") for ln in item.get("lines", []))
#             html_parts.append(f"<p>{text.strip()}</p>")
#     html_parts.extend(["</body>", "</html>"])
#     return "\n".join(html_parts)


# def save_html(html_content: str, output_path: Path):
#     """Save HTML content to a file path."""
#     output_path.write_text(html_content, encoding="utf-8")


# # --- New: Full style guide renderer ---
# def markdown_to_styled_html(markdown_content: str) -> str:
#     """Wrap Markdown in a full HTML document using the provided styling guide."""
#     # Convert md to basic HTML
#     # body_html = md_convert(markdown_content, extensions=["extra", "smarty"])

#     # Convert md to basic HTML, allowing raw HTML blocks & comments to pass through
#     body_html = md_convert(
#         markdown_content,
#         extensions=["extra", "smarty"],
#         output_format="html",
#         # no safe_mode in v3+, raw HTML is preserved by default
#     )

#     # Build full document
#     html = [
#         "<!DOCTYPE html>",
#         '<html lang="en">',
#         "  <head>",
#         '    <meta charset="UTF-8" />',
#         "    <title>HTML Table & Content Output</title>",
#         "    <style>",
#         "      body {",
#         "        font-family: Arial, sans-serif;",
#         "        margin: 40px;",
#         "        color: #000;",
#         "        background-color: #fff;",
#         "      }",
#         "      h1, h2, h3 {",
#         "        color: #000;",
#         "      }",
#         "      table {",
#         "        width: 100%;",
#         "        border-collapse: collapse;",
#         "        margin-bottom: 2em;",
#         "      }",
#         "      th, td {",
#         "        border: 1px solid #000;",
#         "        padding: 10px;",
#         "        vertical-align: top;",
#         "      }",
#         "      th {",
#         "        background-color: #f0f0f0;",
#         "        color: #000;",
#         "        text-align: left;",
#         "      }",
#         "      caption {",
#         "        caption-side: top;",
#         "        font-weight: bold;",
#         "        text-align: left;",
#         "        margin-bottom: 10px;",
#         "      }",
#         "      .note {",
#         "        font-style: italic;",
#         "        margin-top: 20px;",
#         "      }",
#         "      .footer-note {",
#         "        font-size: 0.9em;",
#         "        color: #000;",
#         "      }",
#         "    </style>",
#         "  </head>",
#         "  <body>",
#         body_html,
#         "  </body>",
#         "</html>",
#     ]
#     return "\n".join(html)


# import base64
# import json
# import uuid

# from pathlib import Path
# import httpx
# from azure.core.credentials import AzureKeyCredential
# from azure.ai.formrecognizer import DocumentAnalysisClient

# # import markdown as _markdown
# from markdown import markdown as md_convert
# import re


# def generate_run_id() -> str:
#     """Generate a short 8-char hex run ID."""
#     return uuid.uuid4().hex[:8]


# # --- Azure helpers ---
# def call_azure_ocr(endpoint: str, api_key: str, pdf_path: str, model_id: str) -> dict:
#     """Call Azure Document Intelligence begin_analyze_document and return full response as dict."""
#     credential = AzureKeyCredential(api_key)
#     client = DocumentAnalysisClient(endpoint, credential)
#     with open(pdf_path, "rb") as f:
#         poller = client.begin_analyze_document(model_id, document=f)
#     result = poller.result()
#     return result.to_dict()


# # --- Mistral helpers ---
# def encode_pdf_to_base64(pdf_path: str) -> str:
#     with open(pdf_path, "rb") as f:
#         return base64.b64encode(f.read()).decode("utf-8")


# def call_mistral_ocr(endpoint: str, api_key: str, pdf_path: str) -> dict:
#     """Call Mistral OCR endpoint and return JSON response."""
#     headers = {
#         "Content-Type": "application/json",
#         "Accept": "application/json",
#         "Authorization": f"Bearer {api_key}",
#     }
#     encoded = encode_pdf_to_base64(pdf_path)
#     payload = {
#         "model": "mistral-ocr-2503",
#         "document": {
#             "type": "document_url",
#             "document_url": f"data:application/pdf;base64,{encoded}",
#         },
#         "include_image_base64": False,
#     }
#     with httpx.Client(timeout=60.0) as client:
#         resp = client.post(endpoint, headers=headers, json=payload)
#         resp.raise_for_status()
#         return resp.json()


# # --- Common output/save ---
# def extract_markdown_from_pages(pages: list) -> str:
#     """Join page markdown or lines into a single Markdown string."""
#     md_pages = []
#     for pg in pages:
#         if "markdown" in pg:
#             md = pg["markdown"]
#         else:
#             md = "\n".join([ln["content"] for ln in pg.get("lines", [])])
#         md_pages.append(md)
#     return "\n\n---\n\n".join(md_pages)


# def save_markdown(content: str, output_path: Path):
#     output_path.write_text(content, encoding="utf-8")


# def save_log(log_data: dict, log_path: Path):
#     log_path.write_text(json.dumps(log_data, indent=2), encoding="utf-8")


# # --- HTML helpers ---


# def markdown_to_html(markdown_content: str, **kwargs) -> str:
#     """Convert a Markdown string into HTML using Python-Markdown extensions."""
#     extensions = kwargs.pop("extensions", ["extra", "tables", "smarty"])
#     html = md_convert(markdown_content, extensions=extensions, **kwargs)
#     # Inline style tables, headers, and cells per design guidelines
#     html = re.sub(
#         r"<table>",
#         '<table style="width: 100%; border-collapse: collapse; border: 1px solid #ddd; margin: 20px 0;">',
#         html,
#     )
#     html = re.sub(
#         r"<th>",
#         '<th style="border: 1px solid #ddd; padding: 8px; background-color: #215e99; color: white;">',
#         html,
#     )
#     html = re.sub(r"<td>", '<td style="border: 1px solid #ddd; padding: 8px;">', html)
#     return html


# def save_html(html_content: str, output_path: Path):
#     """Save HTML content to a file path."""
#     output_path.write_text(html_content, encoding="utf-8")


# def tables_to_structured_html(tables: list) -> str:
#     """
#     Reconstructs each 'table' block from the Content Understanding JSON
#     into a single <table> element, repeating header rows as needed.

#     Expects each table to be a dict containing:
#       - 'id' (str)
#       - 'rows' (list of lists of cell dicts)
#       - optional 'columns' metadata
#     """
#     html_parts = []
#     seen = set()
#     for tbl in tables:
#         tbl_id = tbl["id"]
#         # Only render each table once
#         if tbl_id in seen:
#             continue
#         # Gather all fragments for this table ID
#         frags = [t for t in tables if t["id"] == tbl_id]
#         seen.add(tbl_id)

#         # Start table with your styles
#         html_parts.append(
#             '<table style="width:100%; border-collapse:collapse; border:1px solid #ddd; margin:20px 0;">'
#         )

#         # Assume first row in first fragment is header
#         header = frags[0]["rows"][0]
#         html_parts.append("<thead>")
#         html_parts.append("  <tr>")
#         for cell in header:
#             html_parts.append(
#                 "<th style='border:1px solid #ddd; padding:8px; "
#                 "background-color:#215e99; color:white;'>"
#                 f"{cell.get('content', '').strip()}"
#                 "</th>"
#             )
#         html_parts.append("  </tr>")
#         html_parts.append("</thead>")

#         # Body: iterate every fragment, skip its first row (header)
#         html_parts.append("<tbody>")
#         for frag in frags:
#             for row in frag["rows"][1:]:
#                 html_parts.append("  <tr>")
#                 for cell in row:
#                     html_parts.append(
#                         "<td style='border:1px solid #ddd; padding:8px;'>"
#                         f"{cell.get('content', '').strip()}"
#                         "</td>"
#                     )
#                 html_parts.append("  </tr>")
#         html_parts.append("</tbody>")
#         html_parts.append("</table>")

#     return "\n".join(html_parts)


# def contents_to_structured_html(contents: list) -> str:
#     """
#     Combines markdown, paragraph lines, and tables into a single HTML.
#     Any table fragments in 'contents' will be handled via tables_to_structured_html.
#     """
#     parts = ["<!DOCTYPE html>", "<html><head><meta charset='utf-8'></head>", "<body>"]

#     # 1) Extract any table objects
#     tables = [c for c in contents if c.get("kind") == "table"]
#     if tables:
#         parts.append(tables_to_structured_html(tables))

#     # 2) Process other blocks
#     for item in contents:
#         # Skip table fragments since already rendered
#         if item.get("kind") == "table":
#             continue

#         if "markdown" in item:
#             parts.append(markdown_to_html(item["markdown"]))
#         elif "lines" in item:
#             text = " ".join(ln.get("content", "") for ln in item["lines"])
#             parts.append(f"<p>{text.strip()}</p>")

#     parts.append("</body></html>")
#     return "\n".join(parts)


# def contents_to_structured_html(contents: list) -> str:
#     """Convert raw Content Understanding JSON 'contents' into structured HTML with styled tables."""
#     parts = [
#         "<!DOCTYPE html>",
#         "<html>",
#         "<head>",
#         '<meta charset="utf-8">',
#         "</head>",
#         "<body>",
#     ]
#     for item in contents:
#         if "markdown" in item:
#             block_html = markdown_to_html(item["markdown"])
#             parts.append(block_html)
#         elif "lines" in item:
#             # Wrap raw lines into a paragraph
#             text = " ".join(ln.get("content", "") for ln in item.get("lines", []))
#             parts.append(f"<p>{text.strip()}</p>")
#     parts.extend(["</body>", "</html>"])
#     return "\n".join(parts)


# import base64
# import json
# import uuid

# from pathlib import Path
# import httpx
# from azure.core.credentials import AzureKeyCredential
# from azure.ai.formrecognizer import DocumentAnalysisClient
# import markdown as _markdown


# def generate_run_id() -> str:
#     """Generate a short 8-char hex run ID."""
#     return uuid.uuid4().hex[:8]


# # --- Azure helpers ---
# def call_azure_ocr(endpoint: str, api_key: str, pdf_path: str, model_id: str) -> dict:
#     """Call Azure Document Intelligence begin_analyze_document and return full response as dict."""
#     credential = AzureKeyCredential(api_key)
#     client = DocumentAnalysisClient(endpoint, credential)
#     with open(pdf_path, "rb") as f:
#         poller = client.begin_analyze_document(model_id, document=f)
#     result = poller.result()
#     return result.to_dict()


# # --- Mistral helpers ---
# def encode_pdf_to_base64(pdf_path: str) -> str:
#     with open(pdf_path, "rb") as f:
#         return base64.b64encode(f.read()).decode("utf-8")


# def call_mistral_ocr(endpoint: str, api_key: str, pdf_path: str) -> dict:
#     """Call Mistral OCR endpoint and return JSON response."""
#     headers = {
#         "Content-Type": "application/json",
#         "Accept": "application/json",
#         "Authorization": f"Bearer {api_key}",
#     }
#     encoded = encode_pdf_to_base64(pdf_path)
#     payload = {
#         "model": "mistral-ocr-2503",
#         "document": {
#             "type": "document_url",
#             "document_url": f"data:application/pdf;base64,{encoded}",
#         },
#         "include_image_base64": False,
#     }
#     with httpx.Client(timeout=60.0) as client:
#         resp = client.post(endpoint, headers=headers, json=payload)
#         resp.raise_for_status()
#         return resp.json()


# # --- Common output/save ---
# def extract_markdown_from_pages(pages: list) -> str:
#     """Join page markdown or lines into a single Markdown string."""
#     md_pages = []
#     # Azure pages use 'pages' with 'lines'; Mistral uses 'pages' with 'markdown'
#     for pg in pages:
#         if "markdown" in pg:
#             md = pg["markdown"]
#         else:
#             md = "\n".join([ln["content"] for ln in pg.get("lines", [])])
#         md_pages.append(md)
#     return "\n\n---\n\n".join(md_pages)


# def save_markdown(content: str, output_path: Path):
#     output_path.write_text(content, encoding="utf-8")


# def save_log(log_data: dict, log_path: Path):
#     log_path.write_text(json.dumps(log_data, indent=2), encoding="utf-8")


# # --- HTML helpers ---


# def markdown_to_html(markdown_content: str, **kwargs) -> str:
#     """Convert a Markdown string into HTML using Python-Markdown extensions."""
#     extensions = kwargs.pop("extensions", ["extra", "tables", "smarty"])
#     html = md_convert(markdown_content, extensions=extensions, **kwargs)
#     # Inline style tables, headers, and cells per design guidelines
#     html = re.sub(
#         r"<table>",
#         '<table style="width: 100%; border-collapse: collapse; border: 1px solid #ddd; margin: 20px 0;">',
#         html,
#     )
#     html = re.sub(
#         r"<th>",
#         '<th style="border: 1px solid #ddd; padding: 8px; background-color: #215e99; color: white;">',
#         html,
#     )
#     html = re.sub(r"<td>", '<td style="border: 1px solid #ddd; padding: 8px;">', html)
#     return html


# def save_html(html_content: str, output_path: Path):
#     """Save HTML content to a file path."""
#     output_path.write_text(html_content, encoding="utf-8")


# def contents_to_structured_html(contents: list) -> str:
#     """Convert raw Content Understanding JSON 'contents' into structured HTML with styled tables."""
#     parts = [
#         "<!DOCTYPE html>",
#         "<html>",
#         "<head>",
#         '<meta charset="utf-8">',
#         "</head>",
#         "<body>",
#     ]
#     for item in contents:
#         if "markdown" in item:
#             block_html = markdown_to_html(item["markdown"])
#             parts.append(block_html)
#         elif "lines" in item:
#             # Wrap raw lines into a paragraph
#             text = " ".join(ln.get("content", "") for ln in item.get("lines", []))
#             parts.append(f"<p>{text.strip()}</p>")
#     parts.extend(["</body>", "</html>"])
#     return "\n".join(parts)
