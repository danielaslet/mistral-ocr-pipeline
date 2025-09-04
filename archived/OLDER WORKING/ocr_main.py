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

# ─── Load environment vars ─────────────────────────────────────────────────────
load_dotenv()

# ─── Load & validate YAML config ──────────────────────────────────────────────
config_path = Path("ocr_config.yaml")
if not config_path.exists():
    raise FileNotFoundError(f"No ocr_config.yaml found at {config_path.resolve()}")

config = yaml.safe_load(config_path.read_text())
if not isinstance(config, dict):
    raise ValueError("config.yaml did not parse into a dict!")

required = ["provider", "input_pdf", "output_dir", "log_dir"]
for key in required:
    if key not in config:
        raise KeyError(f"Missing required key '{key}' in ocr_config.yaml")

provider = config["provider"]
model_key = config.get("model", "read")
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

# ─── Prepare run ───────────────────────────────────────────────────────────────
run_id = generate_run_id()
basename = input_pdf.stem
prefix = f"{basename}_{provider}_{model_key}_{run_id}"
md_path = output_dir / f"{prefix}.md"
log_path = log_dir / f"{prefix}.log.json"


def main():
    if provider == "adi":
        model_map = {
            "read": "prebuilt-read",
            "layout": "prebuilt-layout",
            "document": "prebuilt-document",
        }
        model_id = model_map.get(model_key)
        if model_id is None:
            raise ValueError(f"Unknown model '{model_key}' for provider 'adi'")
        resp = call_azure_ocr(AZ_ENDPOINT, AZ_KEY, str(input_pdf), model_id)  # type: ignore
        pages = resp.get("pages", [])
    else:
        resp = call_mistral_ocr(MI_ENDPOINT, MI_KEY, str(input_pdf))  # type: ignore
        pages = resp.get("pages", [])

    # Extract & save Markdown
    markdown = extract_markdown_from_pages(pages)
    save_markdown(markdown, md_path)

    # Build and save run log
    log_data = {
        "run_id": run_id,
        "timestamp": datetime.utcnow().isoformat(),
        "provider": provider,
        "model_key": model_key,
        "input_file": str(input_pdf),
        "output_markdown": str(md_path),
        "response": resp,
    }
    save_log(log_data, log_path)

    print(f"▶ Saved Markdown: {md_path}")
    print(f"▶ Saved Log:      {log_path}")


if __name__ == "__main__":
    main()
