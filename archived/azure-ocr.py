import os
import argparse
from pathlib import Path
from dotenv import load_dotenv

import fitz  # PyMuPDF
from azure.core.credentials import AzureKeyCredential

# from azure.ai.documentintelligence import DocumentAnalysisClient
from azure.ai.formrecognizer import DocumentAnalysisClient

# ─── Load config ────────────────────────────────────────────────────────────────
load_dotenv()
ENDPOINT = os.getenv("AZURE_DI_ENDPOINT")
API_KEY = os.getenv("AZURE_DI_API_KEY")

# ─── Mapping of friendly names to prebuilt model IDs ──────────────────────────
MODEL_MAP = {
    "read": "prebuilt-read",  # OCR-only
    "layout": "prebuilt-layout",  # layout (tables, selection marks, etc.)
    "document": "prebuilt-document",  # general document understanding
}


def parse_args():
    p = argparse.ArgumentParser(
        description="OCR a PDF using Azure Document Intelligence and export Markdown."
    )
    p.add_argument(
        "input_pdf",
        help="Path to the PDF file to process",
    )
    p.add_argument(
        "-o",
        "--output",
        default="ocr_output.md",
        help="Path for the output Markdown file",
    )
    p.add_argument(
        "-m",
        "--model",
        choices=MODEL_MAP.keys(),
        default="read",
        help="Which prebuilt model to use: read | layout | document",
    )
    return p.parse_args()


def run_ocr_and_save_markdown(input_path: str, output_path: str, model_id: str):
    # Initialize client
    credential = AzureKeyCredential(API_KEY)
    client = DocumentAnalysisClient(ENDPOINT, credential)

    # Read file and dispatch to chosen prebuilt model
    with open(input_path, "rb") as f:
        poller = client.begin_analyze_document(model_id, document=f)
    result = poller.result()

    # Extract Markdown-like text per page
    pages_md = []
    for page in result.pages:
        lines = [line.content for line in page.lines]
        pages_md.append("\n".join(lines))

    combined_md = "\n\n---\n\n".join(pages_md)
    Path(output_path).write_text(combined_md, encoding="utf-8")
    print(f"▶ Model: {model_id}")
    print(f"▶ Saved OCR Markdown to: {output_path}")


if __name__ == "__main__":
    args = parse_args()
    model_id = MODEL_MAP[args.model]
    run_ocr_and_save_markdown(args.input_pdf, args.output, model_id)
