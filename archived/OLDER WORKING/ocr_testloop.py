import os
import yaml
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

from ocr_helpers import (
    generate_run_id,
    call_azure_ocr,
    call_mistral_ocr,
    extract_markdown_from_pages,
    save_markdown,
    save_log,
)

# ─── Load environment variables ─────────────────────────────────────────────────
load_dotenv()

# ─── Load & validate YAML config ───────────────────────────────────────────────
config_path = Path("ocr_config.yaml")
if not config_path.exists():
    raise FileNotFoundError(f"No ocr_config.yaml found at {config_path.resolve()}")

config = yaml.safe_load(config_path.read_text())
if not isinstance(config, dict):
    raise ValueError("ocr_config.yaml did not parse into a dict")

required = ["input_pdf", "output_dir", "log_dir"]
for key in required:
    if key not in config:
        raise KeyError(f"Missing required key '{key}' in ocr_config.yaml")

input_pdf = Path(config["input_pdf"])
output_dir = Path(config["output_dir"])
log_dir = Path(config["log_dir"])

output_dir.mkdir(exist_ok=True)
log_dir.mkdir(exist_ok=True)

# ─── Credentials ───────────────────────────────────────────────────────────────
AZ_ENDPOINT = os.getenv("AZURE_DI_ENDPOINT")
AZ_KEY = os.getenv("AZURE_DI_API_KEY")
MI_ENDPOINT = os.getenv("AZURE_MISTRAL_OCR_ENDPOINT")
MI_KEY = os.getenv("AZURE_MISTRAL_OCR_API_KEY")

# ─── Modes to cycle through ─────────────────────────────────────────────────────
modes = [
    ("adi", "read", "prebuilt-read"),
    ("adi", "layout", "prebuilt-layout"),
    ("adi", "document", "prebuilt-document"),
    ("mistral", "mistral", None),
]

# ─── Main loop ─────────────────────────────────────────────────────────────────
for provider, mode_key, azure_model_id in modes:
    run_id = generate_run_id()
    basename = input_pdf.stem
    prefix = f"{basename}_{provider}_{mode_key}_{run_id}"
    md_file = output_dir / f"{prefix}.md"
    log_file = log_dir / f"{prefix}.log.json"

    if provider == "adi":
        resp = call_azure_ocr(AZ_ENDPOINT, AZ_KEY, str(input_pdf), azure_model_id)  # type: ignore
        pages = resp.get("pages", [])
    else:
        resp = call_mistral_ocr(MI_ENDPOINT, MI_KEY, str(input_pdf))  # type: ignore
        pages = resp.get("pages", [])

    # Extract and save Markdown
    markdown = extract_markdown_from_pages(pages)
    save_markdown(markdown, md_file)

    # Build and save run log
    log_data = {
        "run_id": run_id,
        "timestamp": datetime.utcnow().isoformat(),
        "provider": provider,
        "mode": mode_key,
        "input_file": str(input_pdf),
        "output_markdown": str(md_file),
        "response": resp,
    }
    save_log(log_data, log_file)

    print(f"▶ [{provider}:{mode_key}] Markdown → {md_file}")
    print(f"▶ [{provider}:{mode_key}] Log      → {log_file}")
