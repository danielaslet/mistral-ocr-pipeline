import base64
import json
import httpx
import fitz  # PyMuPDF
from pathlib import Path
from dotenv import load_dotenv
import os

# Load API credentials
load_dotenv()
AZURE_MISTRAL_OCR_ENDPOINT = os.getenv("AZURE_MISTRAL_OCR_ENDPOINT")
AZURE_MISTRAL_OCR_API_KEY = os.getenv("AZURE_MISTRAL_OCR_API_KEY")

# Path to your local PDF
INPUT_DOCUMENT_PATH = (
    "/Users/danielaslet/waterfield_tech_vscode/Mistral OCR/TableExample.pdf"
)
OUTPUT_MARKDOWN_PATH = (
    "/Users/danielaslet/waterfield_tech_vscode/Mistral OCR/ocr_output.md"
)


def encode_pdf_to_base64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def call_ocr_model(encoded_pdf: str) -> dict:
    endpoint_url = f"{AZURE_MISTRAL_OCR_ENDPOINT}"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {AZURE_MISTRAL_OCR_API_KEY}",
    }
    payload = {
        "model": "mistral-ocr-2503",
        "document": {
            "type": "document_url",
            "document_url": f"data:application/pdf;base64,{encoded_pdf}",
        },
        "include_image_base64": False,
    }

    with httpx.Client(timeout=60.0) as client:
        response = client.post(endpoint_url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()


def save_markdown_from_ocr(ocr_response: dict, output_path: str):
    all_md = []
    for page in ocr_response.get("pages", []):
        all_md.append(page.get("markdown", ""))
    combined_md = "\n\n---\n\n".join(all_md)
    Path(output_path).write_text(combined_md, encoding="utf-8")
    print(f"Markdown saved to: {output_path}")


def main():
    encoded_pdf = encode_pdf_to_base64(INPUT_DOCUMENT_PATH)
    ocr_result = call_ocr_model(encoded_pdf)
    save_markdown_from_ocr(ocr_result, OUTPUT_MARKDOWN_PATH)


if __name__ == "__main__":
    main()
