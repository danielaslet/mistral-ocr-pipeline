"""
pdf_raster_compare.py (with YAML config)

Compare two PDF-to-image rasterization engines:
- PyMuPDF (fitz)
- pdf2image (Poppler)

Reads input, output, and engine settings from `pdf_raster_config.yaml`.
"""

import os
import time
import yaml
import fitz
from pathlib import Path
from pdf2image import convert_from_path
from hashlib import md5

# ─── Load YAML config ──────────────────────────────────────────────────────────
CONFIG_PATH = Path("pdf_raster_config.yaml")
if not CONFIG_PATH.exists():
    raise FileNotFoundError("Missing pdf_raster_config.yaml")

with open(CONFIG_PATH) as f:
    config = yaml.safe_load(f)

INPUT_PDF = Path(config.get("input_pdf", "./TableExample.pdf"))
OUTPUT_BASE = Path(config.get("output_dir", "./raster_output"))
DPI = config.get("dpi", 150)
ENABLED_ENGINES = config.get("engines", ["pymupdf", "pdf2image"])


# ─── Utils ─────────────────────────────────────────────────────────────────────
def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def checksum(path: Path):
    return md5(path.read_bytes()).hexdigest()


# ─── PyMuPDF Engine ────────────────────────────────────────────────────────────
def render_with_pymupdf(pdf_path: Path, out_dir: Path, dpi: int):
    t0 = time.time()
    ensure_dir(out_dir)
    doc = fitz.open(pdf_path)
    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)
    output = []
    for i, page in enumerate(doc):
        pix = page.get_pixmap(matrix=matrix)
        img_path = out_dir / f"page_{i + 1:03}_pymupdf.png"
        pix.save(str(img_path))
        output.append(img_path)
    return time.time() - t0, output


# ─── pdf2image Engine ──────────────────────────────────────────────────────────
def render_with_pdf2image(pdf_path: Path, out_dir: Path, dpi: int):
    t0 = time.time()
    ensure_dir(out_dir)
    images = convert_from_path(str(pdf_path), dpi=dpi)
    output = []
    for i, img in enumerate(images):
        img_path = out_dir / f"page_{i + 1:03}_pdf2image.png"
        img.save(img_path, "PNG")
        output.append(img_path)
    return time.time() - t0, output


# ─── Main Compare Logic ────────────────────────────────────────────────────────
def compare_raster_engines(pdf_path: Path, base_out_dir: Path, dpi: int):
    engines = {
        "pymupdf": render_with_pymupdf,
        "pdf2image": render_with_pdf2image,
    }

    summary = {}
    for name in ENABLED_ENGINES:
        engine = engines.get(name)
        if engine is None:
            summary[name] = {"error": "Engine not implemented"}
            continue
        print(f"▶ Rasterizing with {name}...")
        out_dir = base_out_dir / name
        try:
            duration, images = engine(pdf_path, out_dir, dpi)
            summary[name] = {
                "time_sec": round(duration, 2),
                "images": [str(img) for img in images],
                "checksums": [checksum(img) for img in images],
                "size_kb": sum(os.path.getsize(img) for img in images) // 1024,
            }
        except Exception as e:
            summary[name] = {"error": str(e)}

    return summary


# ─── Execute ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    result = compare_raster_engines(INPUT_PDF, OUTPUT_BASE, DPI)
    from pprint import pprint

    pprint(result)
