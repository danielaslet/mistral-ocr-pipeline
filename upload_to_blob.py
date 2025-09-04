import os
import yaml
from pathlib import Path
from azure.storage.blob import ContainerClient
from dotenv import load_dotenv

def upload_file_to_blob(local_file_path, blob_name=None):
    """Upload a file to the Azure blob container"""
    load_dotenv()
    
    BASE_DIR = Path(__file__).parent
    cfg_path = BASE_DIR / "analyze_content_understanding_blob_config.yaml"
    cfg = yaml.safe_load(cfg_path.read_text())
    
    blob_url = cfg["blob_container_url"].rstrip("/")
    sas_token = cfg["sas_token"].lstrip("?")
    
    container_client = ContainerClient.from_container_url(f"{blob_url}?{sas_token}")
    
    local_path = Path(local_file_path)
    if not local_path.exists():
        raise FileNotFoundError(f"File not found: {local_file_path}")
    
    # Use provided blob name or default to filename
    if blob_name is None:
        blob_name = local_path.name
    
    print(f"🔄 Uploading {local_path.name} to {blob_name}")
    
    with open(local_path, "rb") as data:
        container_client.upload_blob(name=blob_name, data=data, overwrite=True)
    
    print(f"✅ Uploaded successfully: {blob_name}")
    return blob_name

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python upload_to_blob.py <local_file_path> [blob_name]")
        sys.exit(1)
    
    local_file = sys.argv[1]
    blob_name = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        upload_file_to_blob(local_file, blob_name)
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        sys.exit(1)