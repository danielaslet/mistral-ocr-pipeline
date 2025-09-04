import os
import time
import yaml
import httpx
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv
from azure.storage.blob import ContainerClient

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
cfg_path = BASE_DIR / "analyze_content_understanding_blob_config.yaml"
cfg = yaml.safe_load(cfg_path.read_text())

# Load blob details
blob_url = cfg["blob_container_url"].rstrip("/")
sas_token = cfg["sas_token"].lstrip("?")
prefix = cfg.get("prefix", "").strip()
blob_prefix = prefix + "/" if prefix else ""

# Output folders
log_dir = BASE_DIR / cfg["log_output_dir"]
md_dir = BASE_DIR / cfg["markdown_output_dir"]
html_dir = BASE_DIR / cfg["html_output_dir"]
for d in [log_dir, md_dir, html_dir]:
    d.mkdir(parents=True, exist_ok=True)

# Analyzer and visualization config
analyzer_id = cfg["analyzer_id"]
enable_viz = cfg.get("enable_visualization", False)
viz_rules = cfg.get("visualization_rules") if enable_viz else None

# Validate credentials
endpoint = os.getenv("AIFOUNDARY_API_ENDPOINT", "").rstrip("/")
key = os.getenv("AIFOUNDARY_API_KEY", "")
if not endpoint or not key:
    raise EnvironmentError("AIFOUNDARY_API_ENDPOINT and AIFOUNDARY_API_KEY must be set")

# ─── Discover files in blob ─────────────────────────────────────────────
container_client = ContainerClient.from_container_url(f"{blob_url}?{sas_token}")
pdf_blobs = [
    blob.name
    for blob in container_client.list_blobs(name_starts_with=blob_prefix)
    if blob.name.endswith(".pdf")
]

if not pdf_blobs:
    print("⚠️ No PDF files found in specified blob location.")
    exit(0)

print(
    f"\n📦 Found {len(pdf_blobs)} PDF file(s) in blob container under '{prefix or '/'}':"
)
for i, name in enumerate(pdf_blobs, 1):
    print(f"   {i:>2}. {name}")

# ─── Submit and process each PDF ───────────────────────────────────────
api_ver = "2025-05-01-preview"
headers = {
    "Ocp-Apim-Subscription-Key": key,
    "Content-Type": "application/json",
}

for idx, blob_name in enumerate(pdf_blobs, 1):
    print(f"\n🔄 ({idx} of {len(pdf_blobs)}) Processing: {blob_name}")

    file_url = f"{blob_url}/{blob_name}?{sas_token}"
    post_url = f"{endpoint}/contentunderstanding/analyzers/{analyzer_id}:analyze?api-version={api_ver}"

    with httpx.Client(timeout=60.0) as client:
        resp = client.post(post_url, headers=headers, json={"url": file_url})
        resp.raise_for_status()
        op_loc = resp.headers.get("Operation-Location")
        if not op_loc:
            raise RuntimeError("No Operation-Location returned by service.")

        # Poll until complete
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

    # ─── Save output files (same base name) ─────────────────────────────
    base = Path(blob_name).stem

    log_path = log_dir / f"{base}.json"
    raw_md_path = md_dir / f"{base}.md"
    styled_path = html_dir / f"{base}.html"

    save_log(data, log_path)
    contents = data.get("result", {}).get("contents", [])
    md_raw = extract_raw_markdown(contents)
    save_markdown(md_raw, raw_md_path)
    styled_html = markdown_to_html(md_raw, visualization_rules=viz_rules)
    save_html(styled_html, styled_path)

    print("✅ Complete:")
    print(f"   • JSON log    → {log_path}")
    print(f"   • Raw MD      → {raw_md_path}")
    print(f"   • Styled HTML → {styled_path}")


# import os
# import time
# import yaml
# import httpx
# from pathlib import Path
# from datetime import datetime, timezone
# from dotenv import load_dotenv
# from azure.storage.blob import ContainerClient

# from analyze_content_understanding_helpers import (
#     extract_raw_markdown,
#     markdown_to_html,
#     save_markdown,
#     save_html,
#     save_log,
# )

# # ─── Load environment & config ─────────────────────────────────────────
# load_dotenv()
# BASE_DIR = Path(__file__).parent
# cfg_path = BASE_DIR / "analyze_content_understanding_blob_config.yaml"
# cfg = yaml.safe_load(cfg_path.read_text())

# # Load blob details
# blob_url = cfg["blob_container_url"].rstrip("/")
# sas_token = cfg["sas_token"].lstrip("?")
# prefix = cfg.get("prefix", "").strip()
# blob_prefix = prefix + "/" if prefix else ""

# # Output folders
# log_dir = BASE_DIR / cfg["log_output_dir"]
# md_dir = BASE_DIR / cfg["markdown_output_dir"]
# html_dir = BASE_DIR / cfg["html_output_dir"]
# for d in [log_dir, md_dir, html_dir]:
#     d.mkdir(parents=True, exist_ok=True)

# # Analyzer and visualization config
# analyzer_id = cfg["analyzer_id"]
# enable_viz = cfg.get("enable_visualization", False)
# viz_rules = cfg.get("visualization_rules") if enable_viz else None

# # Validate credentials
# endpoint = os.getenv("AIFOUNDARY_API_ENDPOINT", "").rstrip("/")
# key = os.getenv("AIFOUNDARY_API_KEY", "")
# if not endpoint or not key:
#     raise EnvironmentError("AIFOUNDARY_API_ENDPOINT and AIFOUNDARY_API_KEY must be set")

# # ─── Discover files in blob ─────────────────────────────────────────────
# container_client = ContainerClient.from_container_url(f"{blob_url}?{sas_token}")
# pdf_blobs = [
#     blob.name
#     for blob in container_client.list_blobs(name_starts_with=blob_prefix)
#     if blob.name.endswith(".pdf")
# ]

# if not pdf_blobs:
#     print("⚠️ No PDF files found in specified blob location.")
#     exit(0)

# print(
#     f"\n📦 Found {len(pdf_blobs)} PDF file(s) in blob container under '{prefix or '/'}':"
# )
# for i, name in enumerate(pdf_blobs, 1):
#     print(f"   {i:>2}. {name}")

# # ─── Submit and process each PDF ───────────────────────────────────────
# api_ver = "2025-05-01-preview"
# headers = {
#     "Ocp-Apim-Subscription-Key": key,
#     "Content-Type": "application/json",
# }

# for idx, blob_name in enumerate(pdf_blobs, 1):
#     print(f"\n🔄 ({idx} of {len(pdf_blobs)}) Processing: {blob_name}")

#     file_url = f"{blob_url}/{blob_name}?{sas_token}"
#     post_url = f"{endpoint}/contentunderstanding/analyzers/{analyzer_id}:analyze?api-version={api_ver}"

#     with httpx.Client(timeout=60.0) as client:
#         resp = client.post(post_url, headers=headers, json={"url": file_url})
#         resp.raise_for_status()
#         op_loc = resp.headers.get("Operation-Location")
#         if not op_loc:
#             raise RuntimeError("No Operation-Location returned by service.")

#         # Poll until complete
#         while True:
#             poll = client.get(op_loc, headers=headers)
#             poll.raise_for_status()
#             data = poll.json()
#             status = data.get("status")
#             if status == "Succeeded":
#                 break
#             if status == "Failed":
#                 raise RuntimeError("Analysis failed.")
#             time.sleep(1)

#     # ─── Save output files ───────────────────────────────────────────────
#     ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
#     base = Path(blob_name).stem

#     log_path = log_dir / f"{base}_log_{ts}.json"
#     raw_md_path = md_dir / f"{base}_raw_{ts}.md"
#     styled_path = html_dir / f"{base}_styled_{ts}.html"

#     save_log(data, log_path)
#     contents = data.get("result", {}).get("contents", [])
#     md_raw = extract_raw_markdown(contents)
#     save_markdown(md_raw, raw_md_path)
#     styled_html = markdown_to_html(md_raw, visualization_rules=viz_rules)
#     save_html(styled_html, styled_path)

#     print("✅ Complete:")
#     print(f"   • JSON log    → {log_path}")
#     print(f"   • Raw MD      → {raw_md_path}")
#     print(f"   • Styled HTML → {styled_path}")


# import os
# import time
# import yaml
# import httpx
# from pathlib import Path
# from datetime import datetime, timezone
# from dotenv import load_dotenv
# from azure.storage.blob import ContainerClient

# from analyze_content_understanding_helpers import (
#     extract_raw_markdown,
#     markdown_to_html,
#     save_markdown,
#     save_html,
#     save_log,
# )

# # ─── Load environment & config ─────────────────────────────────────────
# load_dotenv()
# BASE_DIR = Path(__file__).parent
# cfg_path = BASE_DIR / "analyze_content_understanding_blob_config.yaml"
# cfg = yaml.safe_load(cfg_path.read_text())

# # Load core config
# blob_url = cfg["blob_container_url"].rstrip("/")
# sas_token = cfg["sas_token"].lstrip("?")
# prefix = cfg.get("prefix", "").strip()
# blob_prefix = prefix + "/" if prefix else ""

# analyzer_id = cfg["analyzer_id"]
# out_md_dir = BASE_DIR / cfg["output_dir"]
# out_html_dir = BASE_DIR / cfg.get("html_output_dir", cfg["output_dir"])
# out_md_dir.mkdir(parents=True, exist_ok=True)
# out_html_dir.mkdir(parents=True, exist_ok=True)

# enable_viz = cfg.get("enable_visualization", False)
# viz_rules = cfg.get("visualization_rules") if enable_viz else None

# endpoint = os.getenv("AIFOUNDARY_API_ENDPOINT", "").rstrip("/")
# key = os.getenv("AIFOUNDARY_API_KEY", "")
# if not endpoint or not key:
#     raise EnvironmentError("AIFOUNDARY_API_ENDPOINT and AIFOUNDARY_API_KEY must be set")

# # ─── List blobs in folder (or root) ────────────────────────────────────
# container_client = ContainerClient.from_container_url(f"{blob_url}?{sas_token}")
# pdf_blobs = [
#     blob.name
#     for blob in container_client.list_blobs(name_starts_with=blob_prefix)
#     if blob.name.endswith(".pdf")
# ]

# if not pdf_blobs:
#     print("⚠️ No PDF files found in specified blob location.")
#     exit(0)

# # ─── Submit & Process Each File ────────────────────────────────────────
# api_ver = "2025-05-01-preview"
# headers = {
#     "Ocp-Apim-Subscription-Key": key,
#     "Content-Type": "application/json",
# }

# for blob_name in pdf_blobs:
#     print(f"\n🔍 Processing: {blob_name}")

#     # Reconstruct full URL
#     file_url = f"{blob_url}/{blob_name}?{sas_token}"

#     post_url = f"{endpoint}/contentunderstanding/analyzers/{analyzer_id}:analyze?api-version={api_ver}"

#     with httpx.Client(timeout=60.0) as client:
#         resp = client.post(post_url, headers=headers, json={"url": file_url})
#         resp.raise_for_status()
#         op_loc = resp.headers.get("Operation-Location")
#         if not op_loc:
#             raise RuntimeError("No Operation-Location returned by service.")

#         # Poll for result
#         while True:
#             poll = client.get(op_loc, headers=headers)
#             poll.raise_for_status()
#             data = poll.json()
#             status = data.get("status")
#             if status == "Succeeded":
#                 break
#             if status == "Failed":
#                 raise RuntimeError("Analysis failed.")
#             time.sleep(1)

#     # ─── Save Outputs ───────────────────────────────────────────────────
#     ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
#     base = Path(blob_name).stem
#     raw_md_path = out_md_dir / f"{base}_raw_{ts}.md"
#     styled_path = out_html_dir / f"{base}_styled_{ts}.html"
#     log_path = out_md_dir / f"{base}_log_{ts}.json"

#     save_log(data, log_path)
#     contents = data.get("result", {}).get("contents", [])
#     md_raw = extract_raw_markdown(contents)
#     save_markdown(md_raw, raw_md_path)
#     styled_html = markdown_to_html(md_raw, visualization_rules=viz_rules)
#     save_html(styled_html, styled_path)

#     print(f"✅ Complete: {blob_name}")
#     print(f"   • JSON log    → {log_path}")
#     print(f"   • Raw MD      → {raw_md_path}")
#     print(f"   • Styled HTML → {styled_path}")
