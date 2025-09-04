import os
import time
import yaml
import httpx
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv
from azure.storage.blob import ContainerClient

from analyze_content_understanding_helpers import (
    extract_raw_markdown,
    markdown_to_html,
    save_markdown,
    save_html,
    save_log,
)

class BlobProcessor:
    def __init__(self):
        load_dotenv()
        self.base_dir = Path(__file__).parent
        self._load_config()
        self._setup_directories()
        self._validate_credentials()
    
    def _load_config(self):
        """Load configuration from YAML file"""
        cfg_path = self.base_dir / "analyze_content_understanding_blob_config.yaml"
        cfg = yaml.safe_load(cfg_path.read_text())
        
        self.blob_url = cfg["blob_container_url"].rstrip("/")
        self.sas_token = cfg["sas_token"].lstrip("?")
        prefix = cfg.get("prefix", "").strip()
        self.blob_prefix = prefix + "/" if prefix else ""
        
        self.analyzer_id = cfg["analyzer_id"]
        self.enable_viz = cfg.get("enable_visualization", False)
        self.viz_rules = cfg.get("visualization_rules") if self.enable_viz else None
        
        # Output directories
        self.log_dir = self.base_dir / cfg["log_output_dir"]
        self.md_dir = self.base_dir / cfg["markdown_output_dir"]
        self.html_dir = self.base_dir / cfg["html_output_dir"]
    
    def _setup_directories(self):
        """Create output directories if they don't exist"""
        for d in [self.log_dir, self.md_dir, self.html_dir]:
            d.mkdir(parents=True, exist_ok=True)
    
    def _validate_credentials(self):
        """Validate required environment variables"""
        self.endpoint = os.getenv("AIFOUNDARY_API_ENDPOINT", "").rstrip("/")
        self.key = os.getenv("AIFOUNDARY_API_KEY", "")
        if not self.endpoint or not self.key:
            raise EnvironmentError("AIFOUNDARY_API_ENDPOINT and AIFOUNDARY_API_KEY must be set")
    
    def get_pdf_blobs(self) -> List[str]:
        """Get list of PDF files in blob container"""
        container_client = ContainerClient.from_container_url(f"{self.blob_url}?{self.sas_token}")
        pdf_blobs = [
            blob.name
            for blob in container_client.list_blobs(name_starts_with=self.blob_prefix)
            if blob.name.endswith(".pdf")
        ]
        return pdf_blobs
    
    def process_single_blob(self, blob_name: str) -> Dict:
        """Process a single PDF blob and return results"""
        file_url = f"{self.blob_url}/{blob_name}?{self.sas_token}"
        post_url = f"{self.endpoint}/contentunderstanding/analyzers/{self.analyzer_id}:analyze?api-version=2025-05-01-preview"
        
        headers = {
            "Ocp-Apim-Subscription-Key": self.key,
            "Content-Type": "application/json",
        }
        
        with httpx.Client(timeout=60.0) as client:
            # Submit for processing
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
                    raise RuntimeError(f"Analysis failed for {blob_name}")
                time.sleep(1)
        
        # Save outputs
        base = Path(blob_name).stem
        log_path = self.log_dir / f"{base}.json"
        raw_md_path = self.md_dir / f"{base}.md"
        styled_path = self.html_dir / f"{base}.html"
        
        save_log(data, log_path)
        contents = data.get("result", {}).get("contents", [])
        md_raw = extract_raw_markdown(contents)
        save_markdown(md_raw, raw_md_path)
        styled_html = markdown_to_html(md_raw, visualization_rules=self.viz_rules)
        save_html(styled_html, styled_path)
        
        return {
            "blob_name": blob_name,
            "status": "completed",
            "outputs": {
                "log": str(log_path),
                "markdown": str(raw_md_path),
                "html": str(styled_path)
            }
        }
    
    def process_all_blobs(self) -> Dict:
        """Process all PDF blobs in container"""
        pdf_blobs = self.get_pdf_blobs()
        
        if not pdf_blobs:
            return {
                "status": "no_files",
                "message": "No PDF files found in blob container",
                "files_processed": 0,
                "results": []
            }
        
        results = []
        for idx, blob_name in enumerate(pdf_blobs, 1):
            try:
                result = self.process_single_blob(blob_name)
                result["index"] = idx
                result["total"] = len(pdf_blobs)
                results.append(result)
            except Exception as e:
                results.append({
                    "blob_name": blob_name,
                    "status": "failed",
                    "error": str(e),
                    "index": idx,
                    "total": len(pdf_blobs)
                })
        
        return {
            "status": "completed",
            "files_processed": len(pdf_blobs),
            "results": results,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

# Backwards compatibility function for existing script
def process_blob_batch() -> Dict:
    """Process all blobs - backwards compatibility function"""
    processor = BlobProcessor()
    return processor.process_all_blobs()