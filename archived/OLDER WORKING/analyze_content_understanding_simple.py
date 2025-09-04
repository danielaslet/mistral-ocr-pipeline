# analyze_content_understanding_simple.py
import os
import time
import yaml
import httpx
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime, timezone

from analyze_content_understanding_helpers import (
    extract_raw_markdown,
    markdown_to_html,
    save_markdown,
    save_html,
    save_log,
)

# ─── Load environment & config ─────────────────────────────────────────
load_dotenv()
BASE_DIR = Path(__file__).parent
cfg_path = BASE_DIR / "analyze_content_understanding_config.yaml"
if not cfg_path.exists():
    raise FileNotFoundError(f"No config at {cfg_path!r}")

cfg = yaml.safe_load(cfg_path.read_text())
file_url = cfg["file_url"]
analyzer_id = cfg["analyzer_id"]
out_md_dir = BASE_DIR / cfg["output_dir"]
out_html_dir = BASE_DIR / cfg.get("html_output_dir", cfg["output_dir"])
out_md_dir.mkdir(parents=True, exist_ok=True)
out_html_dir.mkdir(parents=True, exist_ok=True)

# ─── Visualization rules from config ────────────────────────────────────
enable_viz = cfg.get("enable_visualization", False)
viz_rules = cfg.get("visualization_rules") if enable_viz else None

# ─── Validate credentials & endpoint ────────────────────────────────────
endpoint = os.getenv("AIFOUNDARY_API_ENDPOINT", "").rstrip("/")
key = os.getenv("AIFOUNDARY_API_KEY", "")
if not endpoint or not key:
    raise EnvironmentError("AIFOUNDARY_API_ENDPOINT and AIFOUNDARY_API_KEY must be set")

# ─── Submit to Content Understanding ────────────────────────────────────
api_ver = "2025-05-01-preview"
post_url = f"{endpoint}/contentunderstanding/analyzers/{analyzer_id}:analyze?api-version={api_ver}"
headers = {
    "Ocp-Apim-Subscription-Key": key,
    "Content-Type": "application/json",
}

with httpx.Client(timeout=60.0) as client:
    resp = client.post(post_url, headers=headers, json={"url": file_url})
    resp.raise_for_status()
    op_loc = resp.headers.get("Operation-Location")
    if not op_loc:
        raise RuntimeError("No Operation-Location returned by service.")

    # Poll until done
    while True:
        poll = client.get(op_loc, headers=headers)
        poll.raise_for_status()
        data = poll.json()
        status = data.get("status")
        if status == "Succeeded":
            break
        if status == "Failed":
            raise RuntimeError("Analysis failed.")
        time.sleep(1)

# ─── Prepare names & paths ──────────────────────────────────────────────
ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
base = Path(file_url.split("?", 1)[0]).stem
raw_md_path = out_md_dir / f"{base}_raw_{ts}.md"
styled_path = out_html_dir / f"{base}_styled_{ts}.html"
log_path = out_md_dir / f"{base}_log_{ts}.json"

# ─── Save raw JSON log ───────────────────────────────────────────────────
save_log(data, log_path)

# ─── Extract & save Raw Markdown ────────────────────────────────────────
contents = data.get("result", {}).get("contents", [])
md_raw = extract_raw_markdown(contents)
save_markdown(md_raw, raw_md_path)

# ─── Convert Raw MD → Styled HTML & Save ────────────────────────────────
styled_html = markdown_to_html(md_raw, visualization_rules=viz_rules)
save_html(styled_html, styled_path)

print("✅ Analysis complete.")
print(f"   • JSON log    → {log_path}")
print(f"   • Raw MD      → {raw_md_path}")
print(f"   • Styled HTML → {styled_path}")
